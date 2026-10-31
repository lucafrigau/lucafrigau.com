// Map of international activities (About page): each marker has a panel with
// the details of its activities, written by scripts/travel_map.py. The panel
// opens when the pointer is over the marker (and stays while the pointer is
// on the panel), when the marker has the keyboard focus, and after a tap or a
// click, which keeps it open until Escape, another tap or a click elsewhere.
// Only one panel is open at a time, and it is placed so that it stays inside
// the window. Without this script the markers keep a native tooltip, and the
// list below the maps gives the same details.
(function () {
  "use strict";
  var stages = document.querySelectorAll(".travel-map .tm-stage");
  if (!stages.length) return;

  var GAP = 10;    // space between the marker and the panel, in pixels
  var EDGE = 6;    // minimum space between the panel and the edges
  var REACH = 24;  // a tap selects the nearest marker within this distance
  var RANK = { pointer: 1, focus: 2, pin: 3 };
  var open = null; // { mark, tip, via: "pointer", "focus" or "pin" }
  var timer = null;

  function shapeOf(mark) {
    return mark.querySelector(".tm-talk, .tm-visit");
  }

  // Each map has two layers of markers, for wide and narrow maps; theme.scss
  // hides one of them. The computed style tells which: some browsers still
  // give a size to the shapes of a hidden SVG group, and let them be focused.
  function shown(mark) {
    return getComputedStyle(mark.parentNode).display !== "none";
  }

  // Only the markers of the layer shown are buttons, in the keyboard order and
  // for screen readers; run again when the layer changes.
  function sync() {
    document.querySelectorAll(".travel-map .tm-mark").forEach(function (mark) {
      if (shown(mark)) {
        mark.setAttribute("tabindex", "0");
        mark.setAttribute("role", "button");
        mark.setAttribute("aria-label", mark.getAttribute("data-label"));
        mark.setAttribute("aria-describedby", mark.getAttribute("data-tip"));
        mark.removeAttribute("aria-hidden");
      } else {
        ["tabindex", "role", "aria-label", "aria-describedby"].forEach(function (name) {
          mark.removeAttribute(name);
        });
        mark.setAttribute("aria-hidden", "true");
      }
    });
  }

  // The panel goes above the marker if it fits, else below, else beside it
  // (on wide maps), else on the side with more room: after a tap or with the
  // keyboard (scroll = true) the page then scrolls so that the panel fits.
  // Horizontally it stays inside the map, or inside the window when it is
  // wider than the map allows.
  function place(mark, tip, scroll) {
    var s = tip.parentNode.getBoundingClientRect();
    var m = shapeOf(mark).getBoundingClientRect();
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var vw = document.documentElement.clientWidth;
    // The navigation bar stays at the top of the window and comes back when
    // the page scrolls up: its height is always left free.
    var header = document.getElementById("quarto-header");
    var fixed = header && /fixed|sticky/.test(getComputedStyle(header).position);
    var top = (fixed ? header.offsetHeight : 0) + EDGE;
    // On phones the visible part of the page changes while the address bar
    // of the browser hides or shows: visualViewport follows it.
    var view = window.visualViewport;
    var bottom = (view ? view.offsetTop + view.height : window.innerHeight) - EDGE;
    var cx = m.left + m.width / 2, cy = m.top + m.height / 2;
    var side = m.top - GAP - h >= top ? "above" : m.bottom + GAP + h <= bottom ? "below"
      : m.right + GAP + w <= Math.min(s.right, vw) - EDGE ? "right"
      : m.left - GAP - w >= Math.max(s.left, 0) + EDGE ? "left" : null;
    if (!side) {
      var down = bottom - m.bottom >= m.top - top;
      var shift = Math.min(h + GAP - (down ? bottom - m.bottom : m.top - top), down ? m.top - top : bottom - m.bottom);
      if (scroll && shift > 1) {
        window.scrollBy({ top: down ? shift : -shift, behavior: "instant" });
        return place(mark, tip, false);
      }
      side = down ? "below" : "above";
    }
    var x, y, arrow;
    if (side === "right" || side === "left") {
      x = side === "right" ? m.right + GAP : m.left - GAP - w;
      y = Math.max(top, Math.min(cy - h / 2, bottom - h));
      arrow = Math.max(14, Math.min(h - 14, cy - y));
    } else {
      var fits = w <= s.width - 2 * EDGE;
      var lo = Math.max(fits ? s.left : 0, 0) + EDGE;
      var hi = Math.min(fits ? s.right : vw, vw) - EDGE - w;
      x = Math.max(lo, Math.min(cx - w / 2, hi));
      y = side === "above" ? m.top - GAP - h : m.bottom + GAP;
      arrow = Math.max(14, Math.min(w - 14, cx - x));
    }
    tip.style.left = x - s.left + "px";
    tip.style.top = y - s.top + "px";
    tip.style.setProperty("--tm-arrow", arrow + "px");
    tip.setAttribute("data-side", side);
  }

  function show(mark, via) {
    clearTimeout(timer);
    if (open && open.mark !== mark) hide();
    var tip = document.getElementById(mark.getAttribute("data-tip"));
    if (!tip) return;
    if (open && RANK[open.via] > RANK[via]) via = open.via;
    tip.hidden = false;
    mark.classList.add("is-active");
    place(mark, tip, via !== "pointer");
    open = { mark: mark, tip: tip, via: via };
  }

  function hide() {
    clearTimeout(timer);
    if (!open) return;
    open.tip.hidden = true;
    open.mark.classList.remove("is-active");
    open = null;
  }

  // A panel opened by the pointer closes shortly after the pointer leaves
  // the marker, unless the pointer moves onto the panel.
  function later() {
    clearTimeout(timer);
    timer = setTimeout(function () {
      if (open && open.via === "pointer") hide();
    }, 250);
  }

  function mouse(e) {
    return e.pointerType !== "touch";
  }

  stages.forEach(function (stage) {
    var marks = stage.querySelectorAll(".tm-mark");
    marks.forEach(function (mark) {
      var title = mark.querySelector("title");
      if (title) mark.removeChild(title);
      mark.addEventListener("pointerenter", function (e) {
        if (mouse(e)) show(mark, "pointer");
      });
      mark.addEventListener("pointerleave", function (e) {
        if (mouse(e) && open && open.mark === mark) later();
      });
    });
    // Focus and keys are handled on the map, not on each marker: in some
    // browsers an SVG element with its own focus listeners can take the
    // focus, even when it is hidden and has no tabindex.
    stage.addEventListener("focusin", function (e) {
      var mark = e.target.closest(".tm-mark");
      if (mark) show(mark, "focus");
    });
    // Moving the focus elsewhere closes the panel; a panel opened by a tap
    // stays when the focus is simply lost (for example, tapping its text).
    stage.addEventListener("focusout", function (e) {
      var mark = e.target.closest(".tm-mark");
      if (mark && open && open.mark === mark && (open.via !== "pin" || e.relatedTarget)) hide();
    });
    // Enter or Space keeps the panel open, also when the focus has already
    // opened it; pressed again, it closes the panel. Escape always closes it.
    stage.addEventListener("keydown", function (e) {
      var mark = e.target.closest(".tm-mark");
      if (!mark || (e.key !== "Enter" && e.key !== " ")) return;
      e.preventDefault();
      if (open && open.mark === mark && open.via === "pin") hide();
      else show(mark, "pin");
    });
    stage.querySelectorAll(".tm-tip").forEach(function (tip) {
      tip.addEventListener("pointerenter", function () {
        clearTimeout(timer);
      });
      tip.addEventListener("pointerleave", function (e) {
        if (mouse(e)) later();
      });
    });
    // A tap or a click selects the nearest marker, so that small markers are
    // easy to hit on phones; elsewhere on the map it closes the panel.
    stage.querySelector("svg").addEventListener("click", function (e) {
      var best = null, nearest = REACH;
      marks.forEach(function (mark) {
        if (!shown(mark)) return;
        var r = shapeOf(mark).getBoundingClientRect();
        var d = Math.hypot(e.clientX - r.left - r.width / 2, e.clientY - r.top - r.height / 2) - r.width / 2;
        if (d < nearest) {
          nearest = d;
          best = mark;
        }
      });
      if (!best || (open && open.mark === best && open.via === "pin")) hide();
      else show(best, "pin");
    });
  });

  document.addEventListener("pointerdown", function (e) {
    if (open && !e.target.closest(".tm-stage")) hide();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && open) hide();
  });
  window.addEventListener("resize", function () {
    sync();
    if (open && shown(open.mark)) place(open.mark, open.tip, false);
    else hide();
  });
  sync();
  document.querySelectorAll(".travel-map .tm-hint").forEach(function (hint) {
    hint.hidden = false;
  });
})();
