# Manual do Josias — Administração dos Orçamentos ENIG

## Entrar

1. Abra o endereço da administração (termina em `/admin.html`) no computador ou no celular.
2. Digite seu **e-mail** e sua **senha** e toque em **Entrar**.
3. Para sair, toque em **Sair**. Fechar o navegador também encerra o acesso.

## Alterar os preços

No quadro **Preços** aparecem os valores em uso:

- **Preço por cm² de ENIG (R$)**: por exemplo `0,05`. Aceita até 6 casas decimais (`0,0485`).
- **Valor mínimo por pedido (R$)**: por exemplo `150,00`. É cobrado uma única vez no pedido inteiro,
  quando o valor calculado for menor que ele.

Para mudar:

1. Preencha **os dois campos**, "Novo preço por cm²" e "Novo valor mínimo". Pode usar vírgula ou ponto.
2. Toque em **Salvar preços**.
3. A mensagem verde confirma, e o quadro passa a mostrar os novos valores e a data da alteração.

A mudança vale **imediatamente** para os próximos orçamentos. Os orçamentos já enviados continuam
válidos com o valor original.

Enquanto os preços não forem cadastrados pela primeira vez, os clientes veem
"serviço ainda não disponível" e não conseguem gerar orçamentos.

## Conferir um orçamento recebido pelo WhatsApp

Todo orçamento traz um número como **HJK-261110-7B44-98F53289EC**:

- `261110` é a data de emissão (ano 26, mês 11, dia 10).
- Os últimos 10 caracteres são um **código de verificação** calculado pelo servidor.

O código cobre **todos** os dados da mensagem: empresa, referência da placa, data e hora de emissão,
medidas, quantidade, percentual e valor. Se qualquer um deles for alterado, o código deixa de conferir.

Para conferir:

1. No WhatsApp, copie a mensagem inteira do cliente.
2. Na administração, em **Conferir orçamento recebido**, cole no campo "Mensagem do WhatsApp".
3. Toque em **Ler mensagem**. Os campos (número, data e hora, empresa, referência, medidas, quantidade,
   percentual e valor) são preenchidos sozinhos. Se precisar digitar à mão, copie exatamente como está
   na mensagem. Se a referência aparecer como "não informada", deixe o campo vazio.
4. Toque em **Verificar**.

Resultados:

- ✔ **Orçamento autêntico**: os dados e o valor são exatamente os calculados pelo sistema.
- ✖ **Orçamento não confere**: algo foi alterado ou digitado errado. Confira com o cliente.

O resultado também mostra o **valor com os preços atuais**, útil quando os preços mudaram
depois que o cliente fez o orçamento.

> O pedido só deve ser considerado recebido quando a mensagem do cliente chega de fato no WhatsApp.
> O cliente pode abrir o WhatsApp e desistir de enviar.

## Dúvidas comuns

**Esqueci a senha.** Peça ao Gilmar para redefinir no painel do Supabase.

**A página diz que não foi possível conectar.** No plano gratuito, o servidor entra em pausa depois de
7 dias sem nenhum acesso. Peça ao Gilmar para reativar (Supabase → projeto → **Restore**). Leva poucos
minutos e nenhum dado se perde.

**Um cliente diz que a página pediu para aguardar.** Existe um limite de consultas seguidas para impedir
robôs: 10 por minuto por pessoa e 120 por minuto no site todo. Basta esperar um ou dois minutos.
