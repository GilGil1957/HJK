-- =====================================================================
--  HJK GALVANOPLASTIA — Orçamentos ENIG          versão 2.0 (18/11/2026)
--  Script de instalação / atualização do banco (Supabase / PostgreSQL)
--
--  Como usar: no Supabase, "SQL Editor" → "New query", cole TODO este
--  arquivo e clique em "Run". Pode ser executado mais de uma vez: os
--  valores já cadastrados pelo administrador são preservados.
--  Atualiza instalações das versões 1.0 e 1.1.
--
--  MODELO DE PREÇO (planilha REFERENCIAS_ENIG, com as decisões de 18/11):
--    área ENIG (cm²)   = largura × comprimento × quantidade × SFA% / 10.000
--    sal de ouro (g)   = área × camada(µm)/10.000 × densidade × fator do sal
--    químicos          = Σ preço × consumo × sal de ouro
--                        (itens "ouro": usam a camada pedida;
--                         itens "área": usam a camada de referência)
--                        + itens indexados (% do custo de outro item)
--    painéis           = ⌈área bruta das placas ÷ área do painel padrão⌉
--    horas             = ⌈painéis ÷ painéis por hora + horas adicionais⌉
--    custo             = químicos + horas × valor da hora + custo fixo
--    preço             = custo × (1 + margem%) ÷ (1 − tributos%)
--    valor final       = MÁXIMO(preço, valor mínimo por pedido)
--
--  Os VALORES INICIAIS deste script são FICTÍCIOS (somente para testes).
--  Os valores reais são digitados pelo Josias na área administrativa e
--  nunca ficam neste arquivo, que é público no GitHub.
-- =====================================================================

create extension if not exists pgcrypto with schema extensions;

-- ---------------------------------------------------------------------
-- 0. Remoção das funções das versões anteriores
-- ---------------------------------------------------------------------
drop function if exists public.calcular_orcamento(numeric, numeric, integer, numeric);
drop function if exists public.calcular_orcamento(text, text, numeric, numeric, integer, numeric);
drop function if exists public.verificar_orcamento(text, numeric, numeric, integer, numeric, numeric);
drop function if exists public.verificar_orcamento(text, text, text, text, numeric, numeric, integer, numeric, numeric);
drop function if exists public.obter_parametros();
drop function if exists public.atualizar_parametros(numeric, numeric);
drop function if exists privado.codigo_verificacao(text, numeric, numeric, integer, numeric, numeric);
drop function if exists privado.codigo_verificacao(text, text, text, text, numeric, numeric, integer, numeric, numeric);

-- ---------------------------------------------------------------------
-- 1. Esquema privado e tabelas
-- ---------------------------------------------------------------------
create schema if not exists privado;
revoke all on schema privado from public;
revoke all on schema privado from anon, authenticated;

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

create table if not exists privado.diagnostico (
  id                      smallint primary key default 1 check (id = 1),
  cf_connecting_ip        boolean,
  x_forwarded_for         boolean,
  x_real_ip               boolean,
  identificacao_usada     text,
  ultima_consulta         timestamptz
);
insert into privado.diagnostico (id) values (1) on conflict (id) do nothing;

-- Parâmetros gerais (catálogo com rótulos e limites de validação)
create table if not exists privado.config (
  chave      text primary key,
  grupo      text    not null,
  rotulo     text    not null,
  unidade    text    not null default '',
  valor      numeric not null,
  minimo     numeric not null,
  maximo     numeric not null,
  casas      integer not null,
  ordem      integer not null,
  ajuda      text    not null default '',
  atualizado_em  timestamptz,
  atualizado_por uuid
);

-- Materiais/químicos
--   tipo 'consumo'  : custo = preço × consumo × sal de ouro (g)
--   tipo 'indexado' : custo = percentual% × custo do item de referência
--   base 'ouro'     : acompanha a camada pedida pelo cliente
--   base 'area'     : acompanha só a área (sal calculado na camada de referência)
create table if not exists privado.quimicos (
  codigo      text primary key,
  nome        text    not null,
  unidade     text    not null default '',
  tipo        text    not null check (tipo in ('consumo', 'indexado')),
  preco       numeric not null default 0 check (preco >= 0),
  consumo     numeric not null default 0 check (consumo >= 0),
  base        text    not null default 'area' check (base in ('ouro', 'area')),
  referencia  text,
  percentual  numeric not null default 0 check (percentual >= 0),
  ordem       integer not null,
  atualizado_em  timestamptz,
  atualizado_por uuid
);

