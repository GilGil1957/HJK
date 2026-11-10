-- =====================================================================
--  HJK GALVANOPLASTIA — Orçamentos ENIG          versão 1.1 (10/11/2026)
--  Script de instalação do banco de dados (Supabase / PostgreSQL)
--
--  Como usar: no painel do Supabase, abra "SQL Editor" → "New query",
--  cole TODO este arquivo e clique em "Run". Pode ser executado mais
--  de uma vez sem perder os preços já cadastrados (inclusive para
--  atualizar uma instalação da versão 1.0).
--
--  O que este script cria:
--    • Esquema "privado" (não exposto pela API pública), contendo:
--        parametros          → preço por cm² e valor mínimo (linha única)
--        administradores     → quem pode alterar os preços (o Josias)
--        segredo             → chave interna dos códigos de verificação
--        limite_requisicoes  → contadores contra consultas automatizadas
--        diagnostico         → indica se o IP do visitante está sendo
--                              identificado (sem guardar o IP)
--    • Funções públicas (chamadas pelo site):
--        servico_disponivel()        → público
--        calcular_orcamento(...)     → público, com limite de consultas
--        sou_administrador()         → usuário logado
--        obter_parametros()          → somente administrador
--        atualizar_parametros(...)   → somente administrador
--        verificar_orcamento(...)    → somente administrador
--
--  Nenhuma resposta pública devolve o preço por cm² ou o valor mínimo.
-- =====================================================================

create extension if not exists pgcrypto with schema extensions;

-- Assinaturas da versão 1.0 (substituídas nesta versão)
drop function if exists public.calcular_orcamento(numeric, numeric, integer, numeric);
drop function if exists public.verificar_orcamento(text, numeric, numeric, integer, numeric, numeric);
drop function if exists privado.codigo_verificacao(text, numeric, numeric, integer, numeric, numeric);

-- ---------------------------------------------------------------------
-- 1. Esquema privado e tabelas
-- ---------------------------------------------------------------------
create schema if not exists privado;
revoke all on schema privado from public;
revoke all on schema privado from anon, authenticated;

create table if not exists privado.parametros (
  id              smallint primary key default 1 check (id = 1),
  preco_cm2       numeric(14,6) check (preco_cm2 > 0),
  minimo_pedido   numeric(12,2) check (minimo_pedido >= 0),
  atualizado_em   timestamptz,
  atualizado_por  uuid
);
-- Linha única, inicialmente SEM preços: o serviço fica bloqueado até o
-- Josias cadastrar os valores pela área administrativa.
insert into privado.parametros (id) values (1) on conflict (id) do nothing;

create table if not exists privado.administradores (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  criado_em  timestamptz not null default now()
);

create table if not exists privado.segredo (
  id     smallint primary key default 1 check (id = 1),
  chave  bytea not null
);
insert into privado.segredo (id, chave)
values (1, extensions.gen_random_bytes(32))
on conflict (id) do nothing;

create table if not exists privado.limite_requisicoes (
  chave     text        not null,
  janela    timestamptz not null,
  contagem  integer     not null default 0,
  primary key (chave, janela)
);

-- Diagnóstico de identificação do visitante. Guarda somente QUAIS
-- cabeçalhos chegaram na última consulta, nunca os endereços IP.
create table if not exists privado.diagnostico (
  id                      smallint primary key default 1 check (id = 1),
  cf_connecting_ip        boolean,
  x_forwarded_for         boolean,
  x_real_ip               boolean,
  identificacao_usada     text,
  ultima_consulta         timestamptz
);
insert into privado.diagnostico (id) values (1) on conflict (id) do nothing;

alter table privado.parametros         enable row level security;
alter table privado.administradores    enable row level security;
alter table privado.segredo            enable row level security;
alter table privado.limite_requisicoes enable row level security;
alter table privado.diagnostico        enable row level security;
-- Sem políticas de RLS = nenhum acesso direto para anon/authenticated.
revoke all on all tables in schema privado from public, anon, authenticated;

-- ---------------------------------------------------------------------
-- 2. Funções internas (esquema privado — não acessíveis pela API)
-- ---------------------------------------------------------------------

-- Usuário atual é administrador?
create or replace function privado.eh_admin()
returns boolean
language sql stable
set search_path = ''
as $$
  select exists (
    select 1 from privado.administradores a where a.user_id = auth.uid()
  );
$$;

