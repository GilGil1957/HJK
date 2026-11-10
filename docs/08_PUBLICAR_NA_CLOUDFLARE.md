# 8. Publicar na Cloudflare Pages (recomendado para uso comercial)

> **Somente após a aprovação do Gilmar.** O Supabase continua o mesmo: só muda o lugar que serve as páginas.

## Por que

O GitHub Pages não permite sites voltados a transações comerciais (ver manual 5, item 5.4).
A Cloudflare Pages serve os mesmos arquivos, sem mudar nada no código, também gratuitamente e com
domínio próprio e HTTPS.

## 8.1 Criar a conta

1. Acesse **dash.cloudflare.com** e crie uma conta gratuita. Para facilitar a transferência futura,
   o ideal é usar um e-mail da HJK.

## 8.2 Publicar

**Opção A: ligada ao repositório do GitHub (atualiza sozinha a cada alteração)**
1. **Workers & Pages** → **Create** → aba **Pages** → **Connect to Git**.
2. Autorize o GitHub e escolha o repositório `hjk-orcamentos-enig`.
3. Configuração de build: Framework preset **None**, Build command **vazio**, Output directory **`/`**.
4. **Save and Deploy**. O endereço será algo como `https://hjk-orcamentos-enig.pages.dev`.

**Opção B: envio manual (sem GitHub)**
1. **Workers & Pages** → **Create** → aba **Pages** → **Upload assets**.
2. Nome do projeto: `hjk-orcamentos-enig` → arraste a pasta do aplicativo (sem a pasta `testes/`) → **Deploy**.
3. Para atualizar, repita o envio.

> Os nomes dos menus da Cloudflare mudam de vez em quando. Procure sempre por "Pages" e "Upload" ou "Connect to Git".

## 8.3 Domínio próprio (opcional)

No projeto: **Custom domains** → **Set up a custom domain** → por exemplo `orcamento.hjk.com.br`.
Siga as instruções de DNS. Se o domínio estiver no Registro.br, basta criar um registro CNAME apontando
para `hjk-orcamentos-enig.pages.dev`.

## 8.4 Depois de publicar

- Execute o roteiro manual de `testes/RELATORIO_DE_TESTES.md`.
- Se o GitHub Pages tiver sido ativado na fase de testes, desative-o (repositório → Settings → Pages →
  Unpublish) para que exista um único endereço oficial.