-- Valores iniciais FICTÍCIOS (insere somente o que ainda não existe)
insert into privado.config (chave, grupo, rotulo, unidade, valor, minimo, maximo, casas, ordem, ajuda) values
  ('camada_min',       'camada',   'Camada mínima aceita',              'µm',  0.03,   0.01,  1,       3, 10, 'Menor camada de ouro que o cliente pode pedir.'),
  ('camada_padrao',    'camada',   'Camada padrão (já preenchida)',     'µm',  0.09,   0.01,  1,       3, 20, 'Valor que aparece preenchido no formulário do cliente.'),
  ('camada_max',       'camada',   'Camada máxima aceita',              'µm',  0.10,   0.01,  1,       3, 30, 'IPC-4552A: máximo de 0,10 µm para ENIG.'),
  ('valor_hora',       'producao', 'Valor da hora de mão de obra',      'R$',  50.00,  0,     100000,  2, 10, ''),
  ('paineis_hora',     'producao', 'Painéis processados por hora',      'painéis/h', 40, 0.01, 100000, 2, 20, ''),
  ('horas_adicionais', 'producao', 'Horas adicionais por pedido',       'h',   1,      0,     1000,    2, 30, 'Somadas antes do arredondamento para cima (preparação).'),
  ('painel_largura',   'producao', 'Painel padrão — largura',           'mm',  245,    10,    5000,    1, 40, 'Usado para estimar quantos painéis o pedido ocupa.'),
  ('painel_comprimento','producao','Painel padrão — comprimento',       'mm',  141,    10,    5000,    1, 50, ''),
  ('custo_fixo',       'producao', 'Custo fixo por pedido',             'R$',  50.00,  0,     1000000, 2, 60, ''),
  ('margem',           'comercial','Margem sobre o custo',              '%',   50,     0,     1000,    2, 10, 'Ex.: 50% → custo × 1,5.'),
  ('tributos',         'comercial','Tributos (por dentro do preço)',    '%',   15,     0,     60,      2, 20, 'Preço = custo com margem ÷ (1 − tributos).'),
  ('minimo_pedido',    'comercial','Valor mínimo por pedido',           'R$',  0,      0,     1000000, 2, 30, '0 = sem mínimo.'),
  ('densidade',        'tecnico',  'Densidade do ouro',                 'g/cm³', 19,   1,     100,     4, 10, ''),
  ('fator_sal',        'tecnico',  'Fator ouro → sal (aurocianeto)',    '×',   1.47,   0.01,  100,     4, 20, ''),
  ('camada_ref',       'tecnico',  'Camada de referência dos consumos', 'µm',  0.09,   0.01,  1,       3, 30, 'Camada usada para os itens que acompanham só a área.')
on conflict (chave) do update
  set grupo = excluded.grupo, rotulo = excluded.rotulo, unidade = excluded.unidade,
      minimo = excluded.minimo, maximo = excluded.maximo, casas = excluded.casas,
      ordem = excluded.ordem, ajuda = excluded.ajuda;          -- valor preservado

insert into privado.quimicos (codigo, nome, unidade, tipo, preco, consumo, base, referencia, percentual, ordem) values
  ('aurocianeto',   'Aurocianeto (sal de ouro)', 'g', 'consumo',  500.00, 1.00, 'ouro', null, 0, 10),
  ('parte_a',       'Parte A',                    'L', 'consumo',  200.00, 0.30, 'area', null, 0, 20),
  ('parte_b',       'Parte B',                    'L', 'consumo',  200.00, 0.30, 'area', null, 0, 30),
  ('preparadora',   'Preparadora',                'L', 'consumo',  200.00, 0.20, 'area', null, 0, 40),
  ('agua',          'Água',                       '',  'indexado',   0,    0,    'area', 'parte_a', 100, 50),
  ('energia',       'Energia',                    '',  'indexado',   0,    0,    'area', 'parte_a',  50, 60),
  ('sulfurico',     'Ácido sulfúrico',            'L', 'consumo',    5.00, 0.80, 'area', null, 0, 70),
  ('sulfurico_pa',  'Ácido sulfúrico PA',         'L', 'consumo',   30.00, 0.20, 'area', null, 0, 80),
  ('desengraxante', 'Desengraxante',              'L', 'consumo',   20.00, 0.20, 'area', null, 0, 90),
  ('persulfato',    'Persulfato',                 'kg','consumo',   40.00, 0.10, 'area', null, 0, 100),
  ('paladio',       'Paládio (ativador)',         'L', 'consumo',  250.00, 0.10, 'area', null, 0, 110)
