"""
Testes automatizados do banco de dados — versão 2.0.

Executa o script de instalação num PostgreSQL local que simula o Supabase e
compara o cálculo do servidor com uma implementação independente em Python
(valores FICTÍCIOS do próprio script). Verifica também administração,
validações, segurança, limites contra robôs e conferência de orçamentos.

Uso:  python3 testes/testar_banco.py "host=/tmp port=5433 user=postgres"
"""
import json
import math
import re
import sys
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path

import psycopg

RAIZ = Path(__file__).resolve().parent.parent
DSN_BASE = sys.argv[1] if len(sys.argv) > 1 else "host=/tmp port=5433 user=postgres"
BANCO = "hjk_teste_v2"
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

_ip = [0]


def novo_ip():
    _ip[0] += 1
    return f"10.1.{_ip[0] // 250}.{_ip[0] % 250}"


def como(papel, usuario=None, ip=None, headers=None):
    c = psycopg.connect(DSN, autocommit=True)
    if headers is None:
        headers = {"cf-connecting-ip": ip or novo_ip()}
    c.execute("select set_config('request.headers', %s, false)", (json.dumps(headers),))
    c.execute("select set_config('request.jwt.claim.sub', %s, false)", (str(usuario) if usuario else "",))
    c.execute(f"set role {papel}")
    return c


EMPRESA, REF = "Eletrônica Teste Ltda", "PCB-01"


def calcular(l, cmp, q, s, k=D("0.09"), ip=None, empresa=EMPRESA, ref=REF, headers=None, papel="anon"):
    with como(papel, ip=ip, headers=headers) as c:
        return c.execute("select public.calcular_orcamento(%s::text,%s::text,%s::numeric,%s::numeric,%s::integer,%s::numeric,%s::numeric)",
                         (empresa, ref, l, cmp, q, s, k)).fetchone()[0]


def admin(sql, args=()):
    with como("authenticated", ADMIN) as c:
        return c.execute(sql, args).fetchone()[0]


def salvar(parametros=None, quimicos=None):
    return admin("select public.salvar_configuracao(%s::jsonb, %s::jsonb)",
                 (json.dumps(parametros or {}), json.dumps(quimicos or [])))


def simular(l, cmp, q, s, k):
    return admin("select public.simular_orcamento(%s::numeric,%s::numeric,%s::integer,%s::numeric,%s::numeric)",
                 (l, cmp, q, s, k))


def ler_config():
    with psycopg.connect(DSN) as c:
        cfg = {k: D(str(v)) for k, v in c.execute("select chave, valor from privado.config")}
        qs = [dict(zip(("codigo", "tipo", "preco", "consumo", "base", "referencia", "percentual", "ordem"), r))
              for r in c.execute("select codigo, tipo, preco, consumo, base, referencia, percentual, ordem from privado.quimicos order by ordem")]
    return cfg, qs


def r2(x):
    return D(x).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def referencia(l, cmp, q, s, k):
    """Implementação independente do modelo de preço (para comparação)."""
    cfg, qs = ler_config()
    l, cmp, s, k = D(str(l)), D(str(cmp)), D(str(s)), D(str(k))
    area = l * cmp * s / 10000 * q
    fator = cfg["densidade"] * cfg["fator_sal"] / 10000
    sal_ouro, sal_ref = area * k * fator, area * cfg["camada_ref"] * fator
    custos, quim = {}, D(0)
    for it in qs:
        if it["tipo"] == "consumo":
            v = D(str(it["preco"])) * D(str(it["consumo"])) * (sal_ouro if it["base"] == "ouro" else sal_ref)
            custos[it["codigo"]] = v
            quim += v
    for it in qs:
        if it["tipo"] == "indexado":
            quim += custos.get(it["referencia"], D(0)) * D(str(it["percentual"])) / 100
    paineis = math.ceil(l * cmp / 100 * q / (cfg["painel_largura"] * cfg["painel_comprimento"] / 100))
    horas = math.ceil(D(paineis) / cfg["paineis_hora"] + cfg["horas_adicionais"])
    custo = quim + horas * cfg["valor_hora"] + cfg["custo_fixo"]
    preco = r2(custo * (1 + cfg["margem"] / 100) / (1 - cfg["tributos"] / 100))
    final = max(preco, cfg["minimo_pedido"])
    return dict(area=r2(area), paineis=paineis, horas=horas, custo=r2(custo), calculado=preco, final=final)


