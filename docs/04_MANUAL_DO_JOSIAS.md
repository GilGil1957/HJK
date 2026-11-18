# Manual do Josias — Administração dos Orçamentos ENIG (versão 2.0)

Endereço: **https://gilgil1957.github.io/HJK/admin.html**

## Entrar, sair e senha

- Digite o **e-mail** e a **senha** e toque em **Entrar**. Fechar o navegador encerra o acesso.
- **Alterar senha:** depois de entrar, toque em **Alterar senha**, digite a nova senha duas vezes (mínimo 10 caracteres)
  e toque em **Salvar nova senha**.
- **Esqueci minha senha:** na tela de entrada, toque em **Esqueci minha senha**, informe o e-mail e toque em
  **Enviar link**. Abra o e-mail recebido, toque no link e crie a senha nova. O link vale por tempo limitado.
  *(Requer o envio de e-mails configurado no Supabase — ver manual 01, item 1.7.)*
- Se o navegador oferecer para **preencher a senha automaticamente**, confira se é a senha certa.

## Como o preço é calculado

1. **Área ENIG** = largura × comprimento × quantidade × Surface Finish Area ÷ 10.000 (cm²).
2. **Sal de ouro (g)** = área × camada ÷ 10.000 × densidade × fator ouro→sal.
3. **Químicos** = preço × consumo × sal de ouro, para cada material.
   - “**Acompanha o ouro**”: usa a camada pedida pelo cliente (normalmente só o aurocianeto).
   - “**Acompanha a área**”: usa a camada de referência — muda só com a área.
   - **Água** e **Energia**: percentual do custo da Parte A.
4. **Painéis** = área bruta das placas ÷ área do painel padrão, arredondado para cima.
5. **Horas** = painéis ÷ painéis por hora + horas adicionais, arredondado para cima. **Mão de obra** = horas × valor da hora.
6. **Custo** = químicos + mão de obra + custo fixo.
7. **Preço** = custo × (1 + margem) ÷ (1 − tributos). Tirando os tributos do preço, sobra o custo com a margem.
8. **Valor final** = o maior entre o preço e o valor mínimo por pedido (0 = sem mínimo).

## Alterar preços e parâmetros

No quadro **Preços e parâmetros**:

| Grupo | O que tem |
|---|---|
| Materiais e químicos | Preço, consumo (por grama de sal de ouro) e “acompanha o ouro / a área” de cada material; % da Parte A para Água e Energia |
| Produção e mão de obra | Valor da hora, painéis por hora, horas adicionais, tamanho do painel padrão, custo fixo |
| Comercial | Margem sobre o custo, tributos, valor mínimo por pedido |
| Camada de ouro | Mínima, padrão (já preenchida para o cliente) e máxima aceitas |
| Fatores técnicos | Densidade do ouro, fator ouro→sal, camada de referência |

1. Altere os campos desejados (vírgula ou ponto; **não use ponto de milhar**: escreva 1500, não 1.500).
2. Toque em **Salvar alterações**. A mensagem verde informa quantos itens mudaram.
3. Se algum valor estiver fora do permitido, **nada é salvo** e a mensagem explica o motivo.
4. **Desfazer** descarta o que ainda não foi salvo.

As alterações valem **na hora** para os próximos orçamentos. Orçamentos já enviados continuam válidos.

> Os valores iniciais do sistema são **fictícios**. Antes de liberar aos clientes, digite os valores reais da planilha.

## Simulador

No quadro **Simulador de orçamento**, informe uma placa e toque em **Simular**. Aparece a composição completa:
cada químico, mão de obra (painéis e horas), custo fixo, custo total, margem, tributos e valor final — igual à
planilha. Use para conferir os valores depois de alterar preços. O simulador aceita camadas fora da faixa do
cliente, mas avisa.

## Conferir um orçamento recebido (WhatsApp ou e-mail)

O número do orçamento (ex.: **HJK-261118-7B44-98F53289EC**) traz a data e um código de verificação que cobre
**todos** os dados: empresa, referência, data e hora, medidas, quantidade, percentual, **camada de ouro** e valor.

1. Copie a mensagem inteira do cliente (WhatsApp ou e-mail).
2. Cole em **Mensagem recebida** e toque em **Ler mensagem**.
3. Toque em **Verificar**:
   - ✔ **Autêntico** — exatamente o que o sistema calculou.
   - ✖ **Não confere** — algo foi alterado ou digitado errado; confira com o cliente.

Também aparece o **valor com os preços atuais**. Orçamentos emitidos antes da versão 2.0 não conferem
(o código mudou).

> O pedido só está recebido quando a mensagem do cliente chega de fato. Abrir o WhatsApp ou o e-mail não basta.

## Dúvidas comuns

- **A página diz que não foi possível conectar:** o Supabase gratuito pausa após 7 dias sem acesso. Peça ao Gilmar
  para reativar (Supabase → projeto → Restore).
- **Cliente diz que a página pediu para aguardar:** limite de 10 consultas por minuto por pessoa contra robôs.
- **Cliente não consegue abrir o e-mail pelo botão:** o botão usa o programa de e-mail do aparelho dele. A página
  mostra o endereço da HJK para envio manual com o número do orçamento.
