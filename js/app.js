// Página do cliente: formulário, cálculo no servidor e envio ao WhatsApp.
(function () {
  "use strict";
  var CFG = window.HJK_CONFIG;
  var H = window.HJK;
  var CAMPOS = ["empresa", "referencia", "quantidade", "largura", "comprimento", "sfa"];

  var $ = function (id) { return document.getElementById(id); };
  var form = $("form-orcamento");
  var btnCalcular = $("btn-calcular");
  var aviso = $("aviso");
  var resultado = $("resultado");
  var ultimoCliente = null;
  var versaoFormulario = 0;

  function rpc(nome, args) {
    var headers = { "Content-Type": "application/json", apikey: CFG.SUPABASE_CHAVE_PUBLICA };
    // Chaves antigas ("anon", formato JWT) também precisam do cabeçalho Authorization.
    if (/^eyJ/.test(CFG.SUPABASE_CHAVE_PUBLICA)) headers.Authorization = "Bearer " + CFG.SUPABASE_CHAVE_PUBLICA;
    return fetch(CFG.SUPABASE_URL.replace(/\/$/, "") + "/rest/v1/rpc/" + nome, {
      method: "POST", headers: headers, body: JSON.stringify(args || {})
    }).then(function (resp) {
      return resp.json().catch(function () { return null; }).then(function (corpo) {
        if (!resp.ok) {
          var e = new Error((corpo && corpo.message) || ("Erro " + resp.status));
          e.status = resp.status;
          throw e;
        }
        return corpo;
      });
    });
  }

  function mostrarAviso(texto, tipo) {
    aviso.textContent = texto;
    aviso.className = "aviso " + (tipo || "erro");
    aviso.hidden = !texto;
  }

  function limparErros() {
    CAMPOS.forEach(function (c) {
      $("erro-" + c).textContent = "";
      $(c).removeAttribute("aria-invalid");
    });
  }

  function esconderResultado() {
    resultado.hidden = true;
    ultimoCliente = null;
    versaoFormulario++;
  }

  function erroConexao() {
    mostrarAviso("Não foi possível conectar ao serviço de orçamentos. Verifique sua internet e tente novamente " +
      "em alguns minutos. Se o problema continuar, fale com a HJK pelo WhatsApp.");
  }

  function exibir(cliente, r) {
    $("r-id").textContent = r.id;
    $("r-data").textContent = r.emitido_em;
    $("r-area-placa").textContent = H.numero(r.area_placa, 2, 2) + " cm²";
    $("r-area-total").textContent = H.numero(r.area_total, 2, 2) + " cm²";
    $("r-valor-calculado").textContent = H.moeda(r.valor_calculado);
    $("r-valor-final").textContent = H.moeda(r.valor_final);
    $("r-unitario").textContent = H.moeda(r.valor_unitario) + (r.quantidade > 1 ? " (aprox.)" : "");
    $("r-minimo").hidden = !r.minimo_aplicado;
    $("btn-whatsapp").href = H.linkWhatsApp(CFG.WHATSAPP_NUMERO, H.montarMensagem(r));
    resultado.hidden = false;
    ultimoCliente = cliente;
    resultado.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    limparErros();
    mostrarAviso("");
    esconderResultado();

    var valores = {};
    CAMPOS.forEach(function (c) { valores[c] = $(c).value; });
    var v = H.validarFormulario(valores);
    if (!v.ok) {
      Object.keys(v.erros).forEach(function (c) {
        $("erro-" + c).textContent = v.erros[c];
        $(c).setAttribute("aria-invalid", "true");
      });
      $(Object.keys(v.erros)[0]).focus();
      return;
    }

    var versaoSolicitada = versaoFormulario;
    btnCalcular.disabled = true;
    btnCalcular.textContent = "Calculando…";
    rpc("calcular_orcamento", {
      p_empresa: v.dados.empresa, p_referencia: v.dados.referencia,
      p_largura: v.dados.largura, p_comprimento: v.dados.comprimento,
      p_quantidade: v.dados.quantidade, p_sfa: v.dados.sfa
    }).then(function (r) {
      if (versaoSolicitada !== versaoFormulario) return;
      if (r && r.ok) exibir(v.dados, r);
      else mostrarAviso((r && r.erro) || "Não foi possível calcular o orçamento.");
    }).catch(function () {
      if (versaoSolicitada === versaoFormulario) erroConexao();
    }).then(function () {
      btnCalcular.disabled = false;
      btnCalcular.textContent = "Calcular orçamento";
    });
  });

  // Qualquer alteração depois do cálculo invalida o resultado exibido,
  // garantindo que a tela e o WhatsApp mostrem sempre os mesmos valores.
  CAMPOS.forEach(function (c) {
    // Também invalida um cálculo ainda pendente (a resposta antiga é descartada).
    $(c).addEventListener("input", esconderResultado);
  });

  $("btn-novo").addEventListener("click", function () {
    form.reset();
    limparErros();
    mostrarAviso("");
    esconderResultado();
    window.scrollTo({ top: 0, behavior: "smooth" });
    $("empresa").focus();
  });

  // Verifica se o serviço está disponível (preços configurados).
  rpc("servico_disponivel").then(function (disponivel) {
    if (disponivel !== true) {
      btnCalcular.disabled = true;
      mostrarAviso("O serviço de orçamento ainda não está disponível. Entre em contato com a HJK pelo WhatsApp.", "info");
    }
  }).catch(erroConexao);
})();