on conflict (codigo) do update
  set nome = excluded.nome, unidade = excluded.unidade, tipo = excluded.tipo,
      referencia = excluded.referencia, ordem = excluded.ordem;   -- preço, consumo, base e % preservados

-- Tabela de parâmetros da versão 1.x (não é mais usada)
drop table if exists privado.parametros;

alter table privado.administradores    enable row level security;
alter table privado.segredo            enable row level security;
alter table privado.limite_requisicoes enable row level security;
alter table privado.diagnostico        enable row level security;
alter table privado.config             enable row level security;
alter table privado.quimicos           enable row level security;
revoke all on all tables in schema privado from public, anon, authenticated;

-- ---------------------------------------------------------------------
-- 2. Funções internas (esquema privado — não acessíveis pela API)
-- ---------------------------------------------------------------------
create or replace function privado.eh_admin()
returns boolean language sql stable set search_path = ''
as $$
  select exists (select 1 from privado.administradores a where a.user_id = auth.uid());
$$;

create or replace function privado.cfg(p_chave text)
returns numeric language sql stable set search_path = ''
as $$
  select c.valor from privado.config c where c.chave = p_chave;
$$;

create or replace function privado.normalizar_texto(p text)
returns text language sql immutable set search_path = ''
as $$
  select btrim(regexp_replace(
           regexp_replace(coalesce(p, ''), '[[:cntrl:]*_~`]', ' ', 'g'),
           '\s+', ' ', 'g'));
$$;

create or replace function privado.normalizar_referencia(p text)
returns text language sql immutable set search_path = ''
as $$
  select case when lower(privado.normalizar_texto(p)) in ('não informada', 'nao informada')
              then '' else privado.normalizar_texto(p) end;
$$;

-- Código de verificação (HMAC-SHA256, 10 hex = 40 bits) — cobre todos os
-- dados da mensagem, inclusive a camada de ouro.
create or replace function privado.codigo_verificacao(
  p_base text, p_emitido_em text, p_empresa text, p_referencia text,
  p_largura numeric, p_comprimento numeric, p_quantidade integer,
  p_sfa numeric, p_camada numeric, p_valor numeric)
returns text language sql stable set search_path = ''
as $$
  select upper(substr(encode(extensions.hmac(
           convert_to(
             'v2|' || p_base
             || '|' || btrim(p_emitido_em)
             || '|' || privado.normalizar_texto(p_empresa)
             || '|' || privado.normalizar_referencia(p_referencia)
             || '|' || round(p_largura, 2)::text
             || '|' || round(p_comprimento, 2)::text
             || '|' || p_quantidade::text
             || '|' || round(p_sfa, 2)::text
             || '|' || round(p_camada, 3)::text
             || '|' || round(p_valor, 2)::text, 'UTF8'),
           (select s.chave from privado.segredo s where s.id = 1),
           'sha256'), 'hex'), 1, 10));
$$;

-- Limite contra consultas automatizadas (igual à versão 1.1)
create or replace function privado.consumir_limite()
returns text language plpgsql volatile set search_path = ''
as $$
declare
  c_visitante_minuto constant integer := 10;
  c_visitante_hora   constant integer := 60;
  c_site_minuto      constant integer := 120;
  c_site_dia         constant integer := 3000;
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
                   (select s.chave from privado.segredo s where s.id = 1), 'sha256'), 'hex');

  if random() < 0.02 then
    delete from privado.limite_requisicoes where janela < now() - interval '2 days';
  end if;

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

-- Validação das entradas do orçamento. Devolve a mensagem de erro ou NULL.
create or replace function privado.validar_entrada(
  p_largura numeric, p_comprimento numeric, p_quantidade integer, p_sfa numeric, p_camada numeric)
