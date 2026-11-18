// Área administrativa v2.0: login, recuperação/alteração de senha,
// parâmetros de custo, simulador e conferência de orçamentos.
(function () {
  "use strict";
  var CFG = window.HJK_CONFIG;
  var H = window.HJK;
  var $ = function (id) { return document.getElementById(id); };

  // Modo de recuperação: o link do e-mail traz "type=recovery" no endereço.
  var hashInicial = window.location.hash || "";
  var modoRecuperacao = /type=recovery/.test(hashInicial);
  var erroNoLink = /error_code=|error=/.test(hashInicial);

  // Sessão só nesta aba (sessionStorage): fechar o navegador encerra o acesso.
  // flowType "implicit": o link de recuperação funciona mesmo aberto em outra aba.
  var sb = window.supabase.createClient(CFG.SUPABASE_URL, CFG.SUPABASE_CHAVE_PUBLICA, {
    auth: { storage: window.sessionStorage, persistSession: true, autoRefreshToken: true,
            detectSessionInUrl: true, flowType: "implicit" }
  });

  var configAtual = null;     // última configuração carregada do servidor
  var senhaPorRecuperacao = false;

  // ------------------------------------------------------------ utilidades
  function aviso(texto, tipo) {
    var a = $("aviso");
    a.textContent = texto || "";
    a.className = "aviso " + (tipo || "erro");
    a.hidden = !texto;
    if (texto) a.scrollIntoView({ block: "nearest" });
  }

  function ocupado(btn, sim, textoOcupado) {
    if (sim) { btn.dataset.texto = btn.textContent; btn.textContent = textoOcupado; btn.disabled = true; }
    else { btn.textContent = btn.dataset.texto || btn.textContent; btn.disabled = false; }
  }

  function el(tag, attrs, filhos) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "texto") e.textContent = attrs[k];
      else if (k === "classe") e.className = attrs[k];
      else e.setAttribute(k, attrs[k]);
    });
    (filhos || []).forEach(function (f) { if (f) e.appendChild(f); });
    return e;
  }

  function mostrar(qual) {
    ["form-login", "form-esqueci", "form-nova-senha", "painel"].forEach(function (id) {
      $(id).hidden = id !== qual;
    });
  }

  function limparEndereco() {
    if (window.location.href.indexOf("#") >= 0) history.replaceState(null, "", window.location.pathname + window.location.search);
  }

  function msgErro(err) {
    if (!err) return "Erro desconhecido.";
    if (err.code === "42501") return "Sem permissão. Entre novamente.";
    return err.message || String(err);
  }

  // ------------------------------------------------------------ login e senha
  function entrarNoPainel(sessao) {
    return sb.rpc("sou_administrador").then(function (res) {
      if (res.error) throw res.error;
      if (res.data !== true) {
        aviso("Este usuário não tem permissão de administrador.");
        return sb.auth.signOut().then(function () { mostrar("form-login"); });
      }
      $("usuario-email").textContent = (sessao && sessao.user && sessao.user.email) || "";
      mostrar("painel");
      return carregarConfiguracao();
    });
  }

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

  $("btn-esqueci").addEventListener("click", function () {
    aviso("");
    $("email-recuperar").value = $("email").value.trim();
    mostrar("form-esqueci");
    $("email-recuperar").focus();
  });
  $("btn-voltar-login").addEventListener("click", function () { aviso(""); mostrar("form-login"); });

  $("form-esqueci").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var email = $("email-recuperar").value.trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { aviso("Informe um e-mail válido."); return; }
    var btn = $("btn-enviar-link");
    ocupado(btn, true, "Enviando…");
    var destino = window.location.origin + window.location.pathname;
    sb.auth.resetPasswordForEmail(email, { redirectTo: destino }).then(function (res) {
      if (res.error && /rate|many|seconds/i.test(res.error.message)) {
        aviso("Muitas solicitações em pouco tempo. Aguarde alguns minutos e tente de novo.");
        return;
      }
      // Mensagem neutra: não revela se o e-mail está cadastrado.
      aviso("Se este e-mail for de um administrador, você receberá em instantes um link para criar uma senha nova. " +
            "Confira também a caixa de spam. O link vale por tempo limitado.", "ok");
      mostrar("form-login");
    }).catch(function () { aviso("Não foi possível enviar agora. Tente novamente em alguns minutos."); })
      .then(function () { ocupado(btn, false); });
  });

  function abrirNovaSenha(porRecuperacao) {
    senhaPorRecuperacao = porRecuperacao;
    $("nova-senha").value = ""; $("nova-senha-2").value = "";
    $("btn-cancelar-senha").hidden = porRecuperacao;
    mostrar("form-nova-senha");
    $("nova-senha").focus();
  }

  $("btn-alterar-senha").addEventListener("click", function () { aviso(""); abrirNovaSenha(false); });
  $("btn-cancelar-senha").addEventListener("click", function () { aviso(""); mostrar("painel"); });

  $("form-nova-senha").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var s1 = $("nova-senha").value, s2 = $("nova-senha-2").value;
    if (s1.length < 10) { aviso("A senha precisa ter pelo menos 10 caracteres."); return; }
    if (s1 !== s2) { aviso("As duas senhas não são iguais."); return; }
    var btn = $("btn-salvar-senha");
    ocupado(btn, true, "Salvando…");
    sb.auth.updateUser({ password: s1 }).then(function (res) {
      if (res.error) {
        aviso(/same|different/i.test(res.error.message) ? "A nova senha precisa ser diferente da anterior."
          : /session|expired|jwt/i.test(res.error.message) ? "O link expirou. Peça um novo em “Esqueci minha senha”."
          : "Não foi possível salvar a senha: " + res.error.message);
        return;
      }
      $("nova-senha").value = ""; $("nova-senha-2").value = "";
      limparEndereco();
      aviso("Senha alterada com sucesso.", "ok");
      return sb.auth.getSession().then(function (r) { return entrarNoPainel(r.data && r.data.session); });
    }).catch(function () { aviso("Não foi possível salvar a senha. Verifique a conexão."); })
      .then(function () { ocupado(btn, false); });
  });

  $("btn-sair").addEventListener("click", function () {
    sb.auth.signOut().then(function () { aviso("Você saiu da administração.", "info"); mostrar("form-login"); });
  });

  // ------------------------------------------------------------ configuração
  var GRUPOS = [
    ["producao", "Produção e mão de obra"],
    ["comercial", "Comercial"],
    ["camada", "Camada de ouro (formulário do cliente)"],
    ["tecnico", "Fatores técnicos"]
  ];

  // Formato para campos editáveis: vírgula decimal e SEM separador de milhar
  // (evita que "1.500" seja lido como 1,5).
  function fmt(v, casas) {
    return Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: casas, useGrouping: false });
  }

  function campoNumero(id, valor, casas) {
    return el("input", { id: id, type: "text", inputmode: "decimal", autocomplete: "off", value: fmt(valor, casas) });
  }

  function montarConfiguracao(cfg) {
    configAtual = cfg;
    var raiz = $("config");
    raiz.textContent = "";
    $("config-data").textContent = cfg.atualizado_em ? "Última alteração: " + cfg.atualizado_em + "." : "";

    // Materiais
    raiz.appendChild(el("h3", { classe: "grupo-titulo", texto: "Materiais e químicos" }));
    raiz.appendChild(el("p", { classe: "dica", texto:
      "Consumo por grama de sal de ouro. “Acompanha o ouro”: varia com a camada pedida. " +
      "“Acompanha a área”: calculado na camada de referência, só depende da área." }));
    var tbody = el("tbody");
    (cfg.quimicos || []).forEach(function (q) {
      var tr = el("tr", { "data-codigo": q.codigo });
      tr.appendChild(el("td", { texto: q.nome }));
      if (q.tipo === "consumo") {
        var sel = el("select", { "data-campo": "base", "aria-label": "Base de " + q.nome }, [
          el("option", { value: "ouro", texto: "Acompanha o ouro" }),
          el("option", { value: "area", texto: "Acompanha a área" })]);
        sel.value = q.base;
        tr.appendChild(el("td", { classe: "num" }, [el("input", { type: "text", inputmode: "decimal", autocomplete: "off",
          "data-campo": "preco", "aria-label": "Preço de " + q.nome, value: fmt(q.preco, 4) })]));
        tr.appendChild(el("td", { classe: "num" }, [el("input", { type: "text", inputmode: "decimal", autocomplete: "off",
          "data-campo": "consumo", "aria-label": "Consumo de " + q.nome, value: fmt(q.consumo, 6) })]));
        tr.appendChild(el("td", { texto: q.unidade ? q.unidade + "/g" : "" }));
        tr.appendChild(el("td", {}, [sel]));
      } else {
        var refNome = ((cfg.quimicos || []).filter(function (x) { return x.codigo === q.referencia; })[0] || {}).nome || q.referencia;
        tr.appendChild(el("td", { classe: "num", texto: "—" }));
        tr.appendChild(el("td", { classe: "num" }, [el("input", { type: "text", inputmode: "decimal", autocomplete: "off",
          "data-campo": "percentual", "aria-label": "Percentual de " + q.nome, value: fmt(q.percentual, 4) })]));
        tr.appendChild(el("td", { texto: "% de " + refNome }));
        tr.appendChild(el("td", { texto: "Segue " + refNome }));
      }
      tbody.appendChild(tr);
    });
    raiz.appendChild(el("div", { classe: "tabela-wrap" }, [el("table", { classe: "tabela", id: "tabela-quimicos" }, [
      el("thead", {}, [el("tr", {}, [el("th", { texto: "Material" }), el("th", { classe: "num", texto: "Preço (R$)" }),
        el("th", { classe: "num", texto: "Consumo" }), el("th", { texto: "Unid." }), el("th", { texto: "Base" })])]),
      tbody])]));

    // Parâmetros por grupo
    GRUPOS.forEach(function (g) {
      var itens = (cfg.parametros || []).filter(function (p) { return p.grupo === g[0]; });
      if (!itens.length) return;
      raiz.appendChild(el("h3", { classe: "grupo-titulo", texto: g[1] }));
      var grade = el("div", { classe: "grade-3" });
      itens.forEach(function (p) {
        var id = "p-" + p.chave;
        var lbl = el("label", { for: id, texto: p.rotulo + " " }, [el("span", { classe: "unid", texto: "(" + p.unidade + ")" })]);
        var inp = campoNumero(id, p.valor, p.casas);
        inp.setAttribute("data-chave", p.chave);
        grade.appendChild(el("div", { classe: "campo" }, [lbl, inp, p.ajuda ? el("p", { classe: "dica", texto: p.ajuda }) : null]));
      });
      raiz.appendChild(grade);
    });
  }

  function carregarConfiguracao() {
    return sb.rpc("obter_configuracao").then(function (res) {
      if (res.error) throw res.error;
      montarConfiguracao(res.data || {});
      // Simulador começa com a camada padrão
      var pad = (res.data.parametros || []).filter(function (p) { return p.chave === "camada_padrao"; })[0];
      if (pad) $("s-camada").value = fmt(pad.valor, 3);
    });
  }

  function lerConfiguracaoDaTela() {
    var erros = [], parametros = {}, quimicos = [];
    (configAtual.parametros || []).forEach(function (p) {
      var v = H.lerDecimal($("p-" + p.chave).value);
      if (isNaN(v)) erros.push(p.rotulo);
      else if (v !== Number(p.valor)) parametros[p.chave] = v;
    });
    var linhas = $("tabela-quimicos").querySelectorAll("tr[data-codigo]");
    Array.prototype.forEach.call(linhas, function (tr) {
      var codigo = tr.getAttribute("data-codigo");
      var orig = (configAtual.quimicos || []).filter(function (q) { return q.codigo === codigo; })[0];
      var item = { codigo: codigo }, mudou = false;
      Array.prototype.forEach.call(tr.querySelectorAll("[data-campo]"), function (inp) {
        var campo = inp.getAttribute("data-campo");
        var v = campo === "base" ? inp.value : H.lerDecimal(inp.value);
        if (campo !== "base" && isNaN(v)) { erros.push(orig.nome + " (" + campo + ")"); return; }
        if (campo === "base" ? v !== orig.base : v !== Number(orig[campo])) { item[campo] = v; mudou = true; }
      });
      if (mudou) quimicos.push(item);
    });
    return { erros: erros, parametros: parametros, quimicos: quimicos };
  }

  $("form-config").addEventListener("submit", function (ev) {
    ev.preventDefault();
    aviso("");
    var d = lerConfiguracaoDaTela();
    if (d.erros.length) { aviso("Valores inválidos em: " + d.erros.join(", ") + "."); return; }
    var n = Object.keys(d.parametros).length + d.quimicos.length;
    if (!n) { aviso("Nenhuma alteração para salvar.", "info"); return; }
    var btn = $("btn-salvar-config");
    ocupado(btn, true, "Salvando…");
    sb.rpc("salvar_configuracao", { p_parametros: d.parametros, p_quimicos: d.quimicos }).then(function (res) {
      if (res.error) { aviso("Nada foi salvo. " + msgErro(res.error)); return; }
      montarConfiguracao(res.data);
      aviso("Alterações salvas (" + n + " " + (n === 1 ? "item" : "itens") + "). Já valem para os próximos orçamentos.", "ok");
    }).catch(function () { aviso("Não foi possível salvar. Verifique a conexão."); })
      .then(function () { ocupado(btn, false); });
  });

  $("btn-desfazer").addEventListener("click", function () {
    if (configAtual) { montarConfiguracao(configAtual); aviso("Alterações não salvas foram descartadas.", "info"); }
  });

  // ------------------------------------------------------------ simulador
  function linha(rotulo, valor, classe) {
    return el("tr", classe ? { classe: classe } : {}, [el("td", { texto: rotulo }), el("td", { classe: "num", texto: valor })]);
  }

  $("form-simular").addEventListener("submit", function (ev) {
    ev.preventDefault();
    aviso("");
    var args = {
      p_largura: H.lerDecimal($("s-largura").value), p_comprimento: H.lerDecimal($("s-comprimento").value),
      p_quantidade: H.lerInteiro($("s-quantidade").value), p_sfa: H.lerDecimal($("s-sfa").value),
      p_camada: H.lerDecimal($("s-camada").value)
    };
    if (Object.keys(args).some(function (k) { return isNaN(args[k]); })) { aviso("Preencha a simulação com números válidos."); return; }
    var btn = $("btn-simular");
    ocupado(btn, true, "Calculando…");
    sb.rpc("simular_orcamento", args).then(function (res) {
      if (res.error) { aviso(msgErro(res.error)); return; }
      var r = res.data, box = $("sim-resultado");
      if (!r.ok) { aviso(r.erro); box.hidden = true; return; }
      var tb = el("tbody");
      tb.appendChild(linha("Área ENIG total", H.numero(r.area_total, 2, 2) + " cm²"));
      tb.appendChild(linha("Sal de ouro (aurocianeto)", H.numero(r.sal_ouro_g, 3, 5) + " g"));
      (r.itens || []).forEach(function (i) { tb.appendChild(linha("   " + i.nome, H.moeda(i.custo))); });
      tb.appendChild(linha("Químicos", H.moeda(r.quimicos), "total"));
      tb.appendChild(linha("Mão de obra (" + H.numero(r.paineis, 0, 0) + " painéis → " + H.numero(r.horas, 0, 0) + " h)", H.moeda(r.mao_de_obra)));
      tb.appendChild(linha("Custo fixo", H.moeda(r.custo_fixo)));
      tb.appendChild(linha("Custo total", H.moeda(r.custo), "total"));
      tb.appendChild(linha("Margem", H.moeda(r.margem_valor)));
      tb.appendChild(linha("Tributos", H.moeda(r.tributos_valor)));
      tb.appendChild(linha("Preço calculado", H.moeda(r.valor_calculado), "total"));
      if (r.minimo_aplicado) tb.appendChild(linha("Valor mínimo por pedido aplicado", ""));
      tb.appendChild(linha("Valor final do orçamento", H.moeda(r.valor_final), "destaque"));
      tb.appendChild(linha("Por placa", H.moeda(r.valor_unitario)));
      box.textContent = "";
      if (r.aviso) box.appendChild(el("p", { classe: "aviso info", texto: "Atenção: o cliente não conseguiria pedir esta simulação. " + r.aviso }));
      box.appendChild(el("div", { classe: "tabela-wrap" }, [el("table", { classe: "tabela", id: "tabela-simulacao" }, [tb])]));
      box.hidden = false;
    }).catch(function () { aviso("Não foi possível simular. Verifique a conexão."); })
      .then(function () { ocupado(btn, false); });
  });

  // ------------------------------------------------------------ conferência
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
    $("v-camada").value = d.camada;
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
      p_camada: H.lerDecimal($("v-camada").value),
      p_valor: H.lerDecimal($("v-valor").value)
    };
    var faltando = Object.keys(dados).filter(function (k) {
      return (k !== "p_referencia" && dados[k] === "") || (typeof dados[k] === "number" && isNaN(dados[k]));
    });
    if (faltando.length) { aviso("Preencha todos os campos da conferência com valores válidos."); return; }
    var btn = $("btn-verificar");
    ocupado(btn, true, "Verificando…");
    sb.rpc("verificar_orcamento", dados).then(function (res) {
      if (res.error) { aviso(msgErro(res.error)); return; }
      var r = res.data, box = $("verif-resultado");
      box.className = "verif-resultado " + (r.valido ? "valido" : "invalido");
      box.textContent = "";
      box.appendChild(el("h3", { texto: r.valido ? "✔ Orçamento autêntico" : "✖ Orçamento não confere" }));
      var linhas = [r.motivo];
      if (r.emitido_em) linhas.push("Emitido em: " + r.emitido_em);
      if (r.area_total != null) linhas.push("Área total ENIG: " + H.numero(r.area_total, 2, 2) + " cm²");
      if (r.valor_informado != null) linhas.push("Valor informado: " + H.moeda(r.valor_informado));
      if (r.valor_com_precos_atuais != null) linhas.push("Valor com os preços atuais: " + H.moeda(r.valor_com_precos_atuais));
      linhas.forEach(function (t) { box.appendChild(el("p", { texto: t })); });
      box.hidden = false;
    }).catch(function () { aviso("Não foi possível verificar. Verifique a conexão."); })
      .then(function () { ocupado(btn, false); });
  });

  // ------------------------------------------------------------ início
  sb.auth.onAuthStateChange(function (evento) {
    if (evento === "PASSWORD_RECOVERY") { modoRecuperacao = true; abrirNovaSenha(true); }
  });

  if (erroNoLink) {
    limparEndereco();
    aviso("O link de recuperação é inválido ou expirou. Peça um novo em “Esqueci minha senha”.");
  }

  sb.auth.getSession().then(function (res) {
    var sessao = res.data && res.data.session;
    if (modoRecuperacao && sessao) { abrirNovaSenha(true); return; }
    if (sessao) return entrarNoPainel(sessao).catch(function () { mostrar("form-login"); });
    mostrar("form-login");
  }).catch(function () {
    mostrar("form-login");
    aviso("Não foi possível conectar ao serviço.");
  });
})();
