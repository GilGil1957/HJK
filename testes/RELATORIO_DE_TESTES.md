# Relatório de testes — HJK Orçamentos ENIG v1.1

Data: 10/11/2026. **Resultado: 55 de 55 testes automatizados aprovados.**

## Como foi testado

| Conjunto | Arquivo | Ambiente | Resultado |
|---|---|---|---|
| Funções do navegador | `testar_funcoes.js` | Node.js 22 | 10/10 |
| Banco de dados e segurança | `testar_banco.py` | PostgreSQL 16 simulando o Supabase (papéis `anon`/`authenticated`, `auth.uid()`) | 30/30 |
| Ponta a ponta no navegador | `testar_navegador.py` | Chromium, computador (1280 px) e celular (390 px), executando as funções SQL reais | 15/15 |

Também foi testada a **atualização de uma instalação 1.0 para a 1.1**: o script novo roda sobre o antigo,
preserva os preços e remove as funções antigas.

Para repetir: `bash testes/executar_testes.sh "<conexão PostgreSQL>"`.

Parâmetros fictícios usados nos testes: **R$ 0,05 por cm²** e **mínimo de R$ 150,00**. Não são preços reais.

## Testes obrigatórios da missão

| # | Teste | Resultado |
|---|---|---|
| 1 | 100 × 100 mm, qtd 1, SFA 75,38% → **75,38 cm²** | ✅ |
| 2 | Mesma placa, qtd 100 → **7.538 cm²** | ✅ |
| 3 | Preço por cm² aplicado: 7.538 × 0,05 = **R$ 376,90** | ✅ |
| 4 | Mínimo aplicado: R$ 3,77 calculado → **R$ 150,00**; mínimo uma vez por pedido | ✅ |
| 5 | Administrador atualiza os parâmetros | ✅ |
| 6 | Parâmetros persistem em nova conexão e em novo navegador | ✅ |
| 7 | Bloqueio de anônimo, de usuário sem permissão e de senha errada | ✅ |
| 8 | Parâmetros não aparecem em respostas públicas; tabelas privadas inacessíveis | ✅ |
| 9 | Campos vazios, negativos, zero, SFA > 200%, NaN e infinito recusados (na tela e no servidor) | ✅ |
| 10 | Mensagem do WhatsApp completa, número oficial, valor idêntico ao da tela | ✅ |
| 11 | Celular (390 px, sem rolagem horizontal) e computador | ✅ |

## Testes acrescentados na v1.1 (revisão do Fernando)

- **Assinatura completa:** a alteração de qualquer campo é detectada (valor, quantidade, SFA, largura,
  empresa, referência, hora, dia ou código).
- **Normalização** de empresa e referência (espaços repetidos, símbolos de formatação do WhatsApp,
  "não informada").
- **Código de 10 caracteres** (40 bits) no formato `HJK-AAMMDD-XXXX-XXXXXXXXXX`.
- **`x-forwarded-for` forjado não burla o limite:** com o mesmo `cf-connecting-ip`, a 11ª consulta é bloqueada
  mesmo trocando o `x-forwarded-for` a cada vez.
- **Sem `cf-connecting-ip`:** todos compartilham um contador único (mais restritivo), e o diagnóstico registra
  a ausência.
- **Limite global por minuto** do site, independente de cabeçalhos.
- **Diagnóstico** registra quais cabeçalhos chegaram, sem guardar o IP.
- **Empresa vazia ou textos longos** recusados também no servidor.
- **Concorrência:** se o cliente altera um campo enquanto o cálculo está em andamento, a resposta atrasada é
  descartada. Este teste **falha** com a correção da revisão (que só invalidava quando já havia resultado na
  tela) e passa com a v1.1.
- **Conferência no navegador:** mensagem colada autêntica; empresa alterada ou valor alterado → "não confere".

## Testes mantidos da v1.0

Serviço bloqueado sem preços · validação dos valores do administrador · decimais com vírgula ou ponto ·
arredondamento de meio centavo · 11ª consulta por minuto bloqueada · IP não armazenado · limite diário ·
orçamento autêntico após mudança de preços · script reexecutável · nenhum erro de JavaScript (com
Content Security Policy ativa).

## Capturas de tela (`testes/capturas/`)

01 serviço indisponível · 02 administração/preços · 03 resultado no computador · 04 validação ·
05 conferência autêntica · 06 conferência alterada · 07–09 celular.

## O que só pode ser testado no ambiente real

1. **Login real** pelo Supabase Auth (testado aqui com um simulador do serviço de login).
2. **Cabeçalho `cf-connecting-ip`** chegando ao banco: verificado pelo roteiro R10 abaixo.
3. **Abertura do WhatsApp** no celular, com o aplicativo instalado.

## Roteiro de teste no ambiente real (cerca de 20 minutos)

Faça depois de configurar o Supabase, primeiro em teste local (`python3 -m http.server`) e depois no
endereço publicado.

| # | Ação | Esperado |
|---|---|---|
| R1 | Abrir a página do cliente antes de cadastrar os preços | Aviso "serviço ainda não disponível", botão desativado |
| R2 | `admin.html` com senha errada | "E-mail ou senha incorretos" |
| R3 | Login do Josias; cadastrar 0,05 e 150,00 | Mensagem verde; quadro atualizado |
| R4 | Fechar o navegador, abrir de novo e entrar | Preços continuam 0,05 e 150,00 |
| R5 | Cliente: 100 × 100, qtd 1, SFA 75,38 | Área 75,38 cm²; R$ 150,00 com aviso de mínimo |
| R6 | Cliente: mesma placa, qtd 100 | Área 7.538,00 cm²; R$ 376,90 |
| R7 | Clicar em "Confirmar pedido pelo WhatsApp" no celular | WhatsApp abre na conversa da HJK com a mensagem preenchida |
| R8 | Copiar a mensagem e conferir na administração | "Orçamento autêntico"; ao mudar empresa ou valor, "não confere" |
| R9 | Clicar em "Calcular" 11 vezes em menos de 1 minuto | Na 11ª: "Muitas consultas em pouco tempo" |
| **R10** | Logo depois de um orçamento, executar no SQL Editor do Supabase: `select * from privado.diagnostico;` | `cf_connecting_ip = true` e `identificacao_usada = 'cf-connecting-ip (por visitante)'` |
| R11 | Logo depois do R9, calcular em outro aparelho (rede de celular, sem Wi-Fi) | Funciona normalmente (confirma a separação por visitante) |
| R12 | No navegador, abrir `https://<projeto>.supabase.co/rest/v1/parametros?apikey=<chave pública>` | Erro (tabela não encontrada); nenhum preço aparece |
| R13 | Cadastrar os preços reais definidos pelo Josias | Pronto para uso |

**Se o R10 mostrar "AUSENTE"**, o sistema continua seguro, mas todos os visitantes passam a dividir o mesmo
limite (10 consultas por minuto no total). Nesse caso, avise o Claudinho para ajustar a identificação antes
de liberar para clientes.
