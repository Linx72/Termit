window.TermitCharts = (function () {
  const PALETTE = {
    queued: "#6366f1",
    running: "#22d3ee",
    completed: "#34d399",
    failed: "#f87171",
    cancelled: "#94a3b8",
    accent: "#818cf8",
    grid: "rgba(148, 163, 184, 0.15)",
    text: "#94a3b8",
  };

  function setupCanvas(canvas, height) {
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || canvas.width;
    const h = height || canvas.clientHeight || 160;
    canvas.width = Math.floor(width * ratio);
    canvas.height = Math.floor(h * ratio);
    canvas.style.height = `${h}px`;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    return { ctx, width, height: h };
  }

  function drawDonut(canvas, segments, options = {}) {
    const { ctx, width, height } = setupCanvas(canvas, options.height || 180);
    ctx.clearRect(0, 0, width, height);
    const total = segments.reduce((sum, item) => sum + item.value, 0);
    const cx = width / 2;
    const cy = height / 2 - 6;
    const outer = Math.min(width, height) * 0.36;
    const inner = outer * 0.58;
    let start = -Math.PI / 2;

    if (total <= 0) {
      ctx.beginPath();
      ctx.arc(cx, cy, outer, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(148,163,184,0.12)";
      ctx.fill();
      ctx.fillStyle = PALETTE.text;
      ctx.font = "13px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(options.emptyLabel || "No data", cx, cy + 4);
      return;
    }

    segments.forEach((seg) => {
      if (seg.value <= 0) return;
      const angle = (seg.value / total) * Math.PI * 2;
      ctx.beginPath();
      ctx.arc(cx, cy, outer, start, start + angle);
      ctx.arc(cx, cy, inner, start + angle, start, true);
      ctx.closePath();
      ctx.fillStyle = seg.color || PALETTE.accent;
      ctx.fill();
      start += angle;
    });

    ctx.fillStyle = "#e2e8f0";
    ctx.font = "600 22px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(String(total), cx, cy - 2);
    ctx.fillStyle = PALETTE.text;
    ctx.font = "11px system-ui, sans-serif";
    ctx.fillText(options.centerLabel || "runs", cx, cy + 14);
  }

  function drawLine(canvas, points, options = {}) {
    const { ctx, width, height } = setupCanvas(canvas, options.height || 160);
    ctx.clearRect(0, 0, width, height);
    const pad = { l: 8, r: 8, t: 12, b: 22 };
    const plotW = width - pad.l - pad.r;
    const plotH = height - pad.t - pad.b;

    if (!points.length) {
      ctx.fillStyle = PALETTE.text;
      ctx.font = "12px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(options.emptyLabel || "Collecting...", width / 2, height / 2);
      return;
    }

    const maxY = Math.max(options.maxY || 0, ...points.map((p) => p.y), 1);
    const minY = options.minY ?? 0;

    ctx.strokeStyle = PALETTE.grid;
    ctx.lineWidth = 1;
    for (let i = 0; i <= 3; i += 1) {
      const y = pad.t + (plotH * i) / 3;
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(width - pad.r, y);
      ctx.stroke();
    }

    const coords = points.map((p, i) => {
      const x = pad.l + (plotW * i) / Math.max(points.length - 1, 1);
      const y = pad.t + plotH - ((p.y - minY) / (maxY - minY || 1)) * plotH;
      return { x, y };
    });

    const grad = ctx.createLinearGradient(0, pad.t, 0, height - pad.b);
    grad.addColorStop(0, "rgba(34, 211, 238, 0.35)");
    grad.addColorStop(1, "rgba(34, 211, 238, 0)");
    ctx.beginPath();
    coords.forEach((c, i) => {
      if (i === 0) ctx.moveTo(c.x, c.y);
      else ctx.lineTo(c.x, c.y);
    });
    ctx.lineTo(coords[coords.length - 1].x, height - pad.b);
    ctx.lineTo(coords[0].x, height - pad.b);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    coords.forEach((c, i) => {
      if (i === 0) ctx.moveTo(c.x, c.y);
      else ctx.lineTo(c.x, c.y);
    });
    ctx.strokeStyle = options.color || "#22d3ee";
    ctx.lineWidth = 2;
    ctx.stroke();

    coords.forEach((c) => {
      ctx.beginPath();
      ctx.arc(c.x, c.y, 3, 0, Math.PI * 2);
      ctx.fillStyle = "#67e8f9";
      ctx.fill();
    });

    const last = points[points.length - 1];
    ctx.fillStyle = PALETTE.text;
    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(`${last.y.toFixed(1)}%`, width - pad.r, pad.t - 2);
  }

  function drawBars(canvas, items, options = {}) {
    const { ctx, width, height } = setupCanvas(canvas, options.height || 140);
    ctx.clearRect(0, 0, width, height);
    if (!items.length) return;

    const pad = { l: 4, r: 4, t: 8, b: 28 };
    const barGap = 10;
    const maxVal = Math.max(...items.map((i) => i.value), 1);
    const barW = (width - pad.l - pad.r - barGap * (items.length - 1)) / items.length;
    const plotH = height - pad.t - pad.b;

    items.forEach((item, idx) => {
      const h = (item.value / maxVal) * plotH;
      const x = pad.l + idx * (barW + barGap);
      const y = pad.t + plotH - h;
      const r = 6;
      ctx.fillStyle = item.color || PALETTE.accent;
      ctx.beginPath();
      ctx.moveTo(x, y + r);
      ctx.arcTo(x, y, x + r, y, r);
      ctx.arcTo(x + barW, y, x + barW, y + r, r);
      ctx.lineTo(x + barW, pad.t + plotH);
      ctx.lineTo(x, pad.t + plotH);
      ctx.closePath();
      ctx.fill();

      ctx.fillStyle = PALETTE.text;
      ctx.font = "10px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(item.label, x + barW / 2, height - 8);
      if (item.value > 0) {
        ctx.fillStyle = "#cbd5e1";
        ctx.fillText(String(item.value), x + barW / 2, y - 4);
      }
    });
  }

  return { drawDonut, drawLine, drawBars, PALETTE };
})();
