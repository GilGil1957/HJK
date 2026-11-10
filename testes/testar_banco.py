"""
Testes automatizados do banco de dados (script SQL do Supabase).

Executa o script de instalação num PostgreSQL local que simula o Supabase
e verifica cálculo, mínimo, administração, persistência, bloqueios,
limites contra consultas automatizadas e verificação de orçamentos.

Uso:  python3 testes/testar_banco.py "host=/tmp port=5433 user=postgres"
"""
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import psycopg

RAIZ = Path(__file__).resolve().parent.parent
DSN_BASE = sys.argv[1] if len(sys.argv) > 1 else "host=/tmp port=5433 user=postgres"
BANCO = "hjk_teste"

resultados = []


def teste(nome):
    def deco(fn):
        try:
            fn()
            resultados.append((True, nome, ""))
        except Exception as e:  # noqa: BLE001
            resultados.append((False, nome, f"{type(e).__name__}: {e}"))
        return fn
    return deco


# ---------------------------------------------------------------- preparação
with psycopg.connect(DSN_BASE + " dbname=postgres", autocommit=True) as c:
    c.execute(f"drop database if exists {BANCO}")
    c.execute(f"create database {BANCO}")

DSN = f"{DSN_BASE} dbname={BANCO}"
with psycopg.connect(DSN, autocommit=True) as c:
    c.execute((RAIZ / "testes/supabase_simulado.sql").read_text())
    c.execute((RAIZ / "supabase/01_instalacao.sql").read_text())
    ADMIN = c.execute("insert into auth.users(email) values ('josias@hjk.test') returning id").fetchone()[0]
    INTRUSO = c.execute("insert into auth.users(email) values ('outro@x.test') returning id").fetchone()[0]
    c.execute("insert into privado.administradores(user_id) values (%s)", (ADMIN,))

_ip_seq = [0]


def novo_ip():
    _ip_seq[0] += 1
    return f"10.0.{_ip_seq[0] // 250}.{_ip_seq[0] % 250}"


def como(papel, usuario=None, ip=None, headers=None):
    """Abre conexão simulando uma requisição da API do Supabase."""
    c = psycopg.connect(DSN, autocommit=True)
    if headers is None:
        headers = {"cf-connecting-ip": ip or novo_ip()}
    c.execute("select set_config('request.headers', %s, false)", (json.dumps(headers),))
    c.execute("select set_config('request.jwt.claim.sub', %s, false)", (str(usuario) if usuario else "",))
    c.execute(f"set role {papel}")
    return c


EMPRESA = "Eletrônica Teste Ltda"
REF = "PCB-01"


def calcular(l, cmp, q, s, ip=None, papel="anon", empresa=EMPRESA, ref=REF, headers=None):
    with como(papel, ip=ip, headers=headers) as c:
        return c.execute("select public.calcular_orcamento(%s::text,%s::text,%s::numeric,%s::numeric,%s::integer,%s::numeric)",
                         (empresa, ref, l, cmp, q, s)).fetchone()[0]


SQL_VERIF = ("select public.verificar_orcamento(%s::text,%s::text,%s::text,%s::text,"
             "%s::numeric,%s::numeric,%s::integer,%s::numeric,%s::numeric)")


def verificar(r, **mudancas):
    """Confere o orçamento r (resposta do cálculo), aplicando alterações opcionais."""
    d = {"id": r["id"], "emitido_em": r["emitido_em"], "empresa": r["empresa"], "referencia": r["referencia"],
         "largura": D(str(r["largura"])), "comprimento": D(str(r["comprimento"])), "quantidade": r["quantidade"],
         "sfa": D(str(r["sfa"])), "valor": D(str(r["valor_final"]))}
    d.update(mudancas)
    return admin_sql(SQL_VERIF, (d["id"], d["emitido_em"], d["empresa"], d["referencia"], d["largura"],
                                 d["comprimento"], d["quantidade"], d["sfa"], d["valor"]))


def admin_sql(sql, args=()):
    with como("authenticated", ADMIN) as c:
        return c.execute(sql, args).fetchone()[0]


def D(x):
    return Decimal(str(x))


# ---------------------------------------------------------------- testes
@teste("Sem parâmetros configurados: serviço indisponível e orçamento bloqueado")
def _():
    with como("anon") as c:
        assert c.execute("select public.servico_disponivel()").fetchone()[0] is False
    r = calcular(100, 100, 1, 75.38)
    assert r["ok"] is False and r["codigo"] == "indisponivel", r


@teste("Teste 7: usuário não autorizado (anônimo) não altera preços")
def _():
    with como("anon") as c:
        try:
            c.execute("select public.atualizar_parametros(1, 1)")
            raise AssertionError("anônimo conseguiu chamar atualizar_parametros")
        except psycopg.errors.InsufficientPrivilege:
            pass