-- Normaliza textos livres (empresa, referência) para que a mensagem do
-- WhatsApp e o código de verificação usem exatamente o mesmo conteúdo:
-- remove caracteres de controle e os símbolos de formatação do WhatsApp
-- (* _ ~ `), junta espaços repetidos e apara as pontas.
create or replace function privado.normalizar_texto(p text)
returns text
language sql immutable
set search_path = ''
as $$
  select btrim(regexp_replace(
           regexp_replace(coalesce(p, ''), '[[:cntrl:]*_~`]', ' ', 'g'),
           '\s+', ' ', 'g'));
$$;

-- Referência normalizada; "não informada" equivale a vazio.
create or replace function privado.normalizar_referencia(p text)
returns text
language sql immutable
set search_path = ''
as $$
  select case when lower(privado.normalizar_texto(p)) in ('não informada', 'nao informada')
              then '' else privado.normalizar_texto(p) end;
$$;

-- Código de verificação (HMAC-SHA256, 10 caracteres hexadecimais = 40 bits).
-- Cobre TODOS os dados da mensagem: identificador-base, data e hora de
-- emissão, empresa, referência, dimensões, quantidade, SFA e valor.
create or replace function privado.codigo_verificacao(
  p_base text, p_emitido_em text, p_empresa text, p_referencia text,
  p_largura numeric, p_comprimento numeric, p_quantidade integer,
  p_sfa numeric, p_valor numeric)
returns text
language sql stable
set search_path = ''
as $$
  select upper(substr(encode(extensions.hmac(
           convert_to(
             p_base
             || '|' || btrim(p_emitido_em)
             || '|' || privado.normalizar_texto(p_empresa)
             || '|' || privado.normalizar_referencia(p_referencia)
             || '|' || round(p_largura, 2)::text
             || '|' || round(p_comprimento, 2)::text
             || '|' || p_quantidade::text
             || '|' || round(p_sfa, 2)::text
             || '|' || round(p_valor, 2)::text, 'UTF8'),
           (select s.chave from privado.segredo s where s.id = 1),
           'sha256'), 'hex'), 1, 10));
$$;

-- Limite contra consultas automatizadas.
-- Devolve NULL se a consulta pode prosseguir, ou a mensagem de bloqueio.
--
-- Identificação do visitante: SOMENTE o cabeçalho "cf-connecting-ip",
-- preenchido pela Cloudflare (que fica na frente do Supabase) com o IP
-- real da conexão e sobrescrito se o cliente tentar enviá-lo.
-- "x-forwarded-for" NÃO é usado porque o cliente pode forjá-lo.
-- Se o cabeçalho não existir, todos os visitantes compartilham um único
-- contador (mais restritivo, nunca mais permissivo).
--
-- Além do limite por visitante, há limites GLOBAIS do site (por minuto e
-- por dia) que não dependem de cabeçalho algum.
--
-- O IP não é armazenado: guarda-se apenas um resumo (HMAC) com a chave
-- secreta, e os contadores são apagados após 2 dias.
create or replace function privado.consumir_limite()
returns text
language plpgsql volatile
set search_path = ''
as $$
declare
  -- >>> Limites ajustáveis (editar aqui e executar o script novamente) <<<
  c_visitante_minuto constant integer := 10;    -- por visitante, por minuto
  c_visitante_hora   constant integer := 60;    -- por visitante, por hora
  c_site_minuto      constant integer := 120;   -- total do site, por minuto
  c_site_dia         constant integer := 3000;  -- total do site, por dia
  v_headers  json;
  v_ip       text;
  v_hash     text;
  v_n        integer;