returns text language plpgsql stable set search_path = ''
as $$
declare
  v_min numeric := privado.cfg('camada_min');
  v_max numeric := privado.cfg('camada_max');
begin
  if p_largura is null or p_comprimento is null or p_quantidade is null or p_sfa is null or p_camada is null then
    return 'Preencha todos os campos numéricos.';
  end if;
  if not (round(p_largura, 2) >= 1 and round(p_largura, 2) <= 1000) then
    return 'A largura deve estar entre 1 e 1.000 mm.';
  end if;
  if not (round(p_comprimento, 2) >= 1 and round(p_comprimento, 2) <= 1000) then
    return 'O comprimento deve estar entre 1 e 1.000 mm.';
  end if;
  if not (p_quantidade >= 1 and p_quantidade <= 1000000) then
    return 'A quantidade deve ser um número inteiro entre 1 e 1.000.000.';
  end if;
  if not (round(p_sfa, 2) > 0 and round(p_sfa, 2) <= 200) then
    return 'O Surface Finish Area deve ser maior que 0% e no máximo 200%.';
  end if;
  if not (round(p_camada, 3) >= v_min and round(p_camada, 3) <= v_max) then
    return 'A camada de ouro deve estar entre ' || replace(rtrim(rtrim(v_min::text, '0'), '.'), '.', ',')
           || ' e ' || replace(rtrim(rtrim(v_max::text, '0'), '.'), '.', ',') || ' µm.';
  end if;
  return null;
end;
$$;

-- Cálculo completo (uso interno). Entradas já validadas e arredondadas.
-- Devolve todos os componentes; a função pública filtra o que é exibido.
create or replace function privado.calcular(
  p_largura numeric, p_comprimento numeric, p_quantidade integer, p_sfa numeric, p_camada numeric)
returns jsonb language plpgsql stable set search_path = ''
as $$
declare
  v_area_placa  numeric;
  v_area        numeric;
  v_fator       numeric;
  v_sal_ouro    numeric;
  v_sal_ref     numeric;
  v_itens       jsonb := '[]'::jsonb;
  v_custos      jsonb := '{}'::jsonb;
  v_quim        numeric := 0;
  v_custo_item  numeric;
  r             record;
  v_area_bruta  numeric;
  v_painel      numeric;
  v_paineis     numeric;
  v_horas       numeric;
  v_mo          numeric;
  v_fixo        numeric := privado.cfg('custo_fixo');
  v_custo       numeric;
  v_com_margem  numeric;
  v_preco       numeric;
  v_calculado   numeric;
  v_minimo      numeric := privado.cfg('minimo_pedido');
  v_final       numeric;
