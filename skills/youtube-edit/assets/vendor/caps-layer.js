/* Burned-in caption layer for /youtube-edit compositions (STYLE.md K1/K2).
 * Data: public/captions.js from scripts/captions.py (window.__CAPS, __CAPS_Y, __CAPS_STYLE).
 * Config (optional, set before this script): window.__CAPS_CFG = {fps, y, room, min}.
 * Adds to the "talking-head-recut" timeline, so load it AFTER the main timeline script.
 *
 * Styles:
 *   default  one line, the whole group appears at once with a small settle, shrink to fit
 *   "bold"   1-3 heavy uppercase words; each word pops in on the frame it is spoken,
 *            emphasis words land in the accent colour, 1.1x (set in CSS so the line makes room)
 */
(function () {
  const tl = window.__timelines && window.__timelines["talking-head-recut"];
  const caps = window.__CAPS, cfg = window.__CAPS_CFG || {};
  if (!tl || !caps) return;
  const host = document.getElementById("caps-host");
  const fps = cfg.fps || 30;
  const y = window.__CAPS_Y || cfg.y || Math.round(1920 * 0.68);
  const room = cfg.room || host.clientWidth - 140, min = cfg.min || 62;
  const bold = window.__CAPS_STYLE === "bold";
  const q = (t) => Math.round(t * fps) / fps;
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  caps.forEach(function (c, i) {
    const d = document.createElement("div");
    d.className = "cap" + (bold ? " bold" : "");
    d.id = "cap-" + i;
    d.style.top = y + "px";
    d.style.whiteSpace = "nowrap";
    d.innerHTML = c.words.map(function (w, k) {
      return '<span class="w' + (w.em ? " em" : "") + '" id="cap-' + i + "-" + k + '">' + esc(w.t) + "</span>";
    }).join(" ");
    host.appendChild(d);
    // one line only: shrink a long group to fit (never below `min`) instead of wrapping
    const base = parseFloat(getComputedStyle(d).fontSize);
    if (d.scrollWidth > room) d.style.fontSize = Math.max(min, Math.floor(base * room / d.scrollWidth)) + "px";
    tl.set(d, { yPercent: -50, opacity: 0 }, 0);
    tl.set(d, { opacity: 1 }, q(c.in));
    if (bold) {
      c.words.forEach(function (w, k) {
        const el = "#cap-" + i + "-" + k;
        const at = q(Math.max(c.in, (w.s == null ? c.in : w.s) - 0.04));   // lands with the word
        tl.set(el, { opacity: 0, scale: 0.5 }, 0);
        tl.fromTo(el, { opacity: 0, scale: 0.5 },
          { opacity: 1, scale: 1, duration: 0.14, ease: "back.out(2.4)" }, at);
      });
    } else {
      tl.fromTo(d, { scale: 0.94 }, { scale: 1, duration: 0.1, ease: "power2.out" }, q(c.in));
    }
    tl.set(d, { opacity: 0 }, q(c.out));
  });
})();
