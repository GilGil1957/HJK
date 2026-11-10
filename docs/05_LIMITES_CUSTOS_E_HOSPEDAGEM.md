# 5. Limites, custos futuros e alternativa de hospedagem

*Informações verificadas em novembro de 2026. Os fornecedores podem mudar seus planos.*

## 5.1 Custo atual: R$ 0,00 por mês

| Serviço | Plano | Limite que importa aqui | Uso esperado |
|---|---|---|---|
| GitHub Pages (testes) | Gratuito | Repositório público; ~100 GB de tráfego por mês (limite flexível); **não permite uso comercial** (ver 5.4) | Muito baixo |
| Cloudflare Pages (comercial) | Free | Sem limite de tráfego para arquivos estáticos; domínio próprio com HTTPS | Muito baixo |
| Supabase | Free | Banco de 500 MB; 5 GB de tráfego por mês; 2 projetos ativos por organização | Poucos KB |

## 5.2 Limitações conhecidas

1. **Pausa por inatividade (a mais importante).** O Supabase Free **pausa o projeto após 7 dias sem
   acessos**. Os dados não se perdem, mas enquanto ele estiver pausado o site mostra "não foi possível
   conectar". Para reativar: painel do Supabase → projeto → **Restore project** (poucos minutos).
   Por decisão do Gilmar, **não foi implementada** a consulta automática que evitaria a pausa.
   Se ela se mostrar necessária, dá para incluir depois uma tarefa agendada gratuita.
2. **Sem backup automático** no plano gratuito. O impacto é pequeno, porque o banco guarda só os dois
   preços e o usuário do Josias. Recomendação: o Josias anota os preços em vigor.
3. **Sem garantia de disponibilidade (SLA)** nos planos gratuitos.
4. **Sigilo relativo dos preços.** Ninguém consegue ler nem alterar os parâmetros diretamente. Mesmo
   assim, quem fizer orçamentos seguidos consegue **deduzir** o preço por cm² (valor ÷ área) e o
   mínimo (valor de um pedido pequeno). Isso é inerente a qualquer calculadora pública. Os limites de
   consulta dificultam a coleta automatizada, mas não impedem uma dedução manual.
5. **Limites contra robôs:** 10 consultas por minuto e 60 por hora por visitante, mais 120 por minuto e
   3.000 por dia no site todo. Eles podem ser ajustados no início da função `privado.consumir_limite`
   do script SQL, executando o script de novo.
   - O visitante é identificado **só** pelo cabeçalho `cf-connecting-ip`, que a Cloudflare (na frente do
     Supabase) preenche com o IP real e que o cliente não consegue forjar. O `x-forwarded-for` não é usado,
     porque pode ser falsificado pelo cliente.
   - Se o cabeçalho deixar de chegar, todos os visitantes passam a compartilhar um contador único: o sistema
     fica mais restritivo, nunca mais permissivo. A tabela `privado.diagnostico` mostra qual situação está
     valendo (ver roteiro R10 do relatório de testes).
   - Um ataque distribuído (muitos IPs) pode esgotar a cota global e deixar o serviço indisponível por alguns
     minutos ou até o dia seguinte. Os limites globais protegem o banco e os recursos gratuitos, mas não
     impedem esse tipo de bloqueio. Proteção mais forte (desafio anti-robô, como o Cloudflare Turnstile)
     pode ser acrescentada depois, se for necessária.
6. **E-mails do Supabase Auth** (redefinição de senha) têm limite baixo no plano gratuito. Como só
   existe um administrador, isso não afeta o uso normal.

## 5.3 Custos futuros possíveis

| Situação | Opção | Custo aproximado |
|---|---|---|
| Acabar com a pausa e ter backup diário | Supabase **Pro** | a partir de US$ 25 por mês |
| Domínio próprio (ex.: `orcamento.hjk.com.br`) | Registro.br | ~R$ 40 por ano |
| Repositório privado com Pages | GitHub Pro / Team | ~US$ 4 por usuário por mês (não é necessário) |

## 5.4 Hospedagem para a operação comercial definitiva

### Por que não o GitHub Pages

As regras de uso do GitHub dizem que o Pages não pode servir de hospedagem gratuita para um negócio online,
uma loja virtual ou qualquer site voltado principalmente a facilitar transações comerciais. Uma calculadora
de orçamentos que gera pedidos para a HJK pode ser enquadrada nessa restrição. Portanto:

- **Fase de testes:** GitHub Pages, como combinado.
- **Uso com clientes:** **Cloudflare Pages** (manual 8). Ela serve os mesmos arquivos sem nenhuma mudança de
  código, é gratuita, aceita domínio próprio e continua usando o mesmo Supabase. O código pode permanecer no
  repositório do GitHub; muda apenas quem serve o site. Antes de adotar, vale conferir os termos vigentes da
  Cloudflare para uso comercial.

### Se a pausa do Supabase incomodar

Opção sem custo mensal: **Cloudflare Pages + Cloudflare Workers + Cloudflare D1 (plano Free)**

- **Não pausa por inatividade.**
- Permite domínio próprio com HTTPS automático.
- Plano gratuito com 100 mil requisições por dia nos Workers e banco D1 (SQLite) de 5 GB.
- **Esforço de migração:** as páginas seriam reaproveitadas quase sem mudança. O cálculo e a
  verificação (hoje em SQL) seriam reescritos como um Worker em JavaScript, e o login do
  administrador passaria a usar o **Cloudflare Access** (gratuito para até 50 usuários), com acesso
  por código enviado ao e-mail do Josias. Estimativa: 1 a 2 dias de desenvolvimento.

### Outras opções

- **Supabase Pro (a partir de US$ 25 por mês):** a mais simples, sem nenhuma mudança no código. Recomendada se a
  HJK aceitar um custo fixo pequeno em troca de backup e disponibilidade.
- **Hospedagem própria da HJK** (servidor ou VPS a partir de ~R$ 30 por mês): instalar PostgreSQL e
  usar o mesmo script SQL. Exige alguém para cuidar de atualizações e segurança do servidor.
