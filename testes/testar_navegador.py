"""
Teste de ponta a ponta no navegador (Chromium), em computador e celular.

O site é servido localmente e as chamadas ao Supabase são atendidas por um
simulador que executa as funções REAIS do script SQL num PostgreSQL local,
com os mesmos papéis (anon / authenticated) usados pelo Supabase.

Uso: python3 testes/testar_navegador.py "host=/tmp port=5433 user=postgres"
Gera capturas de tela em testes/capturas/.
"""
import base64
import functools
import http.server
import json
import re
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
CAPTURAS = RAIZ / "testes" / "capturas"
CAPTURAS.mkdir(exist_ok=True)
DSN_BASE = sys.argv[1] if len(sys.argv) > 1 else "host=/tmp port=5433 user=postgres"
BANCO = "hjk_e2e"
URL_SB = "https://teste-hjk.supabase.co"
CHAVE = "sb_publishable_TESTE"

# ------------------------------------------------------------ banco de teste
with psycopg.connect(DSN_BASE + " dbname=postgres", autocommit=True) as c:
    c.execute(f"drop database if exists {BANCO}")
    c.execute(f"create database {BANCO}")
DSN = f"{DSN_BASE} dbname={BANCO}"
USUARIOS = {}
with psycopg.connect(DSN, autocommit=True) as c:
    c.execute((RAIZ / "testes/supabase_simulado.sql").read_text())
    c.execute((RAIZ / "supabase/01_instalacao.sql").read_text())
    for email in ("josias@hjk.test", "intruso@x.test"):
        USUARIOS[email] = str(c.execute("insert into auth.users(email) values (%s) returning id", (email,)).fetchone()[0])
    c.execute("insert into privado.administradores(user_id) values (%s)", (USUARIOS["josias@hjk.test"],))
SENHAS = {"josias@hjk.test": "Senha-Forte-123", "intruso@x.test": "outra-senha"}

TIPOS = {
    "servico_disponivel": {},
    "sou_administrador": {},
    "obter_parametros": {},
    "calcular_orcamento": {"p_empresa": "text", "p_referencia": "text", "p_largura": "numeric", "p_comprimento": "numeric", "p_quantidade": "integer", "p_sfa": "numeric"},
    "atualizar_parametros": {"p_preco_cm2": "numeric", "p_minimo_pedido": "numeric"},
    "verificar_orcamento": {"p_id": "text", "p_emitido_em": "text", "p_empresa": "text", "p_referencia": "text",
                            "p_largura": "numeric", "p_comprimento": "numeric",
                            "p_quantidade": "integer", "p_sfa": "numeric", "p_valor": "numeric"},
}


def b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")


def token_para(email):
    return b64({"alg": "HS256", "typ": "JWT"}) + "." + b64(
        {"sub": USUARIOS[email], "email": email, "role": "authenticated", "exp": int(time.time()) + 3600}) + ".x"


def usuario_do_token(auth):
    if not auth or not auth.startswith("Bearer "):
        return None
    partes = auth[7:].split(".")
    if len(partes) != 3:
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(partes[1] + "==")).get("sub")
    except Exception:  # noqa: BLE001
        return None


requisicoes_rpc = []
SEGURAR = {"ativo": False, "pendentes": []}