# ======================================================================
@teste("Instalação: 15 parâmetros e 11 materiais com valores FICTÍCIOS")
def _():
    cfg, qs = ler_config()
    assert len(cfg) == 15 and len(qs) == 11, (len(cfg), len(qs))
    assert cfg["camada_min"] == D("0.03") and cfg["camada_padrao"] == D("0.09") and cfg["camada_max"] == D("0.10")
    assert cfg["margem"] == 50 and cfg["tributos"] == 15
    assert [q["codigo"] for q in qs if q["base"] == "ouro"] == ["aurocianeto"]


@teste("Dados públicos do formulário: só disponibilidade e limites da camada")
def _():
    with como("anon") as c:
        d = c.execute("select public.dados_formulario()").fetchone()[0]
    assert set(d) == {"disponivel", "camada_min", "camada_padrao", "camada_max"}, d
    assert d["disponivel"] is True and D(str(d["camada_padrao"])) == D("0.09")


@teste("Cálculo igual ao modelo independente (vários casos)")
def _():
    casos = [(100, 100, 1, D("75.38"), D("0.09")), (100, 100, 100, D("75.38"), D("0.09")),
             (245, 47, 210, D("8.49"), D("0.09")), (80.5, 120, 250, D("132.4"), D("0.05")),
             (50, 50, 5000, D("200"), D("0.10")), (1000, 1000, 3, D("12.5"), D("0.03"))]
    for caso in casos:
        r = calcular(*caso)
        e = referencia(*caso)
        assert r["ok"], (caso, r)
        assert D(str(r["area_total"])) == e["area"], (caso, r["area_total"], e)
        assert D(str(r["valor_calculado"])) == e["calculado"], (caso, r["valor_calculado"], e)
        assert D(str(r["valor_final"])) == e["final"], (caso, r, e)


@teste("Teste 1/2 da missão: 100×100 mm, 75,38% → 75,38 cm² (qtd 1) e 7.538 cm² (qtd 100)")
def _():
    assert D(str(calcular(100, 100, 1, D("75.38"))["area_total"])) == D("75.38")
    assert D(str(calcular(100, 100, 100, D("75.38"))["area_total"])) == D("7538.00")


@teste("Camada maior → preço maior; só o aurocianeto acompanha o ouro")
def _():
    a = simular(100, 100, 100, D("75.38"), D("0.05"))
    b = simular(100, 100, 100, D("75.38"), D("0.10"))
    assert D(str(b["valor_final"])) > D(str(a["valor_final"]))
    ia = {i["codigo"]: D(str(i["custo"])) for i in a["itens"]}
    ib = {i["codigo"]: D(str(i["custo"])) for i in b["itens"]}
    assert ib["aurocianeto"] == r2(ia["aurocianeto"] * 2) or abs(ib["aurocianeto"] - ia["aurocianeto"] * 2) <= D("0.01")
    for cod in ia:
        if cod != "aurocianeto":
            assert ia[cod] == ib[cod], cod


@teste("Painéis e horas arredondados para cima (mínimo 2 h com +1)")
def _():
    r = simular(245, 141, 1, D("10"), D("0.09"))      # exatamente 1 painel
    assert r["paineis"] == 1 and r["horas"] == 2, r
    r = simular(245, 141, 41, D("10"), D("0.09"))     # 41 painéis → 41/40+1 = 2,025 → 3 h
    assert r["paineis"] == 41 and r["horas"] == 3, r
    r = simular(100, 100, 1, D("10"), D("0.09"))      # fração de painel conta como 1
    assert r["paineis"] == 1


@teste("Tributos por dentro: preço − tributos = custo com margem")
def _():
    r = simular(100, 100, 100, D("75.38"), D("0.09"))
    preco, custo = D(str(r["valor_calculado"])), D(str(r["custo"]))
    cfg, _ = ler_config()
    assert abs(preco * (1 - cfg["tributos"] / 100) - custo * (1 + cfg["margem"] / 100)) <= D("0.02"), r


@teste("Simulador: composição soma o custo total")
def _():
    r = simular(100, 100, 100, D("75.38"), D("0.09"))
    soma_itens = sum(D(str(i["custo"])) for i in r["itens"])
    assert abs(soma_itens - D(str(r["quimicos"]))) <= D("0.06"), (soma_itens, r["quimicos"])
    assert abs(D(str(r["quimicos"])) + D(str(r["mao_de_obra"])) + D(str(r["custo_fixo"])) - D(str(r["custo"]))) <= D("0.02")


@teste("Valor mínimo por pedido aplicado uma vez ao pedido")
def _():
    salvar({"minimo_pedido": 5000})
    r = calcular(100, 100, 10, D("75.38"))
    assert D(str(r["valor_final"])) == D("5000.00") and r["minimo_aplicado"] is True, r
    assert D(str(r["valor_unitario"])) == D("500.00")
    salvar({"minimo_pedido": 0})
    assert calcular(100, 100, 10, D("75.38"))["minimo_aplicado"] is False


