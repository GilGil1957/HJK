# Revisão técnica independente — 10/11/2026

## Escopo
Inspeção do pacote recebido, leitura do SQL e JavaScript, execução dos 10 testes Node.js e integração da imagem original da HJK, recortada sem redesenho. Não houve conexão com Supabase real, autenticação real nem teste em celular real. Os demais 38 testes são informados pelo relatório do autor, não reexecutados nesta revisão.

## Ajuste realizado
- Logo original em `assets/logo-hjk.png`, recortado para remover slogan e ícones.
- Corrigida condição de corrida no cliente: se um campo mudar enquanto o cálculo remoto está pendente, a resposta antiga não é mais exibida.

## Pendências antes da publicação
1. **CRÍTICO — limites por visitante:** a função `privado.consumir_limite()` utiliza `cf-connecting-ip`, `x-real-ip` e `x-forwarded-for` de `request.headers`. Validar no Supabase real se esses cabeçalhos são confiáveis e distintos entre usuários. Não confiar em cabeçalhos que o cliente possa forjar; caso não haja identificação segura, usar controle de abuso em camada confiável.
2. **IMPORTANTE — verificação parcial:** o HMAC cobre dimensões, quantidade, percentual e valor, mas NÃO cobre nome da empresa, referência da placa nem data/hora completa. Assim, a mensagem pode ser alterada nesses campos sem invalidar o código. Exibir isso no manual ou ampliar a assinatura para cobri-los.
3. **IMPORTANTE — código curto:** apenas 6 dígitos hexadecimais (24 bits); aumentar o tamanho para reduzir risco de falsificação.
4. **IMPORTANTE — acesso e implantação:** confirmar login Supabase Auth real, RPC e permissões, limites por IP, WhatsApp em celular e responsividade antes de liberar para clientes.
5. **COMERCIAL:** preços são inferíveis por consultas repetidas ao serviço; o código impede leitura direta, não garante sigilo econômico absoluto.
6. **COMERCIAL:** confirmar validade do orçamento, impostos, frete e condições de recebimento com Josias; o texto atual de WhatsApp pode soar como ordem definitiva de execução.
7. **HOSPEDAGEM:** confirmar adequação dos termos do GitHub Pages para a operação comercial; considerar migração antes do uso público.

## Parecer
Bom protótipo, mas NÃO aprovado para produção antes da validação dos pontos acima. Não foram alterados SQL, lógica de autenticação nem preço.
