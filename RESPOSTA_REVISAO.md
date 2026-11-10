# Resposta à revisão técnica do Fernando — versão 1.1 (10/11/2026)

Obrigado pela revisão. Os pontos foram tratados como descrito abaixo. A revisão original está em
`REVISAO_FERNANDO.md`.

| # | Ponto da revisão | Situação na v1.1 |
|---|---|---|
| — | Logo original recortado | **Incorporado.** O cabeçalho foi ajustado: marca centralizada e fundo no tom das bordas da imagem. |
| — | Condição de corrida no cliente | **Corrigido de forma completa.** Na revisão, o contador só avançava quando já havia resultado na tela, então uma alteração *durante* o cálculo não invalidava a resposta. Agora qualquer digitação invalida. Há um teste automatizado que falha com a versão anterior e passa com a nova. |
| 1 | **CRÍTICO** — cabeçalhos de IP | **Corrigido.** O `x-forwarded-for` (que o cliente consegue forjar) e o `x-real-ip` deixaram de ser usados. A identificação é feita só pelo `cf-connecting-ip`, que a Cloudflare na frente do Supabase preenche e sobrescreve. Sem ele, todos compartilham um contador único (falha segura). Foi incluído um **limite global por minuto** (120) que não depende de cabeçalho, além do diário (3.000). A tabela `privado.diagnostico` mostra, sem guardar IPs, se a identificação funciona no Supabase real (roteiro R10). A validação final no ambiente real continua obrigatória. |
| 2 | Assinatura parcial | **Corrigido.** O código cobre empresa, referência, data e hora completas, medidas, quantidade, percentual e valor. O servidor normaliza empresa e referência e devolve o texto que vai para a mensagem. A conferência no admin ganhou os campos correspondentes, preenchidos automaticamente pela mensagem colada. |
| 3 | Código curto (24 bits) | **Corrigido.** Agora são 10 caracteres hexadecimais (40 bits), com formato `HJK-AAMMDD-XXXX-XXXXXXXXXX`. Como a conferência só é feita pelo administrador logado, não existe tentativa em massa pela internet; os 40 bits deixam a chance de uma alteração "acertar" o código em cerca de 1 em 1 trilhão. |
| 4 | Validação no ambiente real | **Mantido como pendência.** O roteiro de 13 passos está em `testes/RELATORIO_DE_TESTES.md`. Nenhuma publicação foi feita. |
| 5 | Preços inferíveis | **Já documentado** (manual 5, item 4). Os limites de consulta dificultam a coleta automatizada, mas sigilo absoluto não é possível numa calculadora pública, como previsto na missão. |
| 6 | Validade, impostos, frete, texto do WhatsApp | **Depende de decisão comercial do Josias.** O texto "Solicitamos a execução do serviço conforme o orçamento apresentado." foi definido literalmente na missão e não foi alterado. Sugestão para avaliar: incluir na tela e na mensagem uma linha como "Orçamento válido por __ dias, sujeito à confirmação da HJK; [impostos/frete inclusos ou não]". É uma alteração simples assim que o Josias definir o texto. |
| 7 | Termos do GitHub Pages | **Confirmado.** As regras do GitHub Pages proíbem usá-lo como hospedagem gratuita de negócio online ou de site voltado a transações comerciais. Fica o GitHub Pages **só para testes**, e o novo **manual 8** cobre a publicação na **Cloudflare Pages** para uso com clientes, com os mesmos arquivos e sem mudança de código. |

## Arquivos alterados

`supabase/01_instalacao.sql` (atualiza instalações 1.0 sem perder preços) · `js/app.js` · `js/comum.js` ·
`js/admin.js` · `admin.html` · `css/estilo.css` · os três testes ·
`README.md` · manuais 03, 04, 05, 07 e o novo 08 · relatório de testes.

## Parecer do autor

Os pontos técnicos 1, 2 e 3 e a correção de concorrência estão resolvidos e cobertos por testes
automatizados. Para liberar aos clientes, continuam necessários: (a) o roteiro no Supabase real, em
especial o R10; (b) a decisão comercial do item 6; (c) a publicação na Cloudflare Pages, e não no
GitHub Pages.
