// Se a imagem da logomarca não estiver disponível, mostra o nome em texto.
(function () {
  var img = document.getElementById("logo");
  var txt = document.getElementById("logo-texto");
  if (!img || !txt) return;
  function falhou() { img.hidden = true; txt.hidden = false; }
  img.addEventListener("error", falhou);
  if (img.complete && img.naturalWidth === 0) falhou();
})();
