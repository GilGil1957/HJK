# Histórico de versões

## 2.0 — 18/11/2026
- Novo modelo de preço baseado na planilha REFERENCIAS_ENIG do Josias, com as decisões de 18/11:
  só o aurocianeto acompanha a camada de ouro (demais químicos acompanham a área, configurável por item);
  painéis estimados pela área do painel padrão; horas arredondadas para cima; margem sobre o custo;
  tributos "por dentro"; valor mínimo por pedido opcional.
- Campo **Camada de ouro (µm)** no orçamento: padrão 0,09; mínimo 0,03; máximo 0,10 (IPC-4552A) — editáveis.
- Administração: ~25 parâmetros em grupos, salvamento tudo-ou-nada, **simulador** com composição completa.
- **Esqueci minha senha** (link por e-mail) e **Alterar senha**.
- Confirmação do pedido **por e-mail** (além do WhatsApp), com o mesmo texto e código de verificação.
- Código de verificação passa a cobrir a camada de ouro (orçamentos da 1.x não conferem mais).
- Removidos o "preço por cm²" e as funções da versão 1.x.

## 1.1 — 10/11/2026
- Revisão do Fernando: limites por visitante só pelo `cf-connecting-ip`, limite global por minuto, assinatura
  completa (40 bits), correção de concorrência, logo, termos do GitHub Pages / Cloudflare Pages.

## 1.0 — 10/11/2026
- Versão inicial: preço por cm² + valor mínimo, WhatsApp, verificação, administração com 2 parâmetros.