begin
  begin
    v_headers := nullif(current_setting('request.headers', true), '')::json;
  exception when others then
    v_headers := null;
  end;

  v_ip := nullif(btrim(v_headers ->> 'cf-connecting-ip'), '');

  update privado.diagnostico set
    cf_connecting_ip    = v_ip is not null,
    x_forwarded_for     = nullif(btrim(v_headers ->> 'x-forwarded-for'), '') is not null,
    x_real_ip           = nullif(btrim(v_headers ->> 'x-real-ip'), '') is not null,
    identificacao_usada = case when v_ip is not null then 'cf-connecting-ip (por visitante)'
                               else 'AUSENTE — contador único para todos' end,
    ultima_consulta     = now()
  where id = 1;

  v_hash := encode(extensions.hmac(convert_to(coalesce(v_ip, 'sem-identificacao'), 'UTF8'),
                   (select s.chave from privado.segredo s where s.id = 1),
                   'sha256'), 'hex');

  -- Limpeza ocasional de contadores antigos
  if random() < 0.02 then
    delete from privado.limite_requisicoes where janela < now() - interval '2 days';
  end if;

  -- Por visitante
  insert into privado.limite_requisicoes as l (chave, janela, contagem)
  values ('m:' || v_hash, date_trunc('minute', now()), 1)
  on conflict (chave, janela) do update set contagem = l.contagem + 1
  returning l.contagem into v_n;
  if v_n > c_visitante_minuto then
    return 'Muitas consultas em pouco tempo. Aguarde alguns minutos e tente novamente.';
  end if;

  insert into privado.limite_requisicoes as l (chave, janela, contagem)
  values ('h:' || v_hash, date_trunc('hour', now()), 1)
  on conflict (chave, janela) do update set contagem = l.contagem + 1
  returning l.contagem into v_n;
  if v_n > c_visitante_hora then
    return 'Muitas consultas em pouco tempo. Aguarde alguns minutos e tente novamente.';
  end if;

  -- Globais do site (independentes de cabeçalho)
  insert into privado.limite_requisicoes as l (chave, janela, contagem)
  values ('site-minuto', date_trunc('minute', now()), 1)
  on conflict (chave, janela) do update set contagem = l.contagem + 1
  returning l.contagem into v_n;
  if v_n > c_site_minuto then
    return 'O serviço está recebendo muitas consultas neste momento. Tente novamente em alguns minutos.';
  end if;

  insert into privado.limite_requisicoes as l (chave, janela, contagem)
  values ('dia', date_trunc('day', now()), 1)
  on conflict (chave, janela) do update set contagem = l.contagem + 1
  returning l.contagem into v_n;
  if v_n > c_site_dia then
    return 'O limite diário de consultas foi atingido. Tente novamente amanhã ou fale com a HJK pelo WhatsApp.';
  end if;

  return null;
end;
$$;

revoke all on all functions in schema privado from public, anon, authenticated;

-- ---------------------------------------------------------------------
-- 3. Funções públicas
-- ---------------------------------------------------------------------

-- 3.1 Serviço disponível? (os dois parâmetros estão configurados)
create or replace function public.servico_disponivel()
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select coalesce((select p.preco_cm2 is not null and p.minimo_pedido is not null
                   from privado.parametros p where p.id = 1), false);
$$;

-- 3.2 Cálculo do orçamento (público, protegido por limite de consultas)
--     Empresa e referência são usadas apenas no código de verificação e
--     devolvidas normalizadas; nada é armazenado.
create or replace function public.calcular_orcamento(
  p_empresa text, p_referencia text,
  p_largura numeric, p_comprimento numeric, p_quantidade integer, p_sfa numeric)
returns jsonb
language plpgsql volatile security definer
set search_path = ''
as $$
declare
  v_bloqueio    text;
  v_preco       numeric;
  v_minimo      numeric;
  v_empresa     text;
  v_referencia  text;
  v_l           numeric;
  v_c           numeric;
  v_s           numeric;
  v_area_placa  numeric;
  v_area_total  numeric;
  v_calculado   numeric;
  v_final       numeric;
  v_agora       timestamp;
  v_emitido     text;
  v_base        text;
