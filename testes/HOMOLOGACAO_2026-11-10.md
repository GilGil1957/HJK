# Homologação no ambiente real — 10/11/2026

**Endereços de teste** (não divulgar aos clientes nesta fase)
- Cliente: https://gilgil1957.github.io/HJK/
- Administração: https://gilgil1957.github.io/HJK/admin.html
- Repositório: https://github.com/GilGil1957/HJK
- Supabase: projeto "HJK Enig" (organização "HJK Galvanoplastia", plano Free, US$ 0)

Preços **fictícios** cadastrados: R$ 0,05 por cm² e mínimo de R$ 150,00.

## Resultados

| # | Teste | Resultado |
|---|---|---|
| R1 | Página sem preços cadastrados | ✅ aviso "serviço ainda não disponível", cálculo bloqueado |
| R2/R7-auth | Cadastro público de usuários | ✅ recusado pelo Supabase ("signup_disabled") |
| R3 | Login do administrador e cadastro dos preços | ✅ "Preços salvos: R$ 0,05 por cm² e mínimo de R$ 150,00" |
| R4 | Preços persistem em novo acesso | ✅ recarregando a administração, os valores continuam salvos |
| R5 | 100 × 100 mm, qtd 1, SFA 75,38% | ✅ 75,38 cm²; calculado R$ 3,77 → **R$ 150,00** (mínimo) |
| R6 | Mesma placa, qtd 100 | ✅ 7.538,00 cm²; **R$ 376,90**; mensagem do WhatsApp idêntica à tela |
| R7 | WhatsApp no celular | ⏳ envio real a cargo do Gilmar (ver abaixo) |
| R8 | Conferência na administração | ✅ mensagem colada → "autêntico"; empresa ou valor alterados → "não confere" |
| R9 | 11 consultas em menos de 1 minuto, com `x-forwarded-for` falsificado a cada vez | ✅ 1ª–10ª ok, 11ª e 12ª bloqueadas |
| **R10** | `select * from privado.diagnostico` | ✅ `cf_connecting_ip = true` → **"cf-connecting-ip (por visitante)"** |
| R11 | Outro aparelho logo após o bloqueio | ⏳ a cargo do Gilmar (celular em rede móvel) |
| R12 | Leitura direta dos preços pela API pública | ✅ tabela inexistente para a API; esquema `privado` não exposto; funções de admin "permission denied" para anônimo |
| — | Tela de celular (375 px) | ✅ sem rolagem horizontal; 80,5 × 120 mm, qtd 250, SFA 132,4% → 31.974,60 cm², R$ 1.598,73 (conferido) |
| — | Computador | ✅ logo, formulário, resultado e administração |

## Configuração aplicada

- Repositório `GilGil1957/HJK` (público), GitHub Pages na branch `main`, pasta raiz.
- App Claude no GitHub com acesso só a `HJK` e `brasil-em-numeros` (nenhum repositório da Micropress).
- Supabase: script `01_instalacao.sql` v1.1 executado; "Allow new users to sign up" **desativado**; administrador
  provisório: gilmar@egga.com.br.
- `js/config.js`: URL do projeto e chave **publicável** (pública por definição; nenhuma chave secreta no repositório).
- Capa do repositório (social preview) com o logo da HJK.

## Pendências antes da liberação comercial

1. R7 e R11 no celular do Gilmar.
2. Criar o usuário do Josias e torná-lo administrador (manual 02).
3. Trocar os preços fictícios pelos reais, definidos pelo Josias.
4. Decisão do Josias sobre validade, impostos e frete no texto do orçamento.
5. Migrar a hospedagem para Cloudflare Pages antes de divulgar aos clientes (termos do GitHub Pages; manual 08).
6. Lembrar que o Supabase Free pausa após 7 dias sem acesso (manual 05).