@teste("Teste 7: usuário logado que NÃO é o Josias não altera nem lê preços")
def _():
    with como("authenticated", INTRUSO) as c:
        for sql in ("select public.atualizar_parametros(1, 1)", "select public.obter_parametros()",
                    "select public.verificar_orcamento('HJK-261110-AAAA-BBBBBBBBBB','10/11/2026 10:00','x','',1,1,1,1,1)"):
            try:
                c.execute(sql)
                raise AssertionError(f"intruso executou: {sql}")
            except psycopg.errors.InsufficientPrivilege:
                pass
        assert c.execute("select public.sou_administrador()").fetchone()[0] is False


@teste("Teste 5: administrador atualiza os parâmetros (preço 0,05/cm²; mínimo R$ 150,00)")
def _():
    r = admin_sql("select public.atualizar_parametros(0.05, 150)")
    assert D(r["preco_cm2"]) == D("0.05") and D(r["minimo_pedido"]) == D("150"), r
    assert admin_sql("select public.sou_administrador()") is True


@teste("Teste 6: parâmetros persistem em nova conexão (novo acesso)")
def _():
    r = admin_sql("select public.obter_parametros()")
    assert D(r["preco_cm2"]) == D("0.05") and D(r["minimo_pedido"]) == D("150"), r
    assert r["atualizado_em"]
    with como("anon") as c:
        assert c.execute("select public.servico_disponivel()").fetchone()[0] is True


@teste("Validação do administrador: preço zero/negativo e mínimo negativo recusados")
def _():
    for p, m in ((0, 10), (-1, 10), (0.05, -1), (0.0000001, 10), (0.05, 10.555)):
        try:
            admin_sql("select public.atualizar_parametros(%s::numeric, %s::numeric)", (p, m))
            raise AssertionError(f"aceitou {p}, {m}")
        except psycopg.errors.InvalidParameterValue:
            pass
    r = admin_sql("select public.obter_parametros()")
    assert D(r["preco_cm2"]) == D("0.05"), "valores válidos foram alterados indevidamente"


@teste("Teste 1: 100 × 100 mm, qtd 1, SFA 75,38% → área 75,38 cm²")
def _():
    r = calcular(100, 100, 1, 75.38)
    assert r["ok"], r
    assert D(r["area_placa"]) == D("75.38") and D(r["area_total"]) == D("75.38"), r


@teste("Teste 2: mesma placa, qtd 100 → área 7.538 cm²")
def _():
    r = calcular(100, 100, 100, 75.38)
    assert D(r["area_total"]) == D("7538.00"), r


@teste("Teste 3: preço por cm² aplicado (7.538 cm² × R$ 0,05 = R$ 376,90)")
def _():
    r = calcular(100, 100, 100, 75.38)
    assert D(r["valor_calculado"]) == D("376.90") and D(r["valor_final"]) == D("376.90"), r
    assert r["minimo_aplicado"] is False
    assert D(r["valor_unitario"]) == D("3.77"), r


@teste("Teste 4: mínimo aplicado (75,38 cm² × 0,05 = R$ 3,77 → R$ 150,00)")
def _():
    r = calcular(100, 100, 1, 75.38)
    assert D(r["valor_calculado"]) == D("3.77"), r
    assert D(r["valor_final"]) == D("150.00") and r["minimo_aplicado"] is True, r


@teste("Mínimo aplicado uma única vez ao pedido (não por placa)")
def _():
    r = calcular(100, 100, 30, 75.38)  # 2.261,4 cm² × 0,05 = 113,07 < 150
    assert D(r["valor_final"]) == D("150.00") and D(r["valor_unitario"]) == D("5.00"), r


@teste("Aceita decimais e SFA acima de 100% (até 200%)")
def _():
    r = calcular(D("50.5"), D("80.25"), 10, D("150.5"))
    # 50,5 × 80,25 × 150,5 / 10000 = 60,99... → por placa
    esperado = D("50.5") * D("80.25") * D("150.5") / 10000
    assert D(r["area_placa"]) == round(esperado, 2), r
    assert D(r["area_total"]) == round(esperado * 10, 2), r
    assert calcular(100, 100, 1, 200)["ok"] is True


@teste("Teste 9: entradas inválidas recusadas (vazias, negativas, zero, SFA > 200%)")
def _():
    casos = [(None, 100, 1, 50), (100, None, 1, 50), (100, 100, None, 50), (100, 100, 1, None),
             (-10, 100, 1, 50), (100, 0, 1, 50), (100, 100, 0, 50), (100, 100, -5, 50),
             (100, 100, 1, 0), (100, 100, 1, -1), (100, 100, 1, 200.01), (100, 100, 1, 250),
             (1001, 100, 1, 50), (100, 100, 1000001, 50), ("NaN", 100, 1, 50), ("Infinity", 100, 1, 50)]
    for caso in casos:
        r = calcular(*caso)
        assert r["ok"] is False and r["codigo"] == "entrada", (caso, r)


