// Funções compartilhadas: leitura de números, formatação brasileira,
// mensagem do WhatsApp e leitura de mensagem para conferência.
(function (raiz) {
  "use strict";

  // Converte texto digitado em número. Aceita vírgula ou ponto decimal
  // ("75,38", "75.38") e separador de milhar quando ambos aparecem
  // ("1.234,56", "1,234.56"). Devolve NaN se inválido.
  function lerDecimal(texto) {
    if (texto === null || texto === undefined) return NaN;
    var s = String(texto).trim().replace(/\s+/g, "").replace(/%$/, "");
    if (s === "" || !/^[0-9.,]+$/.test(s)) return NaN;
    var ultVirgula = s.lastIndexOf(","), ultPonto = s.lastIndexOf(".");
    if (ultVirgula >= 0 && ultPonto >= 0) {
      var dec = ultVirgula > ultPonto ? "," : ".";
      var mil = dec === "," ? "." : ",";
      s = s.split(mil).join("");
      if (s.split(dec).length > 2) return NaN;
      s = s.replace(dec, ".");
    } else if (ultVirgula >= 0) {
      if (s.split(",").length > 2) return NaN;
      s = s.replace(",", ".");
    } else if (s.split(".").length > 2) {
      return NaN;
    }
    if (!/^\d*\.?\d+$|^\d+\.$/.test(s)) return NaN;
    return Number(s);
  }

  // Quantidade: somente dígitos (inteiro positivo).
  function lerInteiro(texto) {
    var s = String(texto === null || texto === undefined ? "" : texto).trim();
    if (!/^\d+$/.test(s)) return NaN;
    return parseInt(s, 10);
  }

  function casasDecimais(n) {
    var s = String(n);
    var i = s.indexOf(".");
    return i < 0 ? 0 : s.length - i - 1;
  }

  var fmtMoeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

  function moeda(v) {
    // Intl usa espaço não separável; trocamos por espaço comum para o WhatsApp.
    return fmtMoeda.format(Number(v)).replace(/ /g, " ");
  }

  function numero(v, min, max) {
    return new Intl.NumberFormat("pt-BR", {
      minimumFractionDigits: min === undefined ? 0 : min,
      maximumFractionDigits: max === undefined ? 2 : max
    }).format(Number(v));
  }

  // Valida o formulário. Devolve { ok, erros: {campo: msg}, dados }.
  function validarFormulario(f) {
    var erros = {};
    var empresa = String(f.empresa || "").trim();
    var referencia = String(f.referencia || "").trim();
    var largura = lerDecimal(f.largura);
    var comprimento = lerDecimal(f.comprimento);
    var quantidade = lerInteiro(f.quantidade);
    var sfa = lerDecimal(f.sfa);

    if (!empresa) erros.empresa = "Informe o nome da empresa.";
    else if (empresa.length > 120) erros.empresa = "Use no máximo 120 caracteres.";
    if (referencia.length > 60) erros.referencia = "Use no máximo 60 caracteres.";

    if (String(f.quantidade || "").trim() === "") erros.quantidade = "Informe a quantidade de placas.";
    else if (isNaN(quantidade)) erros.quantidade = "Use apenas números inteiros, sem pontos ou vírgulas.";
    else if (quantidade < 1 || quantidade > 1000000) erros.quantidade = "A quantidade deve estar entre 1 e 1.000.000.";

    [["largura", largura, "a largura"], ["comprimento", comprimento, "o comprimento"]].forEach(function (c) {
      if (String(f[c[0]] || "").trim() === "") erros[c[0]] = "Informe " + c[2] + " em milímetros.";
      else if (isNaN(c[1])) erros[c[0]] = "Número inválido. Exemplo: 100 ou 100,5.";
      else if (c[1] < 1 || c[1] > 1000) erros[c[0]] = "Deve estar entre 1 e 1.000 mm.";
      else if (casasDecimais(c[1]) > 2) erros[c[0]] = "Use no máximo 2 casas decimais.";
    });

    if (String(f.sfa || "").trim() === "") erros.sfa = "Informe o percentual Surface Finish Area.";
    else if (isNaN(sfa)) erros.sfa = "Número inválido. Exemplo: 75,38.";
    else if (sfa <= 0 || sfa > 200) erros.sfa = "Deve ser maior que 0% e no máximo 200%.";
    else if (casasDecimais(sfa) > 2) erros.sfa = "Use no máximo 2 casas decimais.";

    return {
      ok: Object.keys(erros).length === 0,
      erros: erros,
      dados: { empresa: empresa, referencia: referencia, largura: largura,
               comprimento: comprimento, quantidade: quantidade, sfa: sfa }
    };
  }

  // Monta a mensagem do WhatsApp SOMENTE com os valores devolvidos pelo
  // servidor (inclusive empresa e referência normalizadas), que são os
  // mesmos cobertos pelo código de verificação.
  function montarMensagem(r) {
    var linhas = [
      "*HJK GALVANOPLASTIA — SOLICITAÇÃO DE ENIG*",
      "",
      "Orçamento: " + r.id,
      "Emitido em: " + r.emitido_em,
      "",
      "Empresa: " + r.empresa,
      "Referência da placa: " + (r.referencia || "não informada"),
      "Quantidade: " + numero(r.quantidade, 0, 0),
      "Dimensões: " + numero(r.largura) + " × " + numero(r.comprimento) + " mm",
      "Surface Finish Area (HQ DFM): " + numero(r.sfa) + "%",
      "Área total ENIG: " + numero(r.area_total, 2, 2) + " cm²",
      "Valor do orçamento: " + moeda(r.valor_final)
    ];
    if (r.minimo_aplicado) linhas.push("(Valor mínimo por pedido aplicado)");
    linhas.push("", "Solicitamos a execução do serviço conforme o orçamento apresentado.");
    return linhas.join("\n");
  }

  function linkWhatsApp(numeroTel, mensagem) {
    return "https://wa.me/" + numeroTel + "?text=" + encodeURIComponent(mensagem);
  }

  // Lê uma mensagem colada do WhatsApp e extrai os dados para conferência.
  function extrairDaMensagem(texto) {
    var t = String(texto || "").replace(/\*/g, "").replace(/ /g, " ");
    function achar(re) { var m = t.match(re); return m ? m[1].trim() : ""; }
    var dim = t.match(/Dimens[õo]es:\s*([\d.,]+)\s*[×xX*]\s*([\d.,]+)/);
    var ref = achar(/Refer[êe]ncia da placa:[ \t]*([^\n]*)/);
    return {
      id: achar(/(HJK-\d{6}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{10})/).toUpperCase(),
      emitido_em: achar(/Emitido em:\s*(\d{2}\/\d{2}\/\d{4} \d{2}:\d{2})/),
      empresa: achar(/Empresa:[ \t]*([^\n]*)/),
      referencia: /^n[ãa]o informada$/i.test(ref) ? "" : ref,
      quantidade: achar(/Quantidade:\s*([\d.]+)/).replace(/\./g, ""),
      largura: dim ? dim[1] : "",
      comprimento: dim ? dim[2] : "",
      sfa: achar(/Surface Finish Area[^:]*:\s*([\d.,]+)/),
      valor: achar(/Valor do or[çc]amento:\s*R\$\s*([\d.,]+)/)
    };
  }

  var api = { lerDecimal: lerDecimal, lerInteiro: lerInteiro, moeda: moeda, numero: numero,
              validarFormulario: validarFormulario, montarMensagem: montarMensagem,
              linkWhatsApp: linkWhatsApp, extrairDaMensagem: extrairDaMensagem };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.HJK = api;
})(typeof window !== "undefined" ? window : this);
