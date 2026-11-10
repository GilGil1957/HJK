-- =====================================================================
--  HJK — Cadastrar o Josias como administrador
--
--  ANTES: crie o usuário do Josias em Authentication → Users → Add user
--         → "Create new user" (marque "Auto Confirm User").
--  DEPOIS: troque o e-mail abaixo pelo e-mail usado e execute no SQL Editor.
-- =====================================================================

insert into privado.administradores (user_id)
select u.id from auth.users u
where lower(u.email) = lower('EMAIL_DO_JOSIAS@exemplo.com.br')
on conflict (user_id) do nothing;

-- Conferência: deve listar o e-mail do Josias
select u.email, a.criado_em
from privado.administradores a
join auth.users u on u.id = a.user_id;

-- Para REMOVER um administrador, use:
-- delete from privado.administradores
-- where user_id = (select id from auth.users where lower(email) = lower('EMAIL@exemplo.com.br'));
