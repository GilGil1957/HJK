// Testes das funções do navegador (leitura de números, validação, mensagem).
// Uso: node testes/testar_funcoes.js
"use strict";
const assert = require("assert");
const H = require("../js/comum.js");

const resultados = [];
function teste(nome, fn) {
  try { fn(); resultados.push([true, nome, ""]); }
  catch (e) { resultados.push([false, nome, e.message]); }
}

teste("Aceita vírgula e ponto decimal", () => {
  assert.strictEqual(H.lerDecimal("75,38"), 75.38);
  assert.strictEqual(H.lerDecimal("75.38"), 75.38);
  assert.strictEqual(H.lerDecimal(" 100 "), 100);
  assert.strictEqual(H.lerDecimal("75,38%"), 75.38);
  assert.strictEqual(H.lerDecimal("1.234,56"), 1234.56);
  assert.strictEqual(H.lerDecimal("1,234.56"), 1234.56);
});

teste("Recusa números inválidos", () => {
  for (const s of ["", "abc", "-5", "1,2,3", "1.2.3", "12a", ",", "1e5", null, undefined]) {
    assert.ok(Number.isNaN(H.lerDecimal(s)), "aceitou: " + s);
  }
});

teste("Quantidade aceita só inteiros positivos", () => {
  assert.strictEqual(H.lerInteiro("100"), 100);
  for (const s of ["1,5", "1.000", "-3", "", "abc"]) assert.ok(Number.isNaN(H.lerInteiro(s)), "aceitou: " + s);
});

const valido = { empresa: "Eletrônica Teste Ltda", referencia: "PCB-01", quantidade: "100",
                 largura: "100", comprimento: "100", sfa: "75,38" };

teste("Formulário válido passa", () => {
  const v = H.validarFormulario(valido);
  assert.ok(v.ok, JSON.stringify(v.erros));
  assert.strictEqual(v.dados.sfa, 75.38);
});

teste("Teste 9: campos vazios, negativos e fora do intervalo são recusados", () => {
  const casos = [
    [{ empresa: "" }, "empresa"], [{ empresa: "   " }, "empresa"],
    [{ quantidade: "" }, "quantidade"], [{ quantidade: "0" }, "quantidade"], [{ quantidade: "-1" }, "quantidade"],
    [{ quantidade: "2,5" }, "quantidade"], [{ largura: "" }, "largura"], [{ largura: "-10" }, "largura"],
    [{ largura: "0" }, "largura"], [{ comprimento: "1001" }, "comprimento"], [{ largura: "10,123" }, "largura"],
    [{ sfa: "" }, "sfa"], [{ sfa: "0" }, "sfa"], [{ sfa: "200,01" }, "sfa"], [{ sfa: "250" }, "sfa"],
    [{ sfa: "-5" }, "sfa"], [{ referencia: "x".repeat(61) }, "referencia"]
  ];
  for (const [alteracao, campo] of casos) {
    const v = H.validarFormulario(Object.assign({}, valido, alteracao));
    assert.ok(!v.ok && v.erros[campo], "não recusou " + JSON.stringify(alteracao));
  }
  assert.ok(H.validarFormulario(Object.assign({}, valido, { sfa: "200" })).ok, "200% deveria ser aceito");
  assert.ok(H.validarFormulario(Object.assign({}, valido, { referencia: "" })).ok, "referência é opcional");
});

const resp = { id: "HJK-261110-A3F9-7B1E40C2D9", emitido_em: "10/11/2026 13:05",
               empresa: "Eletrônica Teste Ltda", referencia: "PCB-01", largura: 100, comprimento: 100,
               quantidade: 100, sfa: 75.38, area_placa: 75.38, area_total: 7538, valor_calculado: 376.9,
               valor_final: 376.9, valor_unitario: 3.77, minimo_aplicado: false };

teste("Teste 10: mensagem do WhatsApp com todos os dados", () => {
  const m = H.montarMensagem(resp);
  for (const trecho of ["*HJK GALVANOPLASTIA — SOLICITAÇÃO DE ENIG*", "Orçamento: HJK-261110-A3F9-7B1E40C2D9",
    "Emitido em: 10/11/2026 13:05", "Empresa: Eletrônica Teste Ltda", "Referência da placa: PCB-01",
    "Quantidade: 100", "Dimensões: 100 × 100 mm", "Surface Finish Area (HQ DFM): 75,38%",
    "Área total ENIG: 7.538,00 cm²", "Valor do orçamento: R$ 376,90",
    "Solicitamos a execução do serviço conforme o orçamento apresentado."]) {
    assert.ok(m.includes(trecho), "faltou: " + trecho + "\n" + m);
  }
  assert.ok(!m.includes("mínimo"));
});

teste("Mensagem indica mínimo aplicado e referência não informada", () => {
  const m = H.montarMensagem(Object.assign({}, resp, { referencia: "", valor_final: 150, minimo_aplicado: true }));
  assert.ok(m.includes("Referência da placa: não informada"));
  assert.ok(m.includes("Valor do orçamento: R$ 150,00"));
  assert.ok(m.includes("(Valor mínimo por pedido aplicado)"));
});

teste("Teste 10: link abre o WhatsApp oficial da HJK com o texto codificado", () => {
  const m = H.montarMensagem(Object.assign({}, resp, { empresa: "A & B", referencia: "#1" }));
  const url = H.linkWhatsApp("5511971651268", m);
  assert.ok(url.startsWith("https://wa.me/5511971651268?text="));
  assert.strictEqual(decodeURIComponent(url.split("?text=")[1]), m);
});

teste("Valor exibido e valor da mensagem usam a mesma formatação", () => {
  for (const v of [0.01, 3.77, 150, 376.9, 1234.5, 98765.43]) {
    const m = H.montarMensagem(Object.assign({}, resp, { valor_final: v }));
    assert.ok(m.includes("Valor do orçamento: " + H.moeda(v)), v);
  }
  assert.strictEqual(H.moeda(1234.5), "R$ 1.234,50");
});

teste("Leitura da mensagem colada para conferência (ida e volta)", () => {
  const r2 = Object.assign({}, resp, { empresa: "Placas & Cia: Filial 2", referencia: "REF: A-7",
    largura: 50.5, comprimento: 80.25, quantidade: 1500, sfa: 150.5, valor_final: 1234.56 });
  const d = H.extrairDaMensagem(H.montarMensagem(r2));
  assert.strictEqual(d.id, resp.id);
  assert.strictEqual(d.emitido_em, "10/11/2026 13:05");
  assert.strictEqual(d.empresa, "Placas & Cia: Filial 2");
  assert.strictEqual(d.referencia, "REF: A-7");
  assert.strictEqual(H.extrairDaMensagem(H.montarMensagem(Object.assign({}, r2, { referencia: "" }))).referencia, "");
  assert.strictEqual(H.lerDecimal(d.largura), 50.5);
  assert.strictEqual(H.lerDecimal(d.comprimento), 80.25);
  assert.strictEqual(H.lerInteiro(d.quantidade), 1500);
  assert.strictEqual(H.lerDecimal(d.sfa), 150.5);
  assert.strictEqual(H.lerDecimal(d.valor), 1234.56);
});

const ok = resultados.filter(r => r[0]).length;
console.log(`\nTESTES DAS FUNÇÕES DO NAVEGADOR — ${ok}/${resultados.length} aprovados\n`);
for (const [p, n, e] of resultados) console.log((p ? "  [OK]   " : "  [FALHA] ") + n + (e ? "\n          " + e : ""));
process.exit(ok === resultados.length ? 0 : 1);