begin
  v_bloqueio := privado.consumir_limite();
  if v_bloqueio is not null then
    return jsonb_build_object('ok', false, 'codigo', 'limite', 'erro', v_bloqueio);
  end if;

  select p.preco_cm2, p.minimo_pedido into v_preco, v_minimo
  from privado.parametros p where p.id = 1;

  if v_preco is null or v_minimo is null then
    return jsonb_build_object('ok', false, 'codigo', 'indisponivel',
      'erro', 'O serviço de orçamento ainda não está disponível. Entre em contato com a HJK pelo WhatsApp.');
  end if;

  -- Validação das entradas
  v_empresa    := privado.normalizar_texto(p_empresa);
  v_referencia := privado.normalizar_referencia(p_referencia);
  if v_empresa = '' then
    return jsonb_build_object('ok', false, 'codigo', 'entrada', 'erro', 'Informe o nome da empresa.');
  end if;
  if char_length(v_empresa) > 120 or char_length(v_referencia) > 60 then
    return jsonb_build_object('ok', false, 'codigo', 'entrada',
      'erro', 'Nome da empresa (até 120 caracteres) ou referência (até 60) muito longos.');
  end if;

  if p_largura is null or p_comprimento is null or p_quantidade is null or p_sfa is null then
    return jsonb_build_object('ok', false, 'codigo', 'entrada', 'erro', 'Preencha todos os campos numéricos.');
  end if;

  v_l := round(p_largura, 2);
  v_c := round(p_comprimento, 2);
  v_s := round(p_sfa, 2);

  if not (v_l >= 1 and v_l <= 1000) then
    return jsonb_build_object('ok', false, 'codigo', 'entrada', 'erro', 'A largura deve estar entre 1 e 1.000 mm.');
  end if;
  if not (v_c >= 1 and v_c <= 1000) then
    return jsonb_build_object('ok', false, 'codigo', 'entrada', 'erro', 'O comprimento deve estar entre 1 e 1.000 mm.');
  end if;
  if not (p_quantidade >= 1 and p_quantidade <= 1000000) then
    return jsonb_build_object('ok', false, 'codigo', 'entrada', 'erro', 'A quantidade deve ser um número inteiro entre 1 e 1.000.000.');
  end if;
  if not (v_s > 0 and v_s <= 200) then
    return jsonb_build_object('ok', false, 'codigo', 'entrada', 'erro', 'O Surface Finish Area deve ser maior que 0% e no máximo 200%.');
  end if;

  -- Cálculo (aritmética decimal exata; arredondamento monetário no fim)
  v_area_placa := v_l * v_c * v_s / 10000;          -- cm² por placa
  v_area_total := v_area_placa * p_quantidade;       -- cm² do pedido
  v_calculado  := round(v_area_total * v_preco, 2);  -- R$
  v_final      := greatest(v_calculado, v_minimo);   -- mínimo uma vez por pedido

  -- Identificador sem histórico: data + aleatório + código de verificação
  v_agora   := now() at time zone 'America/Sao_Paulo';
  v_emitido := to_char(v_agora, 'DD/MM/YYYY HH24:MI');
  v_base    := 'HJK-' || to_char(v_agora, 'YYMMDD') || '-'
               || upper(encode(extensions.gen_random_bytes(2), 'hex'));

  return jsonb_build_object(
    'ok',              true,
    'id',              v_base || '-' || privado.codigo_verificacao(
                         v_base, v_emitido, v_empresa, v_referencia,
                         v_l, v_c, p_quantidade, v_s, v_final),
    'emitido_em',      v_emitido,
    'empresa',         v_empresa,
    'referencia',      v_referencia,
    'largura',         v_l,
    'comprimento',     v_c,
    'quantidade',      p_quantidade,
    'sfa',             v_s,
    'area_placa',      round(v_area_placa, 2),
    'area_total',      round(v_area_total, 2),
    'valor_calculado', v_calculado,
    'valor_final',     v_final,
    'valor_unitario',  round(v_final / p_quantidade, 2),
    'minimo_aplicado', v_final > v_calculado
  );
end;
$$;

-- 3.3 O usuário logado é administrador?
create or replace function public.sou_administrador()
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select privado.eh_admin();
$$;

-- 3.4 Consultar os parâmetros (somente administrador)
create or replace function public.obter_parametros()
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
declare
  v jsonb;
