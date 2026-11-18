"""
Teste de ponta a ponta no navegador (Chromium) — versão 2.0.

O site é servido localmente; as chamadas ao Supabase são atendidas por um
simulador que executa as funções REAIS do script SQL num PostgreSQL local,
com os papéis anon/authenticated. O serviço de login (Auth) é simulado,
inclusive a recuperação de senha por e-mail.

Uso: python3 testes/testar_navegador.py "host=/tmp port=5433 user=postgres"
Capturas de tela em testes/capturas/.
"""
import base64
import functools
import http.server
import json
import re
import sys
import threading
import time
from decimal import Decimal as D
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs

import psycopg
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
CAPTURAS = RAIZ / "testes" / "capturas"
CAPTURAS.mkdir(exist_ok=True)
DSN_BASE = sys.argv[1] if len(sys.argv) > 1 else "host=/tmp port=5433 user=postgres"
BANCO = "hjk_e2e_v2"
URL_SB = "https://teste-hjk.supabase.co"
CHAVE = "sb_publishable_TESTE"

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
EMAILS_RECUPERACAO = []

TIPOS = {
    "dados_formulario": {}, "servico_disponivel": {}, "sou_administrador": {}, "obter_configuracao": {},
    "salvar_configuracao": {"p_parametros": "jsonb", "p_quimicos": "jsonb"},
    "simular_orcamento": {"p_largura": "numeric", "p_comprimento": "numeric", "p_quantidade": "integer",
                          "p_sfa": "numeric", "p_camada": "numeric"},
    "calcular_orcamento": {"p_empresa": "text", "p_referencia": "text", "p_largura": "numeric", "p_comprimento": "numeric",
                           "p_quantidade": "integer", "p_sfa": "numeric", "p_camada": "numeric"},
    "verificar_orcamento": {"p_id": "text", "p_emitido_em": "text", "p_empresa": "text", "p_referencia": "text",
                            "p_largura": "numeric", "p_comprimento": "numeric", "p_quantidade": "integer",
                            "p_sfa": "numeric", "p_camada": "numeric", "p_valor": "numeric"},
}


def esperado(l, c_, q, s, k):
    """Valor final calculado diretamente pela função interna do banco."""
    with psycopg.connect(DSN) as c:
        return D(str(c.execute("select privado.calcular(%s,%s,%s,%s,%s)", (D(l), D(c_), q, D(s), D(k))).fetchone()[0]["valor_final"]))


def b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")


def token_para(email):
    return b64({"alg": "HS256", "typ": "JWT"}) + "." + b64(
        {"sub": USUARIOS[email], "email": email, "role": "authenticated", "aud": "authenticated",
         "exp": int(time.time()) + 3600}) + ".x"


def dados_token(auth):
    if not auth or not auth.startswith("Bearer "):
        return None
    partes = auth[7:].split(".")
    if len(partes) != 3:
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(partes[1] + "=="))
    except Exception:  # noqa: BLE001
        return None


def usuario_json(email):
    return {"id": USUARIOS[email], "email": email, "aud": "authenticated", "role": "authenticated",
            "app_metadata": {}, "user_metadata": {}, "created_at": "2026-01-01T00:00:00Z"}


requisicoes_rpc = []
SEGURAR = {"ativo": False, "pendentes": []}
CORS = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*"}


def responder(route, status, corpo):
    route.fulfill(status=status, headers=CORS, content_type="application/json", body=json.dumps(corpo, default=str))