def simulador(route, request):
    if SEGURAR["ativo"] and "calcular_orcamento" in request.url:
        SEGURAR["pendentes"].append((route, request))  # resposta atrasada de propósito
        return
    u = urlparse(request.url)
    cors = {"access-control-allow-origin": "*", "access-control-allow-headers": "*",
            "access-control-allow-methods": "*"}
    if request.method == "OPTIONS":
        return route.fulfill(status=204, headers=cors)
    if u.path.startswith("/auth/v1/token"):
        d = json.loads(request.post_data or "{}")
        if SENHAS.get(d.get("email")) != d.get("password"):
            return route.fulfill(status=400, headers=cors, content_type="application/json",
                                 body=json.dumps({"code": 400, "error_code": "invalid_credentials",
                                                  "msg": "Invalid login credentials"}))
        email = d["email"]
        return route.fulfill(status=200, headers=cors, content_type="application/json", body=json.dumps({
            "access_token": token_para(email), "token_type": "bearer", "expires_in": 3600,
            "expires_at": int(time.time()) + 3600, "refresh_token": "r",
            "user": {"id": USUARIOS[email], "email": email, "aud": "authenticated", "role": "authenticated",
                     "app_metadata": {}, "user_metadata": {}, "created_at": "2026-01-01T00:00:00Z"}}))
    if u.path.startswith("/auth/v1/logout"):
        return route.fulfill(status=204, headers=cors)
    m = re.fullmatch(r"/rest/v1/rpc/(\w+)", u.path)
    if not m or m.group(1) not in TIPOS:
        return route.fulfill(status=404, headers=cors, body="{}")
    fn = m.group(1)
    args = json.loads(request.post_data or "{}")
    requisicoes_rpc.append((fn, args))
    if request.headers.get("apikey") != CHAVE:
        return route.fulfill(status=401, headers=cors, body="{}")
    sub = usuario_do_token(request.headers.get("authorization"))
    papel = "authenticated" if sub else "anon"
    tipos = TIPOS[fn]
    sql = f"select public.{fn}(" + ", ".join(f"{k} => %s::{t}" for k, t in tipos.items()) + ")"
    try:
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute("select set_config('request.headers', %s, false)", (json.dumps({"cf-connecting-ip": "198.51.100.1"}),))
            c.execute("select set_config('request.jwt.claim.sub', %s, false)", (sub or "",))
            c.execute(f"set role {papel}")
            res = c.execute(sql, [args.get(k) for k in tipos]).fetchone()[0]
        return route.fulfill(status=200, headers=cors, content_type="application/json", body=json.dumps(res, default=str))
    except psycopg.Error as e:
        status = 403 if e.sqlstate == "42501" else 400
        return route.fulfill(status=status, headers=cors, content_type="application/json",
                             body=json.dumps({"code": e.sqlstate, "message": e.diag.message_primary}))


CONFIG_TESTE = f"""window.HJK_CONFIG = {{ SUPABASE_URL: "{URL_SB}", SUPABASE_CHAVE_PUBLICA: "{CHAVE}",
WHATSAPP_NUMERO: "5511971651268" }};"""

# ------------------------------------------------------------ servidor local
class Silencioso(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


Handler = functools.partial(Silencioso, directory=str(RAIZ))
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
SITE = "http://127.0.0.1:8765"

resultados = []


def teste(nome, fn):
    try:
        fn()
        resultados.append((True, nome, ""))
    except Exception as e:  # noqa: BLE001
        resultados.append((False, nome, f"{type(e).__name__}: {str(e)[:300]}"))


def novo_contexto(browser, celular=False):
    opcoes = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2, "is_mobile": True,
              "has_touch": True} if celular else {"viewport": {"width": 1280, "height": 900}}
    ctx = browser.new_context(locale="pt-BR", **opcoes)
    ctx.route(f"{URL_SB}/**", simulador)
    ctx.route(f"{SITE}/js/config.js", lambda r, q: r.fulfill(status=200, content_type="application/javascript", body=CONFIG_TESTE))
    return ctx


def preencher(page, empresa="Eletrônica Teste Ltda", ref="PCB-0042", qtd="100", larg="100", comp="100", sfa="75,38"):
    page.fill("#empresa", empresa)
    page.fill("#referencia", ref)
    page.fill("#quantidade", qtd)
    page.fill("#largura", larg)
    page.fill("#comprimento", comp)
    page.fill("#sfa", sfa)


erros_console = []