@teste("Teste 8: respostas públicas não contêm preço por cm² nem valor mínimo")
def _():
    r = calcular(100, 100, 100, 75.38)
    proibidas = {"preco_cm2", "minimo_pedido", "preco", "minimo"}
    assert not (proibidas & set(r.keys())), r.keys()
    with como("anon") as c:
        assert c.execute("select public.servico_disponivel()").fetchone()[0] in (True, False)


@teste("Teste 8: tabelas privadas inacessíveis por anon e por usuário comum")
def _():
    for papel, usuario in (("anon", None), ("authenticated", INTRUSO), ("authenticated", ADMIN)):
        for tabela in ("parametros", "segredo", "administradores", "limite_requisicoes"):
            with como(papel, usuario) as c:
                try:
                    c.execute(f"select * from privado.{tabela}")
                    raise AssertionError(f"{papel} leu privado.{tabela}")
                except psycopg.errors.InsufficientPrivilege:
                    pass
    with como("anon") as c:
        try:
            c.execute("select privado.codigo_verificacao('x',1,1,1,1,1)")
            raise AssertionError("anon chamou função interna")
        except psycopg.errors.InsufficientPrivilege:
            pass


@teste("Limite: 11ª consulta do mesmo visitante no mesmo minuto é bloqueada")
def _():
    ip = "203.0.113.7"
    for i in range(10):
        assert calcular(100, 100, 1, 50, ip=ip)["ok"], f"consulta {i + 1} bloqueada cedo demais"
    r = calcular(100, 100, 1, 50, ip=ip)
    assert r["ok"] is False and r["codigo"] == "limite", r
    assert calcular(100, 100, 1, 50, ip="203.0.113.8")["ok"], "outro visitante foi bloqueado"


@teste("Limite: IP do visitante não é armazenado em texto")
def _():
    with psycopg.connect(DSN) as c:
        chaves = [k for (k,) in c.execute("select chave from privado.limite_requisicoes")]
    assert chaves and not any("203.0.113" in k for k in chaves)


@teste("Limite diário global do site")
def _():
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("update privado.limite_requisicoes set contagem = 3000 where chave = 'dia'")
    r = calcular(100, 100, 1, 50)
    assert r["ok"] is False and r["codigo"] == "limite" and "diário" in r["erro"], r
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("update privado.limite_requisicoes set contagem = 0 where chave = 'dia'")


