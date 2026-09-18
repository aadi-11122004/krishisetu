/* KrishiSetu — client helpers (progressive enhancement only; all core
   features work without JS). */
(function () {
  // auto-dismiss toasts
  document.querySelectorAll(".toast").forEach(function (t) {
    setTimeout(function () {
      t.style.transition = "opacity .5s, transform .5s";
      t.style.opacity = "0";
      t.style.transform = "translateY(-6px)";
      setTimeout(function () { t.remove(); }, 500);
    }, 4200);
  });

  // animated delivery vehicle on the route map (tracking page)
  var mapWrap = document.querySelector(".map-wrap.anim svg");
  if (mapWrap) {
    var line = mapWrap.querySelector("polyline");
    if (line && line.getTotalLength) {
      var NS = "http://www.w3.org/2000/svg";
      var dot = document.createElementNS(NS, "circle");
      dot.setAttribute("r", "7");
      dot.setAttribute("fill", "#1b5e20");
      dot.setAttribute("stroke", "#f9a825");
      dot.setAttribute("stroke-width", "3");
      mapWrap.appendChild(dot);
      var len = line.getTotalLength();
      var start = null, DUR = 14000;
      function frame(ts) {
        if (!start) start = ts;
        var t = ((ts - start) % DUR) / DUR;          // 0..1 loop
        var p = line.getPointAtLength(t * len);
        dot.setAttribute("cx", p.x);
        dot.setAttribute("cy", p.y);
        requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    }
  }

  // marketplace search: submit on Enter is native; add tiny debounce for select auto-apply
  var form = document.getElementById("filterForm");
  if (form) {
    form.querySelectorAll("select, input[type=checkbox]").forEach(function (el) {
      el.addEventListener("change", function () { form.submit(); });
    });
  }
})();