with sync_playwright() as p:
    browser = p.chromium.launch()

    # 1) Serviço sem preços
    ctx = novo_contexto(browser)
    page = ctx.new_page()
    page.on("console", lambda m: erros_console.append(m.text) if m.type == "error" and "404" not in m.text else None)
    page.on("response", lambda r: erros_console.append("404: " + r.url) if r.status == 404 and "logo-hjk.png" not in r.url else None)
    page.on("pageerror", lambda e: erros_console.append(str(e)))

    def t_indisponivel():
        page.goto(SITE + "/index.html")
        page.wait_for_selector("#aviso:not([hidden])")
        assert "ainda não está disponível" in page.text_content("#aviso")
        assert page.is_disabled("#btn-calcular")
        page.screenshot(path=str(CAPTURAS / "01_servico_indisponivel.png"), full_page=True)
    teste("Sem preços configurados, a página bloqueia o orçamento", t_indisponivel)

    # 2) Administração: intruso
    adm = ctx.new_page()

    def t_intruso():
        adm.goto(SITE + "/admin.html")
        adm.wait_for_selector("#form-login:not([hidden])")
        adm.fill("#email", "intruso@x.test")
        adm.fill("#senha", "outra-senha")
        adm.click("#btn-entrar")
        adm.wait_for_selector("#aviso:has-text('permissão')")
        assert adm.is_hidden("#painel")
    teste("Teste 7: usuário sem permissão não acessa o painel", t_intruso)

    def t_senha_errada():
        adm.fill("#email", "josias@hjk.test")
        adm.fill("#senha", "errada")
        adm.click("#btn-entrar")
        adm.wait_for_selector("#aviso:has-text('incorretos')")
        assert adm.is_hidden("#painel")
    teste("Teste 7: senha incorreta é recusada", t_senha_errada)

    def t_admin():
        adm.fill("#senha", "Senha-Forte-123")
        adm.click("#btn-entrar")
        adm.wait_for_selector("#painel:not([hidden])")
        assert "não configurado" in adm.text_content("#atual-preco")
        adm.fill("#novo-preco", "0,05")
        adm.fill("#novo-minimo", "150,00")
        adm.click("#btn-salvar")
        adm.wait_for_selector("#atual-preco:has-text('0,05')")
        assert adm.text_content("#atual-minimo").strip() == "R$ 150,00", adm.text_content("#atual-minimo")
        adm.screenshot(path=str(CAPTURAS / "02_admin_precos.png"), full_page=True)
    teste("Teste 5: Josias entra e cadastra preço R$ 0,05/cm² e mínimo R$ 150,00", t_admin)

    # 3) Cliente: orçamento com mínimo e sem mínimo
    resultado_100 = {}

    def t_cliente_minimo():
        page.goto(SITE + "/index.html")
        page.wait_for_selector("#btn-calcular:enabled")
        preencher(page, qtd="1")
        page.click("#btn-calcular")
        page.wait_for_selector("#resultado:not([hidden])")
        assert page.text_content("#r-area-total").strip() == "75,38 cm²", page.text_content("#r-area-total")
        assert page.text_content("#r-valor-calculado").strip() == "R$ 3,77"
        assert page.text_content("#r-valor-final").strip() == "R$ 150,00"
        assert page.is_visible("#r-minimo")
    teste("Testes 1 e 4: 100×100 mm, qtd 1, 75,38% → 75,38 cm²; mínimo R$ 150,00 aplicado", t_cliente_minimo)

    def t_cliente_100():
        page.click("#btn-novo")
        assert page.input_value("#empresa") == "" and page.is_hidden("#resultado")
        preencher(page, qtd="100")
        page.click("#btn-calcular")
        page.wait_for_selector("#resultado:not([hidden])")
        assert page.text_content("#r-area-total").strip() == "7.538,00 cm²"
        assert page.text_content("#r-valor-final").strip() == "R$ 376,90"
        assert page.is_hidden("#r-minimo")
        href = page.get_attribute("#btn-whatsapp", "href")
        assert href.startswith("https://wa.me/5511971651268?text=")
        msg = __import__("urllib.parse").parse.unquote(href.split("?text=")[1])
        assert "Valor do orçamento: R$ 376,90" in msg and "Área total ENIG: 7.538,00 cm²" in msg, msg
        assert page.text_content("#r-id") in msg
        resultado_100["msg"] = msg
        page.screenshot(path=str(CAPTURAS / "03_resultado_computador.png"), full_page=True)
    teste("Testes 2, 3 e 10: qtd 100 → 7.538 cm², R$ 376,90; WhatsApp com valor idêntico", t_cliente_100)

    def t_whatsapp_abre():
        with page.expect_popup() as pop:
            page.click("#btn-whatsapp")
        nova = pop.value
        assert nova.url.startswith("https://wa.me/5511971651268") or "whatsapp" in nova.url or nova.url == "about:blank", nova.url
        nova.close()
    ctx.route("https://wa.me/**", lambda r, q: r.fulfill(status=200, body="WhatsApp simulado"))
    ctx.route("https://api.whatsapp.com/**", lambda r, q: r.fulfill(status=200, body="WhatsApp simulado"))
    teste("Teste 10: botão abre o WhatsApp da HJK em nova aba", t_whatsapp_abre)

    def t_alteracao_invalida():
        page.fill("#quantidade", "200")
        assert page.is_hidden("#resultado"), "resultado antigo continuou visível após alterar dados"
    teste("Alterar um campo após o cálculo esconde o resultado antigo", t_alteracao_invalida)

    def t_concorrencia():
        page.goto(SITE + "/index.html")
        page.wait_for_selector("#btn-calcular:enabled")
        preencher(page, qtd="100")
        SEGURAR["ativo"] = True
        page.click("#btn-calcular")
        page.wait_for_selector("#btn-calcular:disabled")
        page.fill("#quantidade", "999")          # cliente altera durante o cálculo
        SEGURAR["ativo"] = False
        route, req = SEGURAR["pendentes"].pop()
        with page.expect_response(lambda r: "calcular_orcamento" in r.url):
            simulador(route, req)                # resposta antiga chega depois
        page.wait_for_selector("#btn-calcular:enabled")
        assert page.is_hidden("#resultado"), "resposta antiga foi exibida após alteração do campo"
    teste("Concorrência: alteração durante o cálculo descarta a resposta antiga", t_concorrencia)

    def t_validacao():
        page.goto(SITE + "/index.html")
        page.wait_for_selector("#btn-calcular:enabled")
        preencher(page, empresa="", qtd="-3", larg="abc", comp="0", sfa="250")
        n = len(requisicoes_rpc)
        page.click("#btn-calcular")
        for campo in ("empresa", "quantidade", "largura", "comprimento", "sfa"):
            assert page.text_content(f"#erro-{campo}").strip(), f"sem erro em {campo}"
        assert len(requisicoes_rpc) == n, "enviou ao servidor dados inválidos"
        assert page.is_hidden("#resultado")
        page.screenshot(path=str(CAPTURAS / "04_validacao.png"), full_page=True)
    teste("Teste 9: campos vazios, negativos e SFA > 200% bloqueados na tela", t_validacao)

    def t_sem_parametros_na_resposta():
        preencher(page)
        with page.expect_response(lambda r: "calcular_orcamento" in r.url) as resp:
            page.click("#btn-calcular")
        dados = resp.value.json()
        assert dados.get("ok") is True, dados
        assert not ({"preco_cm2", "minimo_pedido"} & set(dados)), dados
    teste("Teste 8: resposta pública do cálculo não contém os parâmetros", t_sem_parametros_na_resposta)

    # 4) Verificação no admin
    def t_verificacao():
        adm.fill("#msg-colada", resultado_100["msg"])
        adm.click("#btn-ler")
        assert adm.input_value("#v-valor") == "376,90", adm.input_value("#v-valor")
        assert adm.input_value("#v-empresa") == "Eletrônica Teste Ltda"
        assert adm.input_value("#v-referencia") == "PCB-0042"
        assert len(adm.input_value("#v-emitido")) == 16
        adm.click("#btn-verificar")
        adm.wait_for_selector("#verif-resultado:not([hidden])")
        assert "autêntico" in adm.text_content("#verif-resultado")
        adm.screenshot(path=str(CAPTURAS / "05_admin_verificacao_ok.png"), full_page=True)
        adm.fill("#v-empresa", "Empresa Falsa Ltda")
        adm.click("#btn-verificar")
        adm.wait_for_selector("#verif-resultado:has-text('não confere')")
        adm.fill("#v-empresa", "Eletrônica Teste Ltda")
        adm.click("#btn-verificar")
        adm.wait_for_selector("#verif-resultado:has-text('autêntico')")
        adm.fill("#v-valor", "300,00")
        adm.click("#btn-verificar")
        adm.wait_for_selector("#verif-resultado:has-text('não confere')")
        adm.screenshot(path=str(CAPTURAS / "06_admin_verificacao_alterada.png"), full_page=True)
    teste("Conferência: mensagem colada é autêntica; empresa ou valor alterados são detectados", t_verificacao)

    def t_persistencia():
        adm.click("#btn-sair")
        adm.wait_for_selector("#form-login:not([hidden])")
        ctx2 = novo_contexto(browser)
        p2 = ctx2.new_page()
        p2.goto(SITE + "/admin.html")
        p2.fill("#email", "josias@hjk.test")
        p2.fill("#senha", "Senha-Forte-123")
        p2.click("#btn-entrar")
        p2.wait_for_selector("#painel:not([hidden])")
        p2.wait_for_selector("#atual-preco:has-text('0,05')")
        assert p2.text_content("#atual-minimo").strip() == "R$ 150,00"
        ctx2.close()
    teste("Teste 6: preços continuam salvos em novo acesso (novo navegador)", t_persistencia)
    ctx.close()

    # 5) Celular
    def t_celular():
        cm = novo_contexto(browser, celular=True)
        pg = cm.new_page()
        pg.goto(SITE + "/index.html")
        pg.wait_for_selector("#btn-calcular:enabled")
        pg.screenshot(path=str(CAPTURAS / "07_celular_formulario.png"), full_page=True)
        largura_doc = pg.evaluate("document.documentElement.scrollWidth")
        assert largura_doc <= 390, f"rolagem horizontal no celular ({largura_doc}px)"
        preencher(pg, qtd="250", larg="80,5", comp="120", sfa="132,4")
        pg.click("#btn-calcular")
        pg.wait_for_selector("#resultado:not([hidden])")
        assert pg.evaluate("document.documentElement.scrollWidth") <= 390
        pg.screenshot(path=str(CAPTURAS / "08_celular_resultado.png"), full_page=True)
        pa = cm.new_page()
        pa.goto(SITE + "/admin.html")
        pa.wait_for_selector("#form-login:not([hidden])")
        pa.screenshot(path=str(CAPTURAS / "09_celular_admin_login.png"), full_page=True)
        cm.close()
    teste("Teste 11: funciona no celular (390 px) sem rolagem horizontal", t_celular)

    browser.close()

teste("Nenhum erro de JavaScript no console", lambda: (_ for _ in ()).throw(AssertionError("; ".join(erros_console))) if erros_console else None)
srv.shutdown()

ok = sum(1 for r in resultados if r[0])
print(f"\nTESTES NO NAVEGADOR — {ok}/{len(resultados)} aprovados\n")
for passou, nome, erro in resultados:
    print(("  [OK]   " if passou else "  [FALHA] ") + nome + (f"\n          {erro}" if erro else ""))
sys.exit(0 if ok == len(resultados) else 1)