begin
  v_area_placa := p_largura * p_comprimento * p_sfa / 10000;
  v_area       := v_area_placa * p_quantidade;
  v_fator      := privado.cfg('densidade') * privado.cfg('fator_sal') / 10000;
  v_sal_ouro   := v_area * p_camada * v_fator;
  v_sal_ref    := v_area * privado.cfg('camada_ref') * v_fator;

  -- Itens de consumo
  for r in select * from privado.quimicos q where q.tipo = 'consumo' order by q.ordem loop
    v_custo_item := r.preco * r.consumo * (case when r.base = 'ouro' then v_sal_ouro else v_sal_ref end);
    v_custos := v_custos || jsonb_build_object(r.codigo, v_custo_item);
    v_quim := v_quim + v_custo_item;
    v_itens := v_itens || jsonb_build_object('codigo', r.codigo, 'nome', r.nome, 'ordem', r.ordem,
                 'quantidade', round(r.consumo * (case when r.base = 'ouro' then v_sal_ouro else v_sal_ref end), 5),
                 'unidade', r.unidade, 'custo', round(v_custo_item, 2));
  end loop;
  -- Itens indexados (% do custo de outro item)
  for r in select * from privado.quimicos q where q.tipo = 'indexado' order by q.ordem loop
    v_custo_item := coalesce((v_custos ->> r.referencia)::numeric, 0) * r.percentual / 100;
    v_quim := v_quim + v_custo_item;
    v_itens := v_itens || jsonb_build_object('codigo', r.codigo, 'nome', r.nome, 'ordem', r.ordem,
                 'quantidade', null, 'unidade', '', 'custo', round(v_custo_item, 2));
  end loop;

  v_area_bruta := p_largura * p_comprimento / 100 * p_quantidade;                 -- cm²
  v_painel     := privado.cfg('painel_largura') * privado.cfg('painel_comprimento') / 100;
  v_paineis    := ceil(v_area_bruta / v_painel);
  v_horas      := ceil(v_paineis / privado.cfg('paineis_hora') + privado.cfg('horas_adicionais'));
  v_mo         := v_horas * privado.cfg('valor_hora');

  v_custo      := v_quim + v_mo + v_fixo;
  v_com_margem := v_custo * (1 + privado.cfg('margem') / 100);
  v_preco      := v_com_margem / (1 - privado.cfg('tributos') / 100);
  v_calculado  := round(v_preco, 2);
  v_final      := greatest(v_calculado, v_minimo);

  return jsonb_build_object(
    'area_placa',      round(v_area_placa, 2),
    'area_total',      round(v_area, 2),
    'sal_ouro_g',      round(v_sal_ouro, 5),
    'itens',           (select coalesce(jsonb_agg(i order by (i ->> 'ordem')::int), '[]'::jsonb)
                          from jsonb_array_elements(v_itens) i),
    'quimicos',        round(v_quim, 2),
    'area_bruta',      round(v_area_bruta, 2),
    'paineis',         v_paineis,
    'horas',           v_horas,
    'mao_de_obra',     round(v_mo, 2),
    'custo_fixo',      round(v_fixo, 2),
    'custo',           round(v_custo, 2),
    'margem_valor',    round(v_com_margem - v_custo, 2),
    'tributos_valor',  round(v_preco - v_com_margem, 2),
    'valor_calculado', v_calculado,
    'valor_final',     v_final,
    'valor_unitario',  round(v_final / p_quantidade, 2),
    'minimo_aplicado', v_final > v_calculado
  );
end;
$$;

revoke all on all functions in schema privado from public, anon, authenticated;

-- ---------------------------------------------------------------------
-- 3. Funções públicas
-- ---------------------------------------------------------------------

-- 3.1 Dados públicos do formulário: disponibilidade e limites da camada.
--     (Não revela custos.)
create or replace function public.dados_formulario()
returns jsonb language sql stable security definer set search_path = ''
as $$
  select jsonb_build_object(
    'disponivel',    exists (select 1 from privado.quimicos) and privado.cfg('margem') is not null,
    'camada_min',    privado.cfg('camada_min'),
    'camada_padrao', privado.cfg('camada_padrao'),
    'camada_max',    privado.cfg('camada_max'));
$$;

-- Compatibilidade com a versão 1.x da página
create or replace function public.servico_disponivel()
returns boolean language sql stable security definer set search_path = ''
as $$
  select (public.dados_formulario() ->> 'disponivel')::boolean;
$$;

-- 3.2 Cálculo do orçamento (público, com limite de consultas)
create or replace function public.calcular_orcamento(
  p_empresa text, p_referencia text,
  p_largura numeric, p_comprimento numeric, p_quantidade integer, p_sfa numeric, p_camada numeric)
returns jsonb language plpgsql volatile security definer set search_path = ''
as $$
declare
  v_bloqueio   text;
  v_erro       text;
  v_empresa    text := privado.normalizar_texto(p_empresa);
  v_referencia text := privado.normalizar_referencia(p_referencia);
  v_l numeric; v_c numeric; v_s numeric; v_k numeric;
  v_r          jsonb;
  v_agora      timestamp;
  v_emitido    text;
  v_base       text;