def simulador(route, request):
    if SEGURAR["ativo"] and "calcular_orcamento" in request.url:
        SEGURAR["pendentes"].append((route, request))
        return
    u = urlparse(request.url)
    if request.method == "OPTIONS":
        return route.fulfill(status=204, headers=CORS)
    if u.path.startswith("/auth/v1/token"):
        d = json.loads(request.post_data or "{}")
        if SENHAS.get(d.get("email")) != d.get("password"):
            return responder(route, 400, {"code": 400, "error_code": "invalid_credentials", "msg": "Invalid login credentials"})
        e = d["email"]
        return responder(route, 200, {"access_token": token_para(e), "token_type": "bearer", "expires_in": 3600,
                                      "expires_at": int(time.time()) + 3600, "refresh_token": "r", "user": usuario_json(e)})
    if u.path.startswith("/auth/v1/recover"):
        d = json.loads(request.post_data or "{}")
        EMAILS_RECUPERACAO.append((d.get("email"), parse_qs(u.query).get("redirect_to", [""])[0]))
        return responder(route, 200, {})
    if u.path.startswith("/auth/v1/user"):
        tok = dados_token(request.headers.get("authorization"))
        if not tok:
            return responder(route, 401, {"msg": "invalid JWT"})
        email = tok["email"]
        if request.method == "PUT":
            nova = json.loads(request.post_data or "{}").get("password")
            if nova:
                SENHAS[email] = nova
        return responder(route, 200, usuario_json(email))
    if u.path.startswith("/auth/v1/logout"):
        return route.fulfill(status=204, headers=CORS)
    m = re.fullmatch(r"/rest/v1/rpc/(\w+)", u.path)
    if not m or m.group(1) not in TIPOS:
        return route.fulfill(status=404, headers=CORS, body="{}")
    fn = m.group(1)
    args = json.loads(request.post_data or "{}")
    requisicoes_rpc.append((fn, args))
    if request.headers.get("apikey") != CHAVE:
        return route.fulfill(status=401, headers=CORS, body="{}")
    tok = dados_token(request.headers.get("authorization"))
    sub = tok["sub"] if tok else None
    papel = "authenticated" if sub else "anon"
    tipos = TIPOS[fn]
    sql = f"select public.{fn}(" + ", ".join(f"{k} => %s::{t}" for k, t in tipos.items()) + ")"
    valores = [json.dumps(args.get(k)) if t == "jsonb" else args.get(k) for k, t in tipos.items()]
    try:
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute("select set_config('request.headers', %s, false)", (json.dumps({"cf-connecting-ip": "198.51.100.1"}),))
            c.execute("select set_config('request.jwt.claim.sub', %s, false)", (sub or "",))
            c.execute(f"set role {papel}")
            res = c.execute(sql, valores).fetchone()[0]
        return responder(route, 200, res)
    except psycopg.Error as e:
        return responder(route, 403 if e.sqlstate == "42501" else 400, {"code": e.sqlstate, "message": e.diag.message_primary})


CONFIG_TESTE = f"""window.HJK_CONFIG = {{ SUPABASE_URL: "{URL_SB}", SUPABASE_CHAVE_PUBLICA: "{CHAVE}",
WHATSAPP_NUMERO: "5511971651268", EMAIL_PEDIDOS: "hjk@hjk.ind.br" }};"""


class Silencioso(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), functools.partial(Silencioso, directory=str(RAIZ)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
SITE = "http://127.0.0.1:8765"

resultados = []


def teste(nome, fn):
    try:
        fn()
        resultados.append((True, nome, ""))
    except Exception as e:  # noqa: BLE001
        resultados.append((False, nome, f"{type(e).__name__}: {str(e)[:400]}"))


erros_console = []


def novo_contexto(browser, celular=False):
    opcoes = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2, "is_mobile": True,
              "has_touch": True} if celular else {"viewport": {"width": 1280, "height": 900}}
    ctx = browser.new_context(locale="pt-BR", **opcoes)
    ctx.route(f"{URL_SB}/**", simulador)
    ctx.route(f"{SITE}/js/config.js", lambda r, q: r.fulfill(status=200, content_type="application/javascript", body=CONFIG_TESTE))
    ctx.route("https://wa.me/**", lambda r, q: r.fulfill(status=200, body="WhatsApp simulado"))
    ctx.route("https://api.whatsapp.com/**", lambda r, q: r.fulfill(status=200, body="WhatsApp simulado"))
    return ctx


def vigiar(page):
    # 400 = respostas de erro provocadas de propósito pelos testes (senha errada, valor inválido)
    page.on("console", lambda m: erros_console.append(m.text) if m.type == "error" and "404" not in m.text
            and "status of 400" not in m.text else None)
    page.on("pageerror", lambda e: erros_console.append(str(e)))
    page.on("response", lambda r: erros_console.append("404: " + r.url) if r.status == 404 else None)
    page.on("response", lambda r: erros_console.append(f"{r.status}: " + r.url) if r.status >= 500 else None)


