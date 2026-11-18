# Relatório de testes — HJK Orçamentos ENIG v2.0

Data: 18/11/2026. **Resultado: 51 de 51 testes automatizados aprovados.**

| Conjunto | Arquivo | Ambiente | Resultado |
|---|---|---|---|
| Funções do navegador | `testar_funcoes.js` | Node.js | 11/11 |
| Banco de dados, cálculo e segurança | `testar_banco.py` | PostgreSQL 16 simulando o Supabase | 21/21 |
| Ponta a ponta no navegador | `testar_navegador.py` | Chromium, computador e celular (390 px), funções SQL reais | 19/19 |

Para repetir: `bash testes/executar_testes.sh "<conexão PostgreSQL>"`.

Os testes usam os valores **fictícios** do script. A conferência com os **valores reais da planilha do Josias**
foi feita à parte, fora do repositório (para não publicar a estrutura de custos): com os dados do exemplo da
planilha, o sistema reproduz **item a item** os custos dos químicos da planilha e chega ao valor esperado pelo
modelo aprovado em 18/11 (horas arredondadas para cima, tributos por dentro). Os números ficam fora deste arquivo,
que é público.

## Principais verificações

- **Cálculo** idêntico a uma implementação independente em seis casos diferentes (inclusive limites de camada).
- Só o aurocianeto muda com a camada; os demais químicos ficam iguais (configurável por item).
- Painéis e horas arredondados para cima; tributos por dentro (preço − tributos = custo com margem).
- Valor mínimo por pedido aplicado uma única vez.
- Administração: salvar é **tudo-ou-nada**; valores inválidos são recusados sem alterar nada; persistência.
- Faixa da camada vem do administrador (mín. 0,03 / padrão 0,09 / máx. 0,10, editáveis).
- Resposta pública **sem** composição de custos; tabelas privadas e funções de administração inacessíveis.
- Código de verificação cobre a camada; qualquer alteração é detectada.
- Limites contra robôs mantidos (cabeçalho `x-forwarded-for` forjado não burla).
- WhatsApp e **e-mail** com o mesmo texto e valor; e-mail para hjk@hjk.ind.br com o nº no assunto.
- **Esqueci minha senha**: pedido do link com retorno para a administração; link de recuperação cria a senha
  nova e a senha nova funciona no login; link expirado mostra aviso; **Alterar senha** e cancelar.
- Concorrência (alteração durante o cálculo), validação na tela, celular sem rolagem lateral, nenhum erro de
  JavaScript.
- Atualização a partir da versão 1.1 e reexecução do script sem perder valores.

## A testar no ambiente real (após publicar)

| # | Ação | Esperado |
|---|---|---|
| R1 | Abrir a página do cliente | Camada preenchida com 0,09 e faixa 0,03–0,10 na dica |
| R2 | Orçamento 100 × 100, qtd 100, 75,38%, 0,09 | Mesmo valor no simulador da administração |
| R3 | Confirmar por WhatsApp e por e-mail (celular) | Textos iguais, nº no assunto do e-mail |
| R4 | Administração: alterar margem e salvar | Novo valor vale no orçamento seguinte |
| R5 | Conferir a mensagem recebida | "Autêntico"; ao mudar a camada, "não confere" |
| R6 | Esqueci minha senha (após configurar o SMTP) | E-mail chega; link cria a senha nova |
| R7 | `select * from privado.diagnostico;` | `cf-connecting-ip (por visitante)` |
| R8 | Digitar os valores reais da planilha | Simulador do exemplo da planilha = valor conferido na análise de 18/11 |