@teste("Identificador: formato HJK-AAMMDD-XXXX-XXXXXXXXXX (código de 40 bits) e data de emissão")
def _():
    import re
    r = calcular(100, 100, 100, 75.38)
    assert re.fullmatch(r"HJK-\d{6}-[0-9A-F]{4}-[0-9A-F]{10}", r["id"]), r["id"]
    assert re.fullmatch(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", r["emitido_em"]), r["emitido_em"]
    assert r["id"][4:10] == r["emitido_em"][8:10] + r["emitido_em"][3:5] + r["emitido_em"][0:2]


@teste("Verificação: orçamento autêntico é confirmado")
def _():
    r = calcular(100, 100, 100, 75.38)
    v = verificar(r)
    assert v["valido"] is True, v
    assert D(v["area_total"]) == D("7538.00") and D(v["valor_com_precos_atuais"]) == D("376.90"), v


@teste("Verificação: QUALQUER campo alterado é detectado (revisão Fernando, item 2)")
def _():
    r = calcular(100, 100, 100, 75.38)
    ultimo = r["id"][-1]
    alteracoes = {
        "valor": {"valor": D("300.00")},
        "quantidade": {"quantidade": 1000},
        "SFA": {"sfa": D("70")},
        "largura": {"largura": D("101")},
        "empresa": {"empresa": "Outra Empresa Ltda"},
        "referência": {"referencia": "PCB-99"},
        "hora de emissão": {"emitido_em": r["emitido_em"][:-2] + ("00" if r["emitido_em"][-2:] != "00" else "01")},
        "dia de emissão": {"emitido_em": ("01" if r["emitido_em"][:2] != "01" else "02") + r["emitido_em"][2:]},
        "código": {"id": r["id"][:-1] + ("0" if ultimo != "0" else "1")},
    }
    for nome, mud in alteracoes.items():
        v = verificar(r, **mud)
        assert v["valido"] is False, (nome, v)
    v = admin_sql("select public.verificar_orcamento('qualquer coisa','10/11/2026 10:00','x','',1,1,1,1,1)")
    assert v["valido"] is False and "formato" in v["motivo"]
    v = verificar(r, emitido_em="ontem")
    assert v["valido"] is False and "DD/MM/AAAA" in v["motivo"]


@teste("Verificação: empresa e referência normalizadas (espaços, formatação do WhatsApp)")
def _():
    r = calcular(100, 100, 10, 50, empresa="  Placas   *Rápidas*  Ltda ", ref="")
    assert r["empresa"] == "Placas Rápidas Ltda" and r["referencia"] == "", r
    assert verificar(r)["valido"] is True
    assert verificar(r, empresa="Placas Rápidas  Ltda", referencia="não informada")["valido"] is True
    assert verificar(r, empresa="placas rápidas ltda")["valido"] is False


@teste("Verificação: orçamento continua autêntico após mudança de preços")
def _():
    r = calcular(100, 100, 100, 75.38)
    admin_sql("select public.atualizar_parametros(0.06, 150)")
    v = verificar(r)
    assert v["valido"] is True and D(v["valor_com_precos_atuais"]) == D("452.28"), v
    admin_sql("select public.atualizar_parametros(0.05, 150)")


@teste("Empresa vazia ou textos longos recusados no servidor")
def _():
    for emp, ref in (("", "x"), ("   ", "x"), ("***", "x"), ("A" * 121, ""), ("A", "B" * 61)):
        r = calcular(100, 100, 1, 50, empresa=emp, ref=ref)
        assert r["ok"] is False and r["codigo"] == "entrada", (emp, ref, r)


@teste("Limite: x-forwarded-for forjado NÃO permite burlar o limite (revisão Fernando, item 1)")
def _():
    real = "198.51.100.50"
    for i in range(10):
        r = calcular(100, 100, 1, 50, headers={"cf-connecting-ip": real, "x-forwarded-for": f"1.1.1.{i}"})
        assert r["ok"], (i, r)
    r = calcular(100, 100, 1, 50, headers={"cf-connecting-ip": real, "x-forwarded-for": "9.9.9.9"})
    assert r["ok"] is False and r["codigo"] == "limite", r


@teste("Limite: sem cf-connecting-ip, todos compartilham um único contador (mais restritivo)")
def _():
    for i in range(10):
        assert calcular(100, 100, 1, 50, headers={"x-forwarded-for": f"2.2.2.{i}"})["ok"], i
    r = calcular(100, 100, 1, 50, headers={"x-forwarded-for": "3.3.3.3", "x-real-ip": "3.3.3.3"})
    assert r["ok"] is False and r["codigo"] == "limite", r
    with psycopg.connect(DSN) as c:
        d = c.execute("select cf_connecting_ip, x_forwarded_for, identificacao_usada from privado.diagnostico").fetchone()
    assert d[0] is False and d[1] is True and "AUSENTE" in d[2], d


@teste("Limite global por minuto do site (independe de cabeçalhos)")
def _():
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("insert into privado.limite_requisicoes values ('site-minuto', date_trunc('minute', now()), 120) "
                  "on conflict (chave, janela) do update set contagem = 120")
    r = calcular(100, 100, 1, 50)
    assert r["ok"] is False and r["codigo"] == "limite" and "neste momento" in r["erro"], r
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("delete from privado.limite_requisicoes where chave = 'site-minuto'")


@teste("Diagnóstico registra presença do cabeçalho sem guardar o IP")
def _():
    calcular(100, 100, 1, 50, ip="192.0.2.77")
    with psycopg.connect(DSN) as c:
        d = c.execute("select row_to_json(d)::text from privado.diagnostico d").fetchone()[0]
    assert '"cf_connecting_ip":true' in d and "por visitante" in d and "192.0.2.77" not in d, d


@teste("Arredondamento monetário consistente (meio centavo arredonda para cima)")
def _():
    admin_sql("select public.atualizar_parametros(0.000125, 0)")
    r = calcular(100, 100, 1, 100)  # 100 cm² × 0,000125 = 0,0125 → 0,01
    assert D(r["valor_calculado"]) == D("0.01"), r
    r = calcular(200, 100, 1, 100)  # 200 cm² × 0,000125 = 0,025 → 0,03
    assert D(r["valor_calculado"]) == D("0.03"), r
    admin_sql("select public.atualizar_parametros(0.05, 150)")


@teste("Script de instalação pode ser executado novamente sem perder os preços")
def _():
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute((RAIZ / "supabase/01_instalacao.sql").read_text())
    r = admin_sql("select public.obter_parametros()")
    assert D(r["preco_cm2"]) == D("0.05") and D(r["minimo_pedido"]) == D("150"), r


# ---------------------------------------------------------------- relatório
ok = sum(1 for r in resultados if r[0])
print(f"\nTESTES DO BANCO — {ok}/{len(resultados)} aprovados\n")
for passou, nome, erro in resultados:
    print(("  [OK]   " if passou else "  [FALHA] ") + nome + (f"\n          {erro}" if erro else ""))
sys.exit(0 if ok == len(resultados) else 1)