def preencher(page, empresa="Eletrônica Teste Ltda", ref="PCB-0042", qtd="100", larg="100", comp="100", sfa="75,38", camada=None):
    page.fill("#empresa", empresa)
    page.fill("#referencia", ref)
    page.fill("#quantidade", qtd)
    page.fill("#largura", larg)
    page.fill("#comprimento", comp)
    page.fill("#sfa", sfa)
    if camada is not None:
        page.fill("#camada", camada)


def moeda(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def login(pg, email="josias@hjk.test", senha=None):
    pg.fill("#email", email)
    pg.fill("#senha", senha or SENHAS[email])
    pg.click("#btn-entrar")


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = novo_contexto(browser)
    page = ctx.new_page()
    vigiar(page)
    estado = {}

    # ------------------------------------------------------------- cliente
    def t_formulario():
        page.goto(SITE + "/index.html")
        page.wait_for_selector("#btn-calcular:enabled")
        page.wait_for_function("document.getElementById('dica-camada').textContent.includes('entre')") if False else None
        page.wait_for_selector("#dica-camada:has-text('entre 0,03 e 0,10')")
        assert page.input_value("#camada") == "0,09"
    teste("Formulário com camada de ouro preenchida (0,09) e faixa 0,03–0,10 vinda do servidor", t_formulario)

    def t_orcamento():
        preencher(page)
        page.click("#btn-calcular")
        page.wait_for_selector("#resultado:not([hidden])")
        esp = esperado("100", "100", 100, "75.38", "0.09")
        assert page.text_content("#r-valor-final").strip() == moeda(esp), (page.text_content("#r-valor-final"), esp)
        assert page.text_content("#r-area-total").strip() == "7.538,00 cm²"
        assert page.text_content("#r-camada").strip() == "0,09 µm"
        wa = unquote(page.get_attribute("#btn-whatsapp", "href").split("?text=")[1])
        assert "Camada de ouro: 0,09 µm" in wa and "Valor do orçamento: " + moeda(esp) in wa, wa
        mail = page.get_attribute("#btn-email", "href")
        assert mail.startswith("mailto:hjk@hjk.ind.br?subject=")
        q = parse_qs(mail.split("?", 1)[1])
        assert page.text_content("#r-id") in q["subject"][0]
        corpo = q["body"][0].replace("\r\n", "\n")
        assert corpo == wa.replace("*", ""), "e-mail diferente do WhatsApp"
        estado["msg"] = wa
        page.screenshot(path=str(CAPTURAS / "03_resultado_computador.png"), full_page=True)
    teste("Orçamento: valor igual ao do servidor; WhatsApp e e-mail com o mesmo texto e valor", t_orcamento)

    def t_whatsapp_abre():
        with page.expect_popup() as pop:
            page.click("#btn-whatsapp")
        pop.value.close()
    teste("Botão do WhatsApp abre a conversa da HJK em nova aba", t_whatsapp_abre)

    def t_camadas():
        valores = {}
        for k in ("0,05", "0,10"):
            page.fill("#camada", k)
            page.click("#btn-calcular")
            page.wait_for_selector("#resultado:not([hidden])")
            valores[k] = page.text_content("#r-valor-final").strip()
        assert valores["0,05"] == moeda(esperado("100", "100", 100, "75.38", "0.05"))
        assert valores["0,10"] == moeda(esperado("100", "100", 100, "75.38", "0.10"))
        assert valores["0,05"] != valores["0,10"]
        n = len(requisicoes_rpc)
        page.fill("#camada", "0,11")
        page.click("#btn-calcular")
        page.wait_for_selector("#erro-camada:has-text('0,03 e 0,10')")
        assert len(requisicoes_rpc) == n and page.is_hidden("#resultado")
    teste("Camada 0,05 e 0,10 dão valores diferentes; 0,11 é recusada na tela", t_camadas)

    def t_concorrencia():
        page.goto(SITE + "/index.html")
        page.wait_for_selector("#btn-calcular:enabled")
        preencher(page)
        SEGURAR["ativo"] = True
        page.click("#btn-calcular")
        page.wait_for_selector("#btn-calcular:disabled")
        page.fill("#camada", "0,07")
        SEGURAR["ativo"] = False
        route, req = SEGURAR["pendentes"].pop()
        with page.expect_response(lambda r: "calcular_orcamento" in r.url):
            simulador(route, req)
        page.wait_for_selector("#btn-calcular:enabled")
        assert page.is_hidden("#resultado")
    teste("Concorrência: alteração durante o cálculo descarta a resposta antiga", t_concorrencia)

    def t_validacao():
        page.goto(SITE + "/index.html")
        page.wait_for_selector("#btn-calcular:enabled")
        preencher(page, empresa="", qtd="-3", larg="abc", comp="0", sfa="250", camada="")
        n = len(requisicoes_rpc)
        page.click("#btn-calcular")
        for campo in ("empresa", "quantidade", "largura", "comprimento", "sfa", "camada"):
            assert page.text_content(f"#erro-{campo}").strip(), campo
        assert len(requisicoes_rpc) == n
        page.screenshot(path=str(CAPTURAS / "04_validacao.png"), full_page=True)
    teste("Teste 9: campos inválidos bloqueados na tela (inclusive a camada)", t_validacao)

    def t_resposta_publica():
        preencher(page, camada="0,06")
        page.click("#btn-calcular")
        page.wait_for_selector("#resultado:not([hidden])")
        page.click("#btn-novo")
        assert page.input_value("#camada") == "0,09", "Novo orçamento deve voltar à camada padrão"
        preencher(page)
        with page.expect_response(lambda r: "calcular_orcamento" in r.url) as resp:
            page.click("#btn-calcular")
        d = resp.value.json()
        assert d["ok"] and not ({"itens", "custo", "quimicos", "mao_de_obra", "margem_valor", "tributos_valor"} & set(d)), d
    teste("Teste 8: resposta pública sem composição de custos; “Novo orçamento” volta à camada padrão", t_resposta_publica)

    # ------------------------------------------------------------- administração
    adm = ctx.new_page()
    vigiar(adm)

    def t_intruso_e_senha():
        adm.goto(SITE + "/admin.html")
        adm.wait_for_selector("#form-login:not([hidden])")
        login(adm, "intruso@x.test")
        adm.wait_for_selector("#aviso:has-text('permissão')")
        login(adm, "josias@hjk.test", "errada")
        adm.wait_for_selector("#aviso:has-text('incorretos')")
        assert adm.is_hidden("#painel")
    teste("Teste 7: sem permissão e senha errada não entram", t_intruso_e_senha)

    def t_admin_config():
        login(adm)
        adm.wait_for_selector("#painel:not([hidden])")
        adm.wait_for_selector("#tabela-quimicos tr[data-codigo='aurocianeto']")
        assert adm.locator("#tabela-quimicos tr[data-codigo]").count() == 11
        assert adm.input_value("#p-margem") == "50" and adm.input_value("#p-tributos") == "15"
        assert adm.input_value("#p-camada_max") == "0,1"
        adm.screenshot(path=str(CAPTURAS / "02_admin_parametros.png"), full_page=True)
    teste("Administração mostra 11 materiais e os parâmetros em grupos", t_admin_config)

    def t_admin_salvar():
        adm.fill("#p-margem", "60")
        adm.fill("#p-minimo_pedido", "1500")
        adm.fill("#tabela-quimicos tr[data-codigo='aurocianeto'] input[data-campo='preco']", "550,5")
        adm.select_option("#tabela-quimicos tr[data-codigo='parte_a'] select", "ouro")
        adm.click("#btn-salvar-config")
        adm.wait_for_selector("#aviso:has-text('Alterações salvas (4 itens)')")
        with psycopg.connect(DSN) as c:
            m = c.execute("select valor from privado.config where chave='margem'").fetchone()[0]
            mn = c.execute("select valor from privado.config where chave='minimo_pedido'").fetchone()[0]
            pr, base = c.execute("select q1.preco, q2.base from privado.quimicos q1, privado.quimicos q2 "
                                 "where q1.codigo='aurocianeto' and q2.codigo='parte_a'").fetchone()
        assert (m, mn, pr, base) == (60, 1500, D("550.5"), "ouro"), (m, mn, pr, base)
        page.goto(SITE + "/index.html")
        page.wait_for_selector("#btn-calcular:enabled")
        preencher(page)
        page.click("#btn-calcular")
        page.wait_for_selector("#resultado:not([hidden])")
        assert page.text_content("#r-valor-final").strip() == moeda(esperado("100", "100", 100, "75.38", "0.09"))
    teste("Teste 5/6: alterações salvas valem imediatamente no orçamento (sem separador de milhar errado)", t_admin_salvar)

    def t_admin_invalido():
        adm.fill("#p-tributos", "100")
        adm.click("#btn-salvar-config")
        adm.wait_for_selector("#aviso:has-text('Nada foi salvo')")
        with psycopg.connect(DSN) as c:
            assert c.execute("select valor from privado.config where chave='tributos'").fetchone()[0] == 15
        adm.click("#btn-desfazer")
        assert adm.input_value("#p-tributos") == "15"
        adm.fill("#p-margem", "50"); adm.fill("#p-minimo_pedido", "0")
        adm.fill("#tabela-quimicos tr[data-codigo='aurocianeto'] input[data-campo='preco']", "500")
        adm.select_option("#tabela-quimicos tr[data-codigo='parte_a'] select", "area")
        adm.click("#btn-salvar-config")
        adm.wait_for_selector("#aviso:has-text('Alterações salvas')")
    teste("Valor inválido: nada é salvo; “Desfazer” restaura a tela", t_admin_invalido)

    def t_simulador():
        adm.click("#btn-simular")
        adm.wait_for_selector("#tabela-simulacao")
        texto = adm.text_content("#tabela-simulacao")
        esp = moeda(esperado("100", "100", 100, "75.38", "0.09"))
        for t in ("Aurocianeto", "Químicos", "Mão de obra", "Custo total", "Margem", "Tributos", "Valor final do orçamento", esp):
            assert t in texto, (t, texto[:300])
        adm.fill("#s-camada", "0,2")
        adm.click("#btn-simular")
        adm.wait_for_selector("#sim-resultado:has-text('Atenção')")
        adm.fill("#s-camada", "0,09")
        adm.click("#btn-simular")
        adm.wait_for_selector("#tabela-simulacao")
        adm.screenshot(path=str(CAPTURAS / "05_admin_simulador.png"), full_page=True)
    teste("Simulador mostra a composição e o mesmo valor do orçamento; avisa camada fora da faixa", t_simulador)

    def t_verificacao():
        page.goto(SITE + "/index.html")
        page.wait_for_selector("#btn-calcular:enabled")
        preencher(page, camada="0,07")
        page.click("#btn-calcular")
        page.wait_for_selector("#resultado:not([hidden])")
        msg = unquote(page.get_attribute("#btn-whatsapp", "href").split("?text=")[1])
        adm.fill("#msg-colada", msg)
        adm.click("#btn-ler")
        assert adm.input_value("#v-camada") == "0,07"
        adm.click("#btn-verificar")
        adm.wait_for_selector("#verif-resultado:has-text('autêntico')")
        adm.fill("#v-camada", "0,09")
        adm.click("#btn-verificar")
        adm.wait_for_selector("#verif-resultado:has-text('não confere')")
        adm.screenshot(path=str(CAPTURAS / "06_admin_conferencia.png"), full_page=True)
    teste("Conferência: mensagem autêntica; camada alterada é detectada", t_verificacao)

    def t_alterar_senha_cancelar():
        adm.click("#btn-alterar-senha")
        adm.wait_for_selector("#form-nova-senha:not([hidden])")
        assert adm.is_visible("#btn-cancelar-senha")
        adm.click("#btn-cancelar-senha")
        adm.wait_for_selector("#painel:not([hidden])")
    teste("“Alterar senha” abre o formulário e pode ser cancelado", t_alterar_senha_cancelar)

    def t_esqueci():
        adm.click("#btn-sair")
        adm.wait_for_selector("#form-login:not([hidden])")
        adm.click("#btn-esqueci")
        adm.wait_for_selector("#form-esqueci:not([hidden])")
        adm.fill("#email-recuperar", "josias@hjk.test")
        adm.click("#btn-enviar-link")
        adm.wait_for_selector("#aviso:has-text('link para criar uma senha nova')")
        email, destino = EMAILS_RECUPERACAO[-1]
        assert email == "josias@hjk.test" and destino == SITE + "/admin.html", EMAILS_RECUPERACAO
    teste("“Esqueci minha senha” pede o link ao Supabase com retorno para a administração", t_esqueci)

    def t_link_recuperacao():
        ctx2 = novo_contexto(browser)
        pr = ctx2.new_page()
        vigiar(pr)
        tok = token_para("josias@hjk.test")
        pr.goto(f"{SITE}/admin.html#access_token={tok}&expires_at={int(time.time()) + 3600}&expires_in=3600"
                f"&refresh_token=r&token_type=bearer&type=recovery")
        pr.wait_for_selector("#form-nova-senha:not([hidden])")
        assert pr.is_hidden("#btn-cancelar-senha")
        pr.fill("#nova-senha", "Nova-Senha-2026!")
        pr.fill("#nova-senha-2", "Nova-Senha-2026?")
        pr.click("#btn-salvar-senha")
        pr.wait_for_selector("#aviso:has-text('não são iguais')")
        pr.fill("#nova-senha", "curta")
        pr.fill("#nova-senha-2", "curta")
        pr.click("#btn-salvar-senha")
        pr.wait_for_selector("#aviso:has-text('10 caracteres')")
        pr.fill("#nova-senha", "Nova-Senha-2026!")
        pr.fill("#nova-senha-2", "Nova-Senha-2026!")
        pr.click("#btn-salvar-senha")
        pr.wait_for_selector("#painel:not([hidden])")
        assert "#" not in pr.url and "access_token" not in pr.url, "o token deve sair do endereço: " + pr.url
        assert SENHAS["josias@hjk.test"] == "Nova-Senha-2026!"
        pr.screenshot(path=str(CAPTURAS / "07_admin_nova_senha_ok.png"), full_page=True)
        ctx2.close()
        login(adm, "josias@hjk.test", "Nova-Senha-2026!")
        adm.wait_for_selector("#painel:not([hidden])")
    teste("Link de recuperação: cria senha nova, entra no painel e a senha nova funciona no login", t_link_recuperacao)

    def t_link_expirado():
        ctx3 = novo_contexto(browser)
        pe = ctx3.new_page()
        pe.goto(f"{SITE}/admin.html#error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid")
        pe.wait_for_selector("#aviso:has-text('expirou')")
        pe.wait_for_selector("#form-login:not([hidden])")
        ctx3.close()
    teste("Link de recuperação expirado mostra aviso claro", t_link_expirado)
    ctx.close()

    # ------------------------------------------------------------- celular
    def t_celular():
        cm = novo_contexto(browser, celular=True)
        pg = cm.new_page()
        vigiar(pg)
        pg.goto(SITE + "/index.html")
        pg.wait_for_selector("#btn-calcular:enabled")
        pg.screenshot(path=str(CAPTURAS / "08_celular_formulario.png"), full_page=True)
        assert pg.evaluate("document.documentElement.scrollWidth") <= 390
        preencher(pg, qtd="250", larg="80,5", comp="120", sfa="132,4", camada="0,08")
        pg.click("#btn-calcular")
        pg.wait_for_selector("#resultado:not([hidden])")
        assert pg.evaluate("document.documentElement.scrollWidth") <= 390
        pg.screenshot(path=str(CAPTURAS / "09_celular_resultado.png"), full_page=True)
        pa = cm.new_page()
        vigiar(pa)
        pa.goto(SITE + "/admin.html")
        pa.wait_for_selector("#form-login:not([hidden])")
        login(pa)
        pa.wait_for_selector("#tabela-quimicos")
        assert pa.evaluate("document.documentElement.scrollWidth") <= 390, "administração com rolagem lateral no celular"
        pa.screenshot(path=str(CAPTURAS / "10_celular_admin.png"), full_page=True)
        cm.close()
    teste("Teste 11: cliente e administração no celular (390 px) sem rolagem lateral", t_celular)

    browser.close()

teste("Nenhum erro de JavaScript no console", lambda: (_ for _ in ()).throw(AssertionError("; ".join(erros_console[:5]))) if erros_console else None)
srv.shutdown()

ok = sum(1 for r in resultados if r[0])
print(f"\nTESTES NO NAVEGADOR (v2.0) — {ok}/{len(resultados)} aprovados\n")
for passou, nome, erro in resultados:
    print(("  [OK]   " if passou else "  [FALHA] ") + nome + (f"\n          {erro}" if erro else ""))
sys.exit(0 if ok == len(resultados) else 1)
