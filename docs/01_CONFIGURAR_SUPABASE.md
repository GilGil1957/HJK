# 1. Configurar o Supabase (gratuito)

Tempo estimado: 15 minutos. Não precisa de cartão de crédito.

> Os nomes dos menus do Supabase mudam de vez em quando. Se algum não bater exatamente,
> procure o equivalente com o mesmo nome em inglês, indicado entre parênteses.

## 1.1 Criar a conta e o projeto

1. Acesse **https://supabase.com** → **Start your project** e entre com a conta GitHub do Gilmar
   (ou com um e-mail; para transferir depois, um e-mail da HJK é melhor).
2. Crie uma organização, por exemplo `HJK Galvanoplastia`, no plano **Free**.
3. **New project**:
   - Nome: `hjk-orcamentos-enig`
   - Database password: gere uma senha forte e **guarde num lugar seguro**. Ela não vai no site.
   - Região: **South America (São Paulo)**.
4. Aguarde 1 a 2 minutos até o projeto ficar pronto.

## 1.2 Instalar o banco de dados

1. No menu lateral, abra **SQL Editor** → **New query**.
2. Abra o arquivo `supabase/01_instalacao.sql`, copie **todo** o conteúdo, cole no editor e clique em **Run**.
3. A mensagem deve ser "Success. No rows returned".

O script pode ser executado de novo (para uma atualização, por exemplo) sem apagar os preços.

## 1.3 Desativar o cadastro público

Isso impede que qualquer pessoa crie uma conta no projeto.

1. **Authentication** → **Sign In / Providers** (ou **Providers** → **Email**).
2. **Desative** "Allow new users to sign up".
3. Deixe o provedor **Email** ativado, porque é por ele que o Josias entra.

## 1.4 Copiar o endereço e a chave pública

1. **Project Settings** → **API Keys** (ou **Data API**).
2. Copie:
   - **Project URL**, por exemplo `https://abcdxyz.supabase.co`
   - **Publishable key** (`sb_publishable_...`). Em projetos antigos, use a **anon public** (começa com `eyJ...`).
3. **Nunca copie a chave "secret" ou "service_role".** Ela dá acesso total ao banco.

## 1.5 Preencher o arquivo `js/config.js`

```js
window.HJK_CONFIG = {
  SUPABASE_URL: "https://abcdxyz.supabase.co",
  SUPABASE_CHAVE_PUBLICA: "sb_publishable_xxxxxxxxxxxxxxxx",
  WHATSAPP_NUMERO: "5511971651268"
};
```

A chave pública pode ficar no site e no GitHub. Ela só dá acesso às funções liberadas pelo script.
Os preços continuam protegidos.

## 1.6 Próximo passo

Crie o acesso do Josias: [02_ACESSO_DO_JOSIAS.md](02_ACESSO_DO_JOSIAS.md).
Enquanto ele não cadastrar os preços, a página do cliente mostra "serviço ainda não disponível".
