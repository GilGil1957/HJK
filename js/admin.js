// Área administrativa: login (Supabase Auth), preços e conferência de orçamentos.
(function () {
  "use strict";
  var CFG = window.HJK_CONFIG;
  var H = window.HJK;
  var $ = function (id) { return document.getElementById(id); };

  // A sessão fica só nesta aba (sessionStorage): fechar o navegador encerra o acesso.
  var sb = window.supabase.createClient(CFG.SUPABASE_URL, CFG.SUPABASE_CHAVE_PUBLICA, {
    auth: { storage: window.sessionStorage, persistSession: true, autoRefreshToken: true, detectSessionInUrl: false }
  });

  function aviso(texto, tipo) {
    var a = $("aviso");
    a.textContent = texto || "";
    a.className = "aviso " + (tipo || "erro");
    a.hidden = !texto;
  }

  function ocupado(btn, sim, textoOcupado) {
    if (sim) { btn.dataset.texto = btn.textContent; btn.textContent = textoOcupado; btn.disabled = true; }
    else { btn.textContent = btn.dataset.texto || btn.textContent; btn.disabled = false; }
  }

  function mostrarLogin() {
    $("painel").hidden = true;
    $("form-login").hidden = false;
  }

  function precoCm2(v) {
    return "R$ " + H.numero(v, 2, 6);
  }

  function carregarParametros() {
    return sb.rpc("obter_parametros").then(function (res) {
      if (res.error) throw res.error;
      var p = res.data || {};
      $("atual-preco").textContent = p.preco_cm2 === null || p.preco_cm2 === undefined ? "não configurado" : precoCm2(p.preco_cm2);
      $("atual-minimo").textContent = p.minimo_pedido === null || p.minimo_pedido === undefined ? "não configurado" : H.moeda(p.minimo_pedido);
      $("atual-data").textContent = p.atualizado_em ? "Última alteração: " + p.atualizado_em
        : "Os preços ainda não foram configurados. Enquanto isso, os clientes não conseguem emitir orçamentos.";
    });
  }

  function entrarNoPainel(sessao) {
    return sb.rpc("sou_administrador").then(function (res) {
      if (res.error) throw res.error;
      if (res.data !== true) {
        aviso("Este usuário não tem permissão de administrador.");
        return sb.auth.signOut().then(mostrarLogin);
      }
      $("usuario-email").textContent = sessao.user.email || "";
      $("form-login").hidden = true;
      $("painel").hidden = false;
      return carregarParametros();
    });
  }

  // Login
  $("form-login").addEventListener("submit", function (ev) {
    ev.preventDefault();
    aviso("");
    var email = $("email").value.trim(), senha = $("senha").value;
    if (!email || !senha) { aviso("Informe e-mail e senha."); return; }
    var btn = $("btn-entrar");
    ocupado(btn, true, "Entrando…");
    sb.auth.signInWithPassword({ email: email, password: senha }).then(function (res) {
      if (res.error) {
        aviso(/rate|many/i.test(res.error.message) ? "Muitas tentativas. Aguarde alguns minutos." : "E-mail ou senha incorretos.");
        return;
      }
      $("senha").value = "";
      return entrarNoPainel(res.data.session);
    }).catch(function () {
      aviso("Não foi possível conectar. Verifique a internet ou se o serviço está ativo.");
    }).then(function () { ocupado(btn, false); });
  });

  $("btn-sair").addEventListener("click", function () {
    sb.auth.signOut().then(function () { aviso("Você saiu da administração.", "info"); mostrarLogin(); });
  });

  // Preços
  $("form-precos").addEventListener("submit", function (ev) {
    ev.preventDefault();
    aviso("");
    var preco = H.lerDecimal($("novo-preco").value);
    var minimo = H.lerDecimal($("novo-minimo").value);
    if (isNaN(preco) || preco <= 0) { aviso("Informe um preço por cm² válido, maior que zero (ex.: 0,05)."); return; }
    if (isNaN(minimo) || minimo < 0) { aviso("Informe um valor mínimo válido (ex.: 150,00)."); return; }
    var btn = $("btn-salvar");
    ocupado(btn, true, "Salvando…");
    sb.rpc("atualizar_parametros", { p_preco_cm2: preco, p_minimo_pedido: minimo }).then(function (res) {
      if (res.error) {
        aviso(res.error.code === "42501" ? "Sem permissão. Entre novamente." : res.error.message);
        return;
      }
      $("novo-preco").value = "";
      $("novo-minimo").value = "";
      aviso("Preços salvos: " + precoCm2(preco) + " por cm² e mínimo de " + H.moeda(minimo) + ".", "ok");
      return carregarParametros();
    }).catch(function () { aviso("Não foi possível salvar. Verifique a conexão."); })
      .then(function () { ocupado(btn, false); });
  });

  // Conferência de orçamento
  $("btn-ler").addEventListener("click", function () {
    var d = H.extrairDaMensagem($("msg-colada").value);
    $("v-id").value = d.id;
    $("v-emitido").value = d.emitido_em;
    $("v-empresa").value = d.empresa;
    $("v-referencia").value = d.referencia;
    $("v-largura").value = d.largura;
    $("v-comprimento").value = d.comprimento;
    $("v-quantidade").value = d.quantidade;
    $("v-sfa").value = d.sfa;
    $("v-valor").value = d.valor;
    $("verif-resultado").hidden = true;
    if (!d.id) aviso("Não encontrei o número do orçamento na mensagem. Confira o texto colado.");
    else aviso("");
  });

  $("form-verificar").addEventListener("submit", function (ev) {
    ev.preventDefault();
    aviso("");
    var dados = {
      p_id: $("v-id").value.trim(),
      p_emitido_em: $("v-emitido").value.trim(),
      p_empresa: $("v-empresa").value.trim(),
      p_referencia: $("v-referencia").value.trim(),
      p_largura: H.lerDecimal($("v-largura").value),
      p_comprimento: H.lerDecimal($("v-comprimento").value),
      p_quantidade: H.lerInteiro(String($("v-quantidade").value).replace(/\./g, "")),
      p_sfa: H.lerDecimal($("v-sfa").value),
      p_valor: H.lerDecimal($("v-valor").value)
    };
    var faltando = Object.keys(dados).filter(function (k) { return (k !== "p_referencia" && dados[k] === "") || (typeof dados[k] === "number" && isNaN(dados[k])); });
    if (faltando.length) { aviso("Preencha todos os campos da conferência com valores válidos."); return; }
    var btn = $("btn-verificar");
    ocupado(btn, true, "Verificando…");
    sb.rpc("verificar_orcamento", dados).then(function (res) {
      if (res.error) { aviso(res.error.code === "42501" ? "Sem permissão. Entre novamente." : res.error.message); return; }
      var r = res.data, box = $("verif-resultado");
      box.className = "verif-resultado " + (r.valido ? "valido" : "invalido");
      box.innerHTML = "";
      var h = document.createElement("h3");
      h.textContent = r.valido ? "✔ Orçamento autêntico" : "✖ Orçamento não confere";
      box.appendChild(h);
      var linhas = [r.motivo];
      if (r.emitido_em) linhas.push("Emitido em: " + r.emitido_em);
      if (r.area_total !== undefined) linhas.push("Área total ENIG: " + H.numero(r.area_total, 2, 2) + " cm²");
      if (r.valor_informado !== undefined) linhas.push("Valor informado: " + H.moeda(r.valor_informado));
      if (r.valor_com_precos_atuais !== null && r.valor_com_precos_atuais !== undefined)
        linhas.push("Valor com os preços atuais: " + H.moeda(r.valor_com_precos_atuais));
      linhas.forEach(function (t) { var p = document.createElement("p"); p.textContent = t; box.appendChild(p); });
      box.hidden = false;
    }).catch(function () { aviso("Não foi possível verificar. Verifique a conexão."); })
      .then(function () { ocupado(btn, false); });
  });

  // Início: retoma sessão existente desta aba, se houver.
  sb.auth.getSession().then(function (res) {
    var sessao = res.data && res.data.session;
    if (sessao) return entrarNoPainel(sessao).catch(mostrarLogin);
    mostrarLogin();
  }).catch(function () {
    mostrarLogin();
    aviso("Não foi possível conectar ao serviço.");
  });
})();