begin
  v_bloqueio := privado.consumir_limite();
  if v_bloqueio is not null then
    return jsonb_build_object('ok', false, 'codigo', 'limite', 'erro', v_bloqueio);
  end if;

  if not coalesce((public.dados_formulario() ->> 'disponivel')::boolean, false) then
    return jsonb_build_object('ok', false, 'codigo', 'indisponivel',
      'erro', 'O serviço de orçamento ainda não está disponível. Entre em contato com a HJK pelo WhatsApp.');
  end if;

  if v_empresa = '' then
    return jsonb_build_object('ok', false, 'codigo', 'entrada', 'erro', 'Informe o nome da empresa.');
  end if;
  if char_length(v_empresa) > 120 or char_length(v_referencia) > 60 then
    return jsonb_build_object('ok', false, 'codigo', 'entrada',
      'erro', 'Nome da empresa (até 120 caracteres) ou referência (até 60) muito longos.');
  end if;
  v_erro := privado.validar_entrada(p_largura, p_comprimento, p_quantidade, p_sfa, p_camada);
  if v_erro is not null then
    return jsonb_build_object('ok', false, 'codigo', 'entrada', 'erro', v_erro);
  end if;

  v_l := round(p_largura, 2); v_c := round(p_comprimento, 2);
  v_s := round(p_sfa, 2);     v_k := round(p_camada, 3);
  v_r := privado.calcular(v_l, v_c, p_quantidade, v_s, v_k);

  v_agora   := now() at time zone 'America/Sao_Paulo';
  v_emitido := to_char(v_agora, 'DD/MM/YYYY HH24:MI');
  v_base    := 'HJK-' || to_char(v_agora, 'YYMMDD') || '-'
               || upper(encode(extensions.gen_random_bytes(2), 'hex'));

  -- Somente o necessário para o cliente (sem composição de custos)
  return jsonb_build_object(
    'ok',              true,
    'id',              v_base || '-' || privado.codigo_verificacao(v_base, v_emitido, v_empresa, v_referencia,
                          v_l, v_c, p_quantidade, v_s, v_k, (v_r ->> 'valor_final')::numeric),
    'emitido_em',      v_emitido,
    'empresa',         v_empresa,
    'referencia',      v_referencia,
    'largura',         v_l,
    'comprimento',     v_c,
    'quantidade',      p_quantidade,
    'sfa',             v_s,
    'camada',          v_k,
    'area_placa',      v_r -> 'area_placa',
    'area_total',      v_r -> 'area_total',
    'valor_calculado', v_r -> 'valor_calculado',
    'valor_final',     v_r -> 'valor_final',
    'valor_unitario',  v_r -> 'valor_unitario',
    'minimo_aplicado', v_r -> 'minimo_aplicado');
end;
$$;

-- 3.3 O usuário logado é administrador?
create or replace function public.sou_administrador()
returns boolean language sql stable security definer set search_path = ''
as $$
  select privado.eh_admin();
$$;