@teste("Administrador altera parâmetros e materiais; persistem em nova conexão")
def _():
    salvar({"margem": 60, "valor_hora": 55.5}, [{"codigo": "aurocianeto", "preco": 510.25},
                                                {"codigo": "parte_a", "base": "ouro", "consumo": 0.333}])
    cfg = admin("select public.obter_configuracao()")
    p = {x["chave"]: D(str(x["valor"])) for x in cfg["parametros"]}
    q = {x["codigo"]: x for x in cfg["quimicos"]}
    assert p["margem"] == 60 and p["valor_hora"] == D("55.5")
    assert D(str(q["aurocianeto"]["preco"])) == D("510.25") and q["parte_a"]["base"] == "ouro"
    assert D(str(q["parte_a"]["consumo"])) == D("0.333") and cfg["atualizado_em"]
    salvar({"margem": 50, "valor_hora": 50}, [{"codigo": "aurocianeto", "preco": 500},
                                              {"codigo": "parte_a", "base": "area", "consumo": 0.3}])


@teste("Salvar é tudo-ou-nada: um valor inválido não altera nada")
def _():
    antes = admin("select public.obter_configuracao()")
    for par, qui in (({"margem": 70, "tributos": 100}, []), ({"margem": 70}, [{"codigo": "parte_b", "preco": -1}]),
                     ({"camada_padrao": 0.2}, []), ({"inexistente": 1}, []), ({"margem": "abc"}, []),
                     ({"custo_fixo": 1.234}, []), ({}, [{"codigo": "parte_b", "base": "cobre"}]),
                     ({}, [{"codigo": "xyz", "preco": 1}])):
        try:
            salvar(par, qui)
            raise AssertionError(f"aceitou {par} {qui}")
        except psycopg.errors.InvalidParameterValue:
            pass
    depois = admin("select public.obter_configuracao()")
    assert antes["parametros"] == depois["parametros"] and antes["quimicos"] == depois["quimicos"]


@teste("Limites da camada vêm do administrador (mín. 0,03 / máx. 0,10 → editável)")
def _():
    assert calcular(100, 100, 1, D("50"), D("0.03"))["ok"] and calcular(100, 100, 1, D("50"), D("0.10"))["ok"]
    for k in (D("0.029"), D("0.101"), D("0.5"), D("0")):
        r = calcular(100, 100, 1, D("50"), k)
        assert r["ok"] is False and "camada" in r["erro"].lower(), (k, r)
    salvar({"camada_max": 0.125})
    assert calcular(100, 100, 1, D("50"), D("0.12"))["ok"]
    salvar({"camada_max": 0.10})


@teste("Teste 9: entradas inválidas recusadas no servidor")
def _():
    casos = [(None, 100, 1, 50), (100, None, 1, 50), (100, 100, None, 50), (100, 100, 1, None),
             (-10, 100, 1, 50), (100, 0, 1, 50), (100, 100, 0, 50), (100, 100, 1, 0), (100, 100, 1, 200.01),
             (1001, 100, 1, 50), (100, 100, 1000001, 50), ("NaN", 100, 1, 50), ("Infinity", 100, 1, 50)]
    for caso in casos:
        r = calcular(*caso)
        assert r["ok"] is False and r["codigo"] == "entrada", (caso, r)
    assert calcular(100, 100, 1, 50, None)["codigo"] == "entrada"
    for emp, ref in (("", "x"), ("***", "x"), ("A" * 121, ""), ("A", "B" * 61)):
        assert calcular(100, 100, 1, 50, empresa=emp, ref=ref)["codigo"] == "entrada"


@teste("Teste 8: resposta pública sem nenhum custo, margem, tributo ou composição")
def _():
    r = calcular(100, 100, 100, D("75.38"))
    proibidas = {"itens", "quimicos", "custo", "mao_de_obra", "custo_fixo", "margem_valor", "tributos_valor",
                 "sal_ouro_g", "paineis", "horas", "preco", "consumo"}
    assert not (proibidas & set(r)), set(r) & proibidas


@teste("Teste 7/8: anônimo e usuário comum não acessam funções de administrador nem tabelas")
def _():
    for papel, usuario in (("anon", None), ("authenticated", INTRUSO)):
        with como(papel, usuario) as c:
            for sql in ("select public.obter_configuracao()",
                        "select public.salvar_configuracao('{\"margem\":1}'::jsonb, '[]'::jsonb)",
                        "select public.simular_orcamento(1,1,1,1,0.09)",
                        "select public.verificar_orcamento('HJK-261118-AAAA-BBBBBBBBBB','18/11/2026 10:00','x','',1,1,1,1,0.09,1)"):
                try:
                    c.execute(sql)
                    raise AssertionError(f"{papel} executou {sql}")
                except psycopg.errors.InsufficientPrivilege:
                    pass
        for tab in ("config", "quimicos", "segredo", "administradores", "limite_requisicoes"):
            with como(papel, usuario) as c:
                try:
                    c.execute(f"select * from privado.{tab}")
                    raise AssertionError(f"{papel} leu {tab}")
                except psycopg.errors.InsufficientPrivilege:
                    pass
    with como("authenticated", INTRUSO) as c:
        assert c.execute("select public.sou_administrador()").fetchone()[0] is False


