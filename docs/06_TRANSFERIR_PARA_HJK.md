# 6. Transferir o aplicativo para a HJK

O aplicativo foi montado para ser transferido sem reprogramação.

## 6.1 GitHub (páginas)

**Opção A: transferir o repositório (mantém o histórico)**
1. A HJK cria uma conta ou organização no GitHub, por exemplo `hjk-galvanoplastia`.
2. Na conta do Gilmar: repositório → **Settings** → **General** → **Danger Zone** → **Transfer ownership**
   → informe a conta da HJK.
3. Na conta da HJK, reative o **Settings → Pages** (manual 3, passo 3.3).
4. O endereço muda para `https://hjk-galvanoplastia.github.io/hjk-orcamentos-enig/`. O GitHub
   redireciona o repositório, mas **não** o site; avise os clientes ou use um domínio próprio.

**Opção B: novo repositório** — a HJK envia os mesmos arquivos para um repositório dela.

Com um **domínio próprio** (ex.: `orcamento.hjk.com.br`), o endereço não muda nas transferências futuras.

## 6.2 Supabase (banco e login)

**Opção A: convidar e transferir**
1. Organização do Supabase → **Team** → convidar o e-mail da HJK como **Owner**.
2. Depois que a HJK aceitar, o Gilmar pode sair da organização.
   Nada muda no site, no endereço ou nas chaves.

**Opção B: projeto novo na conta da HJK**
1. Siga o manual 1 na conta da HJK e o manual 2 para recriar o acesso do Josias.
2. Atualize `js/config.js` com o novo endereço e a nova chave pública.
3. O Josias cadastra os preços de novo.
4. Orçamentos emitidos no projeto antigo **não** são verificáveis no novo, porque cada projeto gera
   sua própria chave de verificação. Faça a troca num momento sem orçamentos pendentes.

## 6.3 Checklist final

- [ ] HJK é dona do repositório e do projeto Supabase
- [ ] Senha do banco do Supabase guardada pela HJK
- [ ] Josias acessa a administração normalmente
- [ ] Gilmar removido dos acessos, se desejado