-- 3.4 Configuração completa (somente administrador)
create or replace function public.obter_configuracao()
returns jsonb language plpgsql stable security definer set search_path = ''
as $$
begin
  if not privado.eh_admin() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  return jsonb_build_object(
    'parametros', (select jsonb_agg(jsonb_build_object(
                     'chave', c.chave, 'grupo', c.grupo, 'rotulo', c.rotulo, 'unidade', c.unidade,
                     'valor', c.valor, 'minimo', c.minimo, 'maximo', c.maximo, 'casas', c.casas,
                     'ajuda', c.ajuda) order by c.grupo, c.ordem) from privado.config c),
    'quimicos',   (select jsonb_agg(jsonb_build_object(
                     'codigo', q.codigo, 'nome', q.nome, 'unidade', q.unidade, 'tipo', q.tipo,
                     'preco', q.preco, 'consumo', q.consumo, 'base', q.base,
                     'referencia', q.referencia, 'percentual', q.percentual) order by q.ordem)
                   from privado.quimicos q),
    'atualizado_em', (select to_char(max(t) at time zone 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI')
                      from (select max(atualizado_em) t from privado.config
                            union all select max(atualizado_em) from privado.quimicos) x));
end;
$$;

-- 3.5 Salvar configuração (somente administrador). Tudo ou nada.
--     p_parametros: {"chave": valor, ...}
--     p_quimicos:   [{"codigo":..., "preco":..., "consumo":..., "base":..., "percentual":...}, ...]
create or replace function public.salvar_configuracao(p_parametros jsonb, p_quimicos jsonb)
returns jsonb language plpgsql volatile security definer set search_path = ''
as $$
declare
  k      text;
  v      numeric;
  c      privado.config%rowtype;
  q      jsonb;
  qr     privado.quimicos%rowtype;
  v_min  numeric; v_pad numeric; v_max numeric;
begin
  if not privado.eh_admin() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;

  -- Parâmetros gerais
  for k in select jsonb_object_keys(coalesce(p_parametros, '{}'::jsonb)) loop
    select * into c from privado.config where chave = k;
    if not found then
      raise exception 'Parâmetro desconhecido: %', k using errcode = '22023';
    end if;
    begin
      v := (p_parametros ->> k)::numeric;
    exception when others then
      raise exception '"%": valor inválido.', c.rotulo using errcode = '22023';
    end;
    if v is null or v < c.minimo or v > c.maximo then
      raise exception '"%": informe um valor entre % e %.', c.rotulo, c.minimo, c.maximo using errcode = '22023';
    end if;
    if round(v, c.casas) <> v then
      raise exception '"%": use no máximo % casas decimais.', c.rotulo, c.casas using errcode = '22023';
    end if;
    update privado.config set valor = v, atualizado_em = now(), atualizado_por = auth.uid()
     where chave = k and valor is distinct from v;
  end loop;

  -- Químicos
  for q in select * from jsonb_array_elements(coalesce(p_quimicos, '[]'::jsonb)) loop
    select * into qr from privado.quimicos where codigo = q ->> 'codigo';
    if not found then
      raise exception 'Material desconhecido: %', q ->> 'codigo' using errcode = '22023';
    end if;
    begin
      if q ? 'preco'      then qr.preco      := (q ->> 'preco')::numeric; end if;
      if q ? 'consumo'    then qr.consumo    := (q ->> 'consumo')::numeric; end if;
      if q ? 'percentual' then qr.percentual := (q ->> 'percentual')::numeric; end if;
      if q ? 'base'       then qr.base       := q ->> 'base'; end if;
    exception when others then
      raise exception '"%": valor inválido.', qr.nome using errcode = '22023';
    end;
    if qr.preco is null or qr.preco < 0 or qr.preco > 1000000 or round(qr.preco, 4) <> qr.preco then
      raise exception '"%": preço deve estar entre 0 e 1.000.000, com até 4 casas.', qr.nome using errcode = '22023';
    end if;
    if qr.consumo is null or qr.consumo < 0 or qr.consumo > 10000 or round(qr.consumo, 6) <> qr.consumo then
      raise exception '"%": consumo deve estar entre 0 e 10.000, com até 6 casas.', qr.nome using errcode = '22023';
    end if;
    if qr.percentual is null or qr.percentual < 0 or qr.percentual > 10000 or round(qr.percentual, 4) <> qr.percentual then
      raise exception '"%": percentual inválido.', qr.nome using errcode = '22023';
    end if;
    if qr.base is null or qr.base not in ('ouro', 'area') then
      raise exception '"%": escolha "ouro" ou "área".', qr.nome using errcode = '22023';
    end if;
    update privado.quimicos
       set preco = qr.preco, consumo = qr.consumo, percentual = qr.percentual, base = qr.base,
           atualizado_em = now(), atualizado_por = auth.uid()
     where codigo = qr.codigo
       and (preco, consumo, percentual, base) is distinct from (qr.preco, qr.consumo, qr.percentual, qr.base);
  end loop;

  -- Coerência da camada
  v_min := privado.cfg('camada_min'); v_pad := privado.cfg('camada_padrao'); v_max := privado.cfg('camada_max');
  if not (v_min <= v_pad and v_pad <= v_max) then
    raise exception 'A camada padrão deve ficar entre a mínima e a máxima.' using errcode = '22023';
  end if;
  if privado.cfg('tributos') >= 100 then
    raise exception 'Tributos devem ser menores que 100%%.' using errcode = '22023';
  end if;

  return public.obter_configuracao();
end;
$$;

-- 3.6 Simulador com composição completa (somente administrador; sem limite de consultas)
create or replace function public.simular_orcamento(
  p_largura numeric, p_comprimento numeric, p_quantidade integer, p_sfa numeric, p_camada numeric)
returns jsonb language plpgsql stable security definer set search_path = ''
as $$
declare
  v_erro text;
begin
  if not privado.eh_admin() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  if p_largura is null or p_comprimento is null or p_quantidade is null or p_sfa is null or p_camada is null
     or p_largura <= 0 or p_comprimento <= 0 or p_quantidade < 1 or p_sfa <= 0 or p_camada <= 0
     or p_largura > 5000 or p_comprimento > 5000 or p_quantidade > 10000000 or p_sfa > 200 or p_camada > 5 then
    return jsonb_build_object('ok', false, 'erro', 'Preencha a simulação com valores válidos.');
  end if;
  -- O simulador aceita camadas fora da faixa do cliente, mas avisa.
  v_erro := privado.validar_entrada(p_largura, p_comprimento, p_quantidade, p_sfa, p_camada);
  return privado.calcular(round(p_largura, 2), round(p_comprimento, 2), p_quantidade, round(p_sfa, 2), round(p_camada, 3))
         || jsonb_build_object('ok', true, 'aviso', v_erro);
end;
$$;

-- 3.7 Conferir um orçamento recebido (somente administrador)
create or replace function public.verificar_orcamento(
  p_id text, p_emitido_em text, p_empresa text, p_referencia text,
  p_largura numeric, p_comprimento numeric, p_quantidade integer,
  p_sfa numeric, p_camada numeric, p_valor numeric)
returns jsonb language plpgsql stable security definer set search_path = ''
as $$
declare
  v_id       text := upper(btrim(coalesce(p_id, '')));
  v_emitido  text := btrim(coalesce(p_emitido_em, ''));
  v_partes   text[];
  v_base     text;
  v_valido   boolean;
  v_atual    jsonb;
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
     or p_quantidade is null or p_sfa is null or p_camada is null or p_valor is null or p_quantidade < 1
     or p_largura <= 0 or p_comprimento <= 0 or p_sfa <= 0 or p_camada <= 0 then
    return jsonb_build_object('valido', false, 'motivo', 'Preencha todos os dados do orçamento.');
  end if;

  v_base := 'HJK-' || v_partes[1] || '-' || v_partes[2];
  v_valido := privado.codigo_verificacao(v_base, v_emitido, p_empresa, p_referencia,
                p_largura, p_comprimento, p_quantidade, p_sfa, p_camada, p_valor) = v_partes[3];
  v_atual := privado.calcular(round(p_largura, 2), round(p_comprimento, 2), p_quantidade,
                              round(p_sfa, 2), round(p_camada, 3));

  return jsonb_build_object(
    'valido',          v_valido,
    'motivo',          case when v_valido
                            then 'Orçamento autêntico: todos os dados (empresa, referência, data, medidas, quantidade, percentual, camada e valor) conferem com o emitido pelo sistema.'
                            else 'Algum dado NÃO confere com o código de verificação (empresa, referência, data/hora, medidas, quantidade, percentual, camada ou valor). O orçamento pode ter sido alterado, digitado incorretamente ou emitido antes da versão 2.0.'
                       end,
    'emitido_em',      v_emitido,
    'area_total',      v_atual -> 'area_total',
    'valor_informado', round(p_valor, 2),
    'valor_com_precos_atuais', v_atual -> 'valor_final');
end;
$$;

-- ---------------------------------------------------------------------
-- 4. Permissões
-- ---------------------------------------------------------------------
revoke all on function public.dados_formulario()   from public, anon, authenticated;
revoke all on function public.servico_disponivel() from public, anon, authenticated;
revoke all on function public.calcular_orcamento(text, text, numeric, numeric, integer, numeric, numeric) from public, anon, authenticated;
revoke all on function public.sou_administrador()  from public, anon, authenticated;
revoke all on function public.obter_configuracao() from public, anon, authenticated;
revoke all on function public.salvar_configuracao(jsonb, jsonb) from public, anon, authenticated;
revoke all on function public.simular_orcamento(numeric, numeric, integer, numeric, numeric) from public, anon, authenticated;
revoke all on function public.verificar_orcamento(text, text, text, text, numeric, numeric, integer, numeric, numeric, numeric) from public, anon, authenticated;

grant execute on function public.dados_formulario()   to anon, authenticated;
grant execute on function public.servico_disponivel() to anon, authenticated;
grant execute on function public.calcular_orcamento(text, text, numeric, numeric, integer, numeric, numeric) to anon, authenticated;
grant execute on function public.sou_administrador()  to authenticated;
grant execute on function public.obter_configuracao() to authenticated;
grant execute on function public.salvar_configuracao(jsonb, jsonb) to authenticated;
grant execute on function public.simular_orcamento(numeric, numeric, integer, numeric, numeric) to authenticated;
grant execute on function public.verificar_orcamento(text, text, text, text, numeric, numeric, integer, numeric, numeric, numeric) to authenticated;

-- Conferência do diagnóstico de identificação do visitante (executar à parte):
--   select * from privado.diagnostico;

-- Fim da instalação.