@teste("Funções da versão 1.x removidas (preço por cm² não existe mais)")
def _():
    with psycopg.connect(DSN) as c:
        n = c.execute("select count(*) from pg_proc where proname in ('obter_parametros','atualizar_parametros')").fetchone()[0]
        t = c.execute("select to_regclass('privado.parametros')").fetchone()[0]
    assert n == 0 and t is None


@teste("Identificador HJK-AAMMDD-XXXX-XXXXXXXXXX e mensagem coerente")
def _():
    r = calcular(100, 100, 100, D("75.38"))
    assert re.fullmatch(r"HJK-\d{6}-[0-9A-F]{4}-[0-9A-F]{10}", r["id"])
    assert D(str(r["camada"])) == D("0.090")


def verificar(r, **m):
    d = dict(id=r["id"], emitido=r["emitido_em"], empresa=r["empresa"], ref=r["referencia"],
             l=D(str(r["largura"])), c=D(str(r["comprimento"])), q=r["quantidade"], s=D(str(r["sfa"])),
             k=D(str(r["camada"])), v=D(str(r["valor_final"])))
    d.update(m)
    return admin("select public.verificar_orcamento(%s::text,%s::text,%s::text,%s::text,%s::numeric,%s::numeric,"
                 "%s::integer,%s::numeric,%s::numeric,%s::numeric)",
                 (d["id"], d["emitido"], d["empresa"], d["ref"], d["l"], d["c"], d["q"], d["s"], d["k"], d["v"]))


@teste("Conferência: autêntico confirmado; qualquer campo alterado (inclusive a camada) detectado")
def _():
    r = calcular(100, 100, 100, D("75.38"), D("0.07"))
    v = verificar(r)
    assert v["valido"] is True and D(str(v["valor_com_precos_atuais"])) == D(str(r["valor_final"])), v
    for nome, m in {"camada": {"k": D("0.09")}, "valor": {"v": D("1.00")}, "empresa": {"empresa": "Outra"},
                    "quantidade": {"q": 101}, "sfa": {"s": D("70")}, "hora": {"emitido": "01/01/2026 00:00"},
                    "código": {"id": r["id"][:-1] + ("0" if r["id"][-1] != "0" else "1")}}.items():
        assert verificar(r, **m)["valido"] is False, nome
    assert verificar(r, k=D("0.070"))["valido"] is True


@teste("Limites contra robôs: 11ª consulta bloqueada; x-forwarded-for forjado não burla")
def _():
    real = "198.51.100.77"
    for i in range(10):
        assert calcular(100, 100, 1, 50, headers={"cf-connecting-ip": real, "x-forwarded-for": f"1.1.1.{i}"})["ok"], i
    r = calcular(100, 100, 1, 50, headers={"cf-connecting-ip": real, "x-forwarded-for": "9.9.9.9"})
    assert r["ok"] is False and r["codigo"] == "limite", r


@teste("Simulador do administrador não consome o limite e avisa camada fora da faixa")
def _():
    for _ in range(15):
        simular(100, 100, 1, 50, D("0.09"))
    r = simular(100, 100, 1, 50, D("0.2"))
    assert r["ok"] is True and r["aviso"] and "camada" in r["aviso"].lower(), r


@teste("Script pode ser executado novamente sem perder valores do administrador")
def _():
    salvar({"margem": 42}, [{"codigo": "paladio", "preco": 123.45}])
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute((RAIZ / "supabase/01_instalacao.sql").read_text())
    cfg, qs = ler_config()
    assert cfg["margem"] == 42 and [q for q in qs if q["codigo"] == "paladio"][0]["preco"] == D("123.45")
    salvar({"margem": 50}, [{"codigo": "paladio", "preco": 250}])


ok = sum(1 for r in resultados if r[0])
print(f"\nTESTES DO BANCO (v2.0) — {ok}/{len(resultados)} aprovados\n")
for passou, nome, erro in resultados:
    print(("  [OK]   " if passou else "  [FALHA] ") + nome + (f"\n          {erro}" if erro else ""))
sys.exit(0 if ok == len(resultados) else 1)
