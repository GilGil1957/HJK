# 2. Criar o acesso administrativo do Josias

Feito uma única vez, por Gilmar, no painel do Supabase.

## 2.1 Criar o usuário

1. **Authentication** → **Users** → **Add user** → **Create new user**.
2. Informe o **e-mail do Josias** e uma **senha forte**, com pelo menos 12 caracteres misturando letras, números e símbolos.
3. Marque **Auto Confirm User** e clique em **Create user**.

## 2.2 Torná-lo administrador

1. **SQL Editor** → **New query**.
2. Cole o conteúdo de `supabase/02_cadastrar_josias.sql`.
3. Troque `EMAIL_DO_JOSIAS@exemplo.com.br` pelo e-mail usado no passo anterior e clique em **Run**.
4. O resultado deve listar o e-mail do Josias.

Sem este passo, o usuário até consegue fazer login, mas recebe "sem permissão de administrador".

## 2.3 Entregar ao Josias

- Endereço: `https://<endereço-do-site>/admin.html`
- O e-mail e a senha, de preferência por um canal seguro e não na mesma mensagem que o endereço.
- O manual: [04_MANUAL_DO_JOSIAS.md](04_MANUAL_DO_JOSIAS.md).

## 2.4 Trocar a senha ou bloquear o acesso

- **Trocar a senha:** Authentication → Users → clique no usuário → **Reset password** (envia um e-mail),
  ou exclua e recrie o usuário, repetindo o passo 2.2.
- **Remover um administrador:** use o comando comentado no final de `02_cadastrar_josias.sql`.
- O Supabase já limita tentativas de login seguidas, o que protege contra adivinhação de senha.

## Segurança

- A sessão do administrador termina ao fechar a aba ou o navegador.
- A página `admin.html` é pública, mas sem um usuário administrador ela não mostra nem altera nada.
  A proteção está no servidor, não na página.


## 2.5 Senha esquecida (versão 2.0)

1. **Pelo próprio usuário:** em `admin.html`, **Esqueci minha senha** → e-mail com link → senha nova.
   Requer o SMTP configurado (manual 01, item 1.7).
2. **Logado:** botão **Alterar senha** no painel.
3. **Pelo Gilmar (sem e-mail):** no SQL Editor, execute — digitando a senha nova **no lugar indicado, entre as
   aspas** — e depois apague o comando do editor:

```sql
update auth.users
   set encrypted_password = extensions.crypt('DIGITE_A_SENHA_NOVA_AQUI', extensions.gen_salt('bf')),
       updated_at = now()
 where email = 'hjk@hjk.ind.br';
```
