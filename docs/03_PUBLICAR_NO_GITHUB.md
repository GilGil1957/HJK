# 3. Publicar na conta GitHub do Gilmar (fase de testes)

> **Atenção aos termos do GitHub Pages.** As regras de uso dizem que o Pages não pode servir de hospedagem
> gratuita para um negócio online ou para um site voltado principalmente a transações comerciais.
> Uma calculadora de orçamentos com pedido pelo WhatsApp pode ser enquadrada nisso. Por isso, use o
> GitHub Pages **só na fase de testes**. Para atender clientes de verdade, publique na Cloudflare Pages
> (manual 8), que serve exatamente os mesmos arquivos.

> **Somente após a aprovação do Gilmar.** Este procedimento cria um repositório **novo e independente**
> e não altera nenhum repositório existente da Micropress.

## 3.1 Antes de publicar

- [ ] Supabase configurado e `js/config.js` preenchido (manual 1)
- [ ] Logomarca em `assets/logo-hjk.png` (manual 7)
- [ ] Teste local feito (README → "Testar no próprio computador")
- [ ] Confirmado que `js/config.js` contém só a chave **pública**

## 3.2 Criar o repositório (pelo site, sem instalar nada)

1. Entre em **github.com** com a conta do Gilmar → **+** → **New repository**.
2. Nome: `hjk-orcamentos-enig`. Visibilidade: **Public** (o GitHub Pages gratuito exige repositório público).
   Não marque "Add a README".
3. **Create repository** → clique em **uploading an existing file**.
4. Arraste **o conteúdo** da pasta `hjk-orcamentos-enig` (index.html, admin.html, css, js, assets, supabase, docs).
   A pasta `testes/` é opcional.
5. **Commit changes**.

Opção pela linha de comando:

```
cd hjk-orcamentos-enig
git init && git add . && git commit -m "HJK Orçamentos ENIG — versão inicial"
git branch -M main
git remote add origin https://github.com/<usuario-do-gilmar>/hjk-orcamentos-enig.git
git push -u origin main
```

## 3.3 Ativar o GitHub Pages

1. No repositório: **Settings** → **Pages**.
2. Source: **Deploy from a branch** → Branch: **main** / pasta **/ (root)** → **Save**.
3. Em 1 a 2 minutos o site fica em: `https://<usuario-do-gilmar>.github.io/hjk-orcamentos-enig/`
   - Clientes: esse endereço
   - Josias: o mesmo endereço + `admin.html`

## 3.4 Conferir depois de publicado

Siga o roteiro manual em `testes/RELATORIO_DE_TESTES.md` (seção "Roteiro de teste no ambiente real").

## 3.5 Atualizações futuras

Edite ou envie o arquivo no GitHub (**Add file** → **Upload files**). O site se atualiza em cerca de 1 minuto.
Os preços **não** ficam no GitHub: são alterados pelo Josias na administração.

## O que é público no repositório

Todo o código e a chave pública do Supabase, o que é intencional e seguro.
**Não ficam no repositório:** preços, valor mínimo, senhas, chave secreta do Supabase e a chave interna
dos códigos de verificação, que é gerada dentro do banco.