begin
  if not privado.eh_admin() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  select jsonb_build_object(
           'preco_cm2',     p.preco_cm2,
           'minimo_pedido', p.minimo_pedido,
           'atualizado_em', to_char(p.atualizado_em at time zone 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI'))
    into v
  from privado.parametros p where p.id = 1;
  return v;
end;
$$;

-- 3.5 Alterar os parâmetros (somente administrador)
create or replace function public.atualizar_parametros(p_preco_cm2 numeric, p_minimo_pedido numeric)
returns jsonb
language plpgsql volatile security definer
set search_path = ''
as $$
begin
  if not privado.eh_admin() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  if p_preco_cm2 is null or not (p_preco_cm2 > 0 and p_preco_cm2 <= 100) then
    raise exception 'O preço por cm² deve ser maior que zero e no máximo R$ 100,00.' using errcode = '22023';
  end if;
  if round(p_preco_cm2, 6) <> p_preco_cm2 then
    raise exception 'O preço por cm² aceita no máximo 6 casas decimais.' using errcode = '22023';
  end if;
  if p_minimo_pedido is null or not (p_minimo_pedido >= 0 and p_minimo_pedido <= 1000000) then
    raise exception 'O valor mínimo deve estar entre R$ 0,00 e R$ 1.000.000,00.' using errcode = '22023';
  end if;
  if round(p_minimo_pedido, 2) <> p_minimo_pedido then
    raise exception 'O valor mínimo aceita no máximo 2 casas decimais.' using errcode = '22023';
  end if;

  update privado.parametros
     set preco_cm2 = p_preco_cm2,
         minimo_pedido = p_minimo_pedido,
         atualizado_em = now(),
         atualizado_por = auth.uid()
   where id = 1;

  return public.obter_parametros();
end;
$$;

-- 3.6 Conferir um orçamento recebido pelo WhatsApp (somente administrador)
create or replace function public.verificar_orcamento(
  p_id text, p_emitido_em text, p_empresa text, p_referencia text,
  p_largura numeric, p_comprimento numeric, p_quantidade integer,
  p_sfa numeric, p_valor numeric)
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
declare
  v_id       text := upper(btrim(coalesce(p_id, '')));
  v_emitido  text := btrim(coalesce(p_emitido_em, ''));
  v_partes   text[];
  v_base     text;
  v_esperado text;
  v_preco    numeric;
  v_minimo   numeric;
  v_area     numeric;
  v_atual    numeric;
  v_valido   boolean;
begin
  if not privado.eh_admin() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;

  v_partes := regexp_match(v_id, '^HJK-([0-9]{6})-([0-9A-F]{4})-([0-9A-F]{10})$');
  if v_partes is null then
    return jsonb_build_object('valido', false,
      'motivo', 'Número do orçamento em formato inválido. O formato correto é HJK-AAMMDD-XXXX-XXXXXXXXXX.');
  end if;
  if v_emitido !~ '^\d{2}/\d{2}/\d{4} \d{2}:\d{2}$' then
    return jsonb_build_object('valido', false,
      'motivo', 'Informe a data e a hora de emissão no formato DD/MM/AAAA HH:MM, como aparece na mensagem.');
  end if;
  if privado.normalizar_texto(p_empresa) = '' or p_largura is null or p_comprimento is null
     or p_quantidade is null or p_sfa is null or p_valor is null or p_quantidade < 1 then
    return jsonb_build_object('valido', false, 'motivo', 'Preencha todos os dados do orçamento.');
  end if;

  v_base := 'HJK-' || v_partes[1] || '-' || v_partes[2];
  v_esperado := privado.codigo_verificacao(v_base, v_emitido, p_empresa, p_referencia,
                  p_largura, p_comprimento, p_quantidade, p_sfa, p_valor);
  v_valido := v_esperado = v_partes[3];

  v_area := round(p_largura, 2) * round(p_comprimento, 2) * round(p_sfa, 2) / 10000 * p_quantidade;

  select p.preco_cm2, p.minimo_pedido into v_preco, v_minimo from privado.parametros p where p.id = 1;
  if v_preco is not null and v_minimo is not null then
    v_atual := greatest(round(v_area * v_preco, 2), v_minimo);
  end if;

  return jsonb_build_object(
    'valido',          v_valido,
    'motivo',          case when v_valido
                            then 'Orçamento autêntico: todos os dados (empresa, referência, data, medidas, quantidade, percentual e valor) conferem com o emitido pelo sistema.'
                            else 'Algum dado NÃO confere com o código de verificação (empresa, referência, data/hora, medidas, quantidade, percentual ou valor). O orçamento pode ter sido alterado ou digitado incorretamente.'
                       end,
    'emitido_em',      v_emitido,
    'area_total',      round(v_area, 2),
    'valor_informado', round(p_valor, 2),
    'valor_com_precos_atuais', v_atual
  );
end;
$$;

-- ---------------------------------------------------------------------
-- 4. Permissões das funções públicas
-- ---------------------------------------------------------------------
revoke all on function public.servico_disponivel()                    from public, anon, authenticated;
revoke all on function public.calcular_orcamento(text, text, numeric, numeric, integer, numeric) from public, anon, authenticated;
revoke all on function public.sou_administrador()                     from public, anon, authenticated;
revoke all on function public.obter_parametros()                      from public, anon, authenticated;
revoke all on function public.atualizar_parametros(numeric, numeric)  from public, anon, authenticated;
revoke all on function public.verificar_orcamento(text, text, text, text, numeric, numeric, integer, numeric, numeric) from public, anon, authenticated;

grant execute on function public.servico_disponivel()                    to anon, authenticated;
grant execute on function public.calcular_orcamento(text, text, numeric, numeric, integer, numeric) to anon, authenticated;
grant execute on function public.sou_administrador()                     to authenticated;
grant execute on function public.obter_parametros()                      to authenticated;
grant execute on function public.atualizar_parametros(numeric, numeric)  to authenticated;
grant execute on function public.verificar_orcamento(text, text, text, text, numeric, numeric, integer, numeric, numeric) to authenticated;

-- ---------------------------------------------------------------------
-- 5. Conferência do diagnóstico (executar à parte, no SQL Editor, depois
--    de fazer um orçamento pelo site publicado):
--
--    select * from privado.diagnostico;
--
--    O esperado é cf_connecting_ip = true e
--    identificacao_usada = 'cf-connecting-ip (por visitante)'.
-- ---------------------------------------------------------------------

-- Fim da instalação.
