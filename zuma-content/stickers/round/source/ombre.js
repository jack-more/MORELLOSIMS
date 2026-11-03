/* ZUMA New Mission. Lightbox: one research area as a field of glowing tiles. Each tile has a bright rim and a soft pool inside;
   Oxblood bars cut across the field on shared lines. One area per field, never mixed.
   <canvas data-lb="metabolic" data-seed="3" data-cols="4" data-rows="4" data-bars="0|1" data-behind="palm|bamboo" data-bseed="5">
   data-behind stands palm fronds or bamboo behind the glowing tiles, seen through the glass. */
(function () {
  var AREAS = {
    dermal: ['#FFC9BE', '#FF6A55', '#A8281F'],
    metabolic: ['#BFE8FB', '#36B3E8', '#0E5A8C'],
    tissue: ['#D5F3BC', '#6CC93A', '#2F6E14'],
    endocrine: ['#FBF1A6', '#F4D63A', '#9A7A06'],
    neuro: ['#E4D8FF', '#A57BF0', '#4B2A9A'],
    supplies: ['#E3E8ED', '#9AA8B6', '#3D4956'],
    oxblood: ['#D99AA6', '#9A3347', '#4A0E1B']
  };
  var OXBLOOD = [110, 28, 42];
  function rgb(h) { return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]; }
  for (var k in AREAS) AREAS[k] = AREAS[k].map(rgb);
  function ss(t) { t = t < 0 ? 0 : t > 1 ? 1 : t; return t * t * (3 - 2 * t); }
  function mix(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
  function rng(seed) {
    return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  }

  function paint(cv) {
    var name = cv.getAttribute('data-lb'), A = AREAS[name] || AREAS.metabolic, L = A[0], B = A[1], D = A[2];
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var sk = +(cv.getAttribute('data-scale') || 1);   // a soft field: big panels paint at a fraction of their size and are stretched
    var W = Math.round(cv.clientWidth * dpr * sk), H = Math.round(cv.clientHeight * dpr * sk);
    if (!W || !H) return;
    cv.width = W; cv.height = H;
    var ctx = cv.getContext('2d'), img = ctx.createImageData(W, H), px = img.data;
    var R = rng(+(cv.getAttribute('data-seed') || 7)), G = rng(99);
    var ncols = +(cv.getAttribute('data-cols') || 4), nrows = +(cv.getAttribute('data-rows') || 4);
    var bars = cv.getAttribute('data-bars') !== '0';
    var base = mix(L, B, 0.5), deepPool = mix(B, D, 0.42), lightPool = mix(L, base, 0.35);
    // on dermal the bar leans browner so it never reads as dermal's own deep red
    var BAR = name === 'oxblood' ? [52, 10, 20] : name === 'dermal' ? mix(OXBLOOD, [40, 16, 12], 0.45) : OXBLOOD;

    // columns: the first wide, the rest narrowing, like a lightbox wall
    var ws = [], tot = 0, i;
    for (i = 0; i < ncols; i++) { var v = (i === 0 ? 2.2 : 0.6 + R() * 1.1); ws.push(v); tot += v; }
    var xs = [0]; for (i = 0; i < ncols; i++) xs.push(xs[i] + ws[i] / tot);
    // shared horizontal lines, so bars line up across columns
    var lines = []; for (i = 0; i < nrows - 1; i++) lines.push((i + 1) / nrows + (R() - 0.5) * 0.6 / nrows);
    lines.sort();

    function tile(a, b, y0, y1) {
      var w = b - a, h = y1 - y0, m = Math.min(w, h);
      if (w < 1 || h < 1) return;
      var cx = (a + b) / 2 + (R() - 0.5) * w * 0.3, cy = (y0 + y1) / 2 + (R() - 0.5) * h * 0.3;
      var rx = w * (0.26 + R() * 0.16), ry = h * (0.26 + R() * 0.16);
      var pool = R() < 0.75 ? deepPool : lightPool, s = 0.55 + R() * 0.35, rim = 5 * dpr;
      for (var y = y0; y < y1; y++) {
        var vt = (y - y0) / h;
        for (var x = a; x < b; x++) {
          var qx = (x - cx) / rx, qy = (y - cy) / ry;
          var col = mix(base, pool, s * Math.exp(-(qx * qx * qx * qx + qy * qy * qy * qy) * 0.9));   // the soft pool, a blurred rounded square
          col = mix(col, L, 0.22 * (1 - vt));                                   // lit from above
          var e = Math.min(x - a, b - 1 - x, y - y0, y1 - 1 - y);
          col = mix(col, L, 0.38 * Math.exp(-e / rim));                         // bright tile edge
          var o = (y * W + x) * 4, gr = (G() - 0.5) * 8;
          px[o] = col[0] + gr; px[o + 1] = col[1] + gr; px[o + 2] = col[2] + gr; px[o + 3] = 255;
        }
      }
    }

    for (var c = 0; c < ncols; c++) {
      var a = Math.round(xs[c] * W), b = Math.round(xs[c + 1] * W);
      var ys = [0]; lines.forEach(function (l) { if (R() > 0.45) ys.push(l); }); ys.push(1);
      for (var s = 0; s < ys.length - 1; s++) tile(a, b, Math.round(ys[s] * H), Math.round(ys[s + 1] * H));
    }
    // bars run straight across a run of neighbouring columns, on the shared lines
    var barRects = [];
    // data-bar-min keeps bars clear of type laid over the field: on a wide panel they start past that fraction of the width,
    // on a tall one (a phone) they stay below it
    var bmin = +(cv.getAttribute('data-bar-min') || 0), tall = cv.clientWidth < cv.clientHeight * 1.2;
    if (bars) lines.forEach(function (l) {
      if (R() < 0.35) return;
      var c0 = Math.floor(R() * ncols), c1 = Math.min(ncols - 1, c0 + 1 + Math.floor(R() * ncols));
      var bx0 = Math.round(xs[c0] * W), bx1 = Math.round(xs[c1 + 1] * W);
      if (bmin && tall && l < bmin) return;
      if (bmin && !tall) { bx0 = Math.max(bx0, Math.round(bmin * W)); if (bx1 - bx0 < W * 0.12) return; }
      var th = Math.max(3, Math.round(H * (0.016 + R() * 0.018)));
      barRects.push([bx0, Math.round(l * H - th / 2), bx1 - bx0, th]);
    });
    ctx.putImageData(img, 0, 0);
    // fronds or bamboo standing behind the lit glass: soft silhouettes in the area's deep tone
    var behind = cv.getAttribute('data-behind');
    if (behind) {
      var Sz = Math.max(W, H), off = W * 3, dc = 'rgba(' + D.map(Math.round).join(',');
      [[Sz * 0.028, dc + ',.34)'], [Sz * 0.01, dc + ',.16)']].forEach(function (pass) {
        var r2 = rng(+(cv.getAttribute('data-bseed') || 5));
        ctx.save();
        ctx.globalCompositeOperation = 'multiply';
        ctx.shadowColor = pass[1]; ctx.shadowBlur = pass[0]; ctx.shadowOffsetX = off;
        ctx.translate(-off, 0); ctx.fillStyle = '#000'; ctx.strokeStyle = '#000';
        (behind === 'bamboo' ? bamboo : palm)(ctx, W, H, r2);
        ctx.restore();
      });
    }
    // the bars sit in front of everything
    ctx.fillStyle = 'rgb(' + BAR.map(Math.round).join(',') + ')';
    barRects.forEach(function (r) { ctx.fillRect(r[0], r[1], r[2], r[3]); });
    cv.setAttribute('data-painted', '');
  }


  /* Shadows: palm fronds or bamboo falling across warm stucco in calm, low light.
     <canvas data-shadow="palm|bamboo" data-seed="4"> */
  function leaf(ctx, x, y, ang, len, wid) {
    var c = Math.cos(ang), s = Math.sin(ang), tx = x + c * len, ty = y + s * len, px = -s * wid, py = c * wid;
    ctx.moveTo(x, y);
    ctx.quadraticCurveTo(x + c * len * 0.45 + px, y + s * len * 0.45 + py, tx, ty);
    ctx.quadraticCurveTo(x + c * len * 0.45 - px, y + s * len * 0.45 - py, x, y);
  }
  function palm(ctx, W, H, R) {
    var fronds = 3;
    for (var f = 0; f < fronds; f++) {
      var x0 = W * (0.75 + R() * 0.4), y0 = -H * (0.1 + R() * 0.1);
      var x2 = W * (0.05 + R() * 0.45), y2 = H * (0.55 + R() * 0.5);
      var x1 = (x0 + x2) / 2 + W * (R() * 0.3), y1 = (y0 + y2) / 2 - H * 0.15;
      var S = Math.max(W, H);
      ctx.lineWidth = S * 0.006; ctx.beginPath();
      ctx.moveTo(x0, y0); ctx.quadraticCurveTo(x1, y1, x2, y2); ctx.stroke();
      ctx.beginPath();
      for (var t = 0.04; t < 0.98; t += 0.022) {
        var u = 1 - t, px = u * u * x0 + 2 * u * t * x1 + t * t * x2, py = u * u * y0 + 2 * u * t * y1 + t * t * y2;
        var dx = 2 * u * (x1 - x0) + 2 * t * (x2 - x1), dy = 2 * u * (y1 - y0) + 2 * t * (y2 - y1), a = Math.atan2(dy, dx);
        var L = S * (0.05 + 0.19 * Math.sin(Math.PI * Math.min(1, t * 1.15))), w = L * 0.07;
        leaf(ctx, px, py, a - 1.05 + (R() - 0.5) * 0.25 + 0.25, L, w);
        leaf(ctx, px, py, a + 1.05 + (R() - 0.5) * 0.25 + 0.25, L, w);
      }
      ctx.fill();
    }
  }
  function bamboo(ctx, W, H, R) {
    var n = 3 + Math.floor(R() * 2);
    for (var i = 0; i < n; i++) {
      var x = W * (0.12 + i / n * 0.8 + (R() - 0.5) * 0.08), lean = (R() - 0.5) * W * 0.12, wd = W * (0.012 + R() * 0.01);
      var seg = H * (0.16 + R() * 0.08);
      for (var y = -R() * seg; y < H; y += seg) {
        var t0 = y / H, t1 = (y + seg * 0.94) / H;
        ctx.beginPath();
        ctx.moveTo(x + lean * t0 - wd / 2, y); ctx.lineTo(x + lean * t0 + wd / 2, y);
        ctx.lineTo(x + lean * t1 + wd / 2, y + seg * 0.94); ctx.lineTo(x + lean * t1 - wd / 2, y + seg * 0.94); ctx.fill();
        if (R() < 0.55) {                                   // a sprig of leaves from the node
          var bx = x + lean * t1, by = y + seg * 0.94, dir = R() < 0.5 ? -1 : 1, S = Math.max(W, H);
          ctx.beginPath();
          for (var k = 0; k < 5 + R() * 4; k++) {
            var a = (dir < 0 ? Math.PI : 0) + dir * (0.25 + R() * 0.9);
            leaf(ctx, bx + dir * k * S * 0.012, by + k * S * 0.006, a, S * (0.07 + R() * 0.06), S * 0.007);
          }
          ctx.fill();
        }
      }
    }
  }
  function shade(cv) {
    var kind = cv.getAttribute('data-shadow'), dpr = Math.min(window.devicePixelRatio || 1, 2);
    var W = Math.round(cv.clientWidth * dpr), H = Math.round(cv.clientHeight * dpr);
    if (!W || !H) return;
    cv.width = W; cv.height = H;
    var ctx = cv.getContext('2d'), R = rng(+(cv.getAttribute('data-seed') || 4));
    // warm stucco, lit from the upper left
    var g = ctx.createLinearGradient(0, 0, W, H);
    g.addColorStop(0, '#F8EEDD'); g.addColorStop(0.55, '#F1E6D4'); g.addColorStop(1, '#E4D5BF');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    var sun = ctx.createRadialGradient(W * 0.3, H * 0.25, 0, W * 0.3, H * 0.25, Math.max(W, H) * 0.7);
    sun.addColorStop(0, 'rgba(255,244,222,.55)'); sun.addColorStop(1, 'rgba(255,244,222,0)');
    ctx.fillStyle = sun; ctx.fillRect(0, 0, W, H);
    // the shadow: shapes drawn off-canvas, only their blurred shadow lands (works in every browser).
    // data-shadow="none" leaves the wall clean: used where a Lightbox sits on it, so the plant shows only behind the glass
    var S = Math.max(W, H), off = W * 3;
    if (kind !== 'none') [[S * 0.03, 'rgba(92,52,36,.20)'], [S * 0.008, 'rgba(92,52,36,.16)']].forEach(function (pass) {
      var r2 = rng(+(cv.getAttribute('data-seed') || 4));
      ctx.save();
      ctx.shadowColor = pass[1]; ctx.shadowBlur = pass[0]; ctx.shadowOffsetX = off; ctx.shadowOffsetY = 0;
      ctx.translate(-off, 0); ctx.fillStyle = '#000'; ctx.strokeStyle = '#000';
      (kind === 'bamboo' ? bamboo : palm)(ctx, W, H, r2);
      ctx.restore();
    });
    // plaster grain
    var img = ctx.getImageData(0, 0, W, H), px = img.data, G = rng(77);
    for (var i = 0; i < px.length; i += 4) { var n = (G() - 0.5) * 7; px[i] += n; px[i + 1] += n; px[i + 2] += n; }
    ctx.putImageData(img, 0, 0);
    cv.setAttribute('data-painted', '');
  }

  var all = [].slice.call(document.querySelectorAll('canvas[data-lb]')), shades = [].slice.call(document.querySelectorAll('canvas[data-shadow]'));
  function run() { all.forEach(paint); shades.forEach(shade); }
  run();
  var last = window.innerWidth, timer;
  window.addEventListener('resize', function () {
    if (Math.abs(window.innerWidth - last) < 40) return;
    last = window.innerWidth; clearTimeout(timer); timer = setTimeout(run, 200);
  });
})();
