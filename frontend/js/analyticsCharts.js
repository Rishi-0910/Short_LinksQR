import { apiFetch } from "./api.js";
import { debounce } from "./dom.js";

const COLORS = { accent: "#6C8EFF", warm: "#FFB454", dim: "#8B92A6", grid: "#2A2F3D" };
let loaded = false;

function setupCanvas(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const cssHeight = Number(canvas.getAttribute("height")) || rect.height || 220;
  canvas.width = rect.width * ratio;
  canvas.height = cssHeight * ratio;
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  return { ctx, width: rect.width, height: cssHeight };
}

function drawLineChart(canvas, points) {
  const { ctx, width, height } = setupCanvas(canvas);
  ctx.clearRect(0, 0, width, height);
  const padding = { top: 16, right: 16, bottom: 28, left: 36 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  if (points.length === 0) {
    ctx.fillStyle = COLORS.dim;
    ctx.font = "13px Inter, sans-serif";
    ctx.fillText("No click data in this range yet.", padding.left, height / 2);
    return;
  }

  const maxVal = Math.max(...points.map((p) => p.clicks), 1);
  const stepX = points.length > 1 ? plotW / (points.length - 1) : 0;

  // Gridlines
  ctx.strokeStyle = COLORS.grid;
  ctx.lineWidth = 1;
  for (let i = 0; i <= 3; i++) {
    const y = padding.top + (plotH / 3) * i;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    ctx.fillStyle = COLORS.dim;
    ctx.font = "11px Inter, sans-serif";
    ctx.fillText(Math.round(maxVal * (1 - i / 3)), 0, y + 4);
  }

  // Line + fill
  ctx.beginPath();
  points.forEach((p, i) => {
    const x = padding.left + stepX * i;
    const y = padding.top + plotH - (p.clicks / maxVal) * plotH;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.strokeStyle = COLORS.accent;
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.lineTo(padding.left + stepX * (points.length - 1), padding.top + plotH);
  ctx.lineTo(padding.left, padding.top + plotH);
  ctx.closePath();
  ctx.fillStyle = "rgba(108,142,255,0.12)";
  ctx.fill();

  // X labels (sparse, so they don't collide)
  ctx.fillStyle = COLORS.dim;
  ctx.font = "11px Inter, sans-serif";
  const labelEvery = Math.ceil(points.length / 6);
  points.forEach((p, i) => {
    if (i % labelEvery !== 0) return;
    const x = padding.left + stepX * i;
    const label = new Date(p.date).toLocaleDateString(undefined, { month: "short", day: "numeric" });
    ctx.fillText(label, x - 12, height - 8);
  });
}

function drawBarChart(canvas, items, labelKey, valueKey) {
  const { ctx, width, height } = setupCanvas(canvas);
  ctx.clearRect(0, 0, width, height);
  const padding = { top: 12, right: 16, bottom: 12, left: 12 };

  if (items.length === 0) {
    ctx.fillStyle = COLORS.dim;
    ctx.font = "13px Inter, sans-serif";
    ctx.fillText("No data yet.", padding.left, height / 2);
    return;
  }

  const maxVal = Math.max(...items.map((i) => i[valueKey]), 1);
  const rowH = Math.min(28, (height - padding.top - padding.bottom) / items.length);
  const labelWidth = 110;
  const barAreaW = width - padding.left - padding.right - labelWidth - 40;

  items.forEach((item, i) => {
    const y = padding.top + i * rowH;
    const barW = (item[valueKey] / maxVal) * barAreaW;

    ctx.fillStyle = COLORS.dim;
    ctx.font = "12px Inter, sans-serif";
    const label = String(item[labelKey]).length > 16 ? String(item[labelKey]).slice(0, 15) + "…" : item[labelKey];
    ctx.fillText(label, padding.left, y + rowH / 2 + 4);

    ctx.fillStyle = i === 0 ? COLORS.accent : "rgba(108,142,255,0.45)";
    ctx.fillRect(padding.left + labelWidth, y + rowH * 0.2, Math.max(barW, 2), rowH * 0.6);

    ctx.fillStyle = COLORS.dim;
    ctx.fillText(item[valueKey], padding.left + labelWidth + barW + 8, y + rowH / 2 + 4);
  });
}

function drawDeviceChart(canvas, distribution) {
  const entries = Object.entries(distribution);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);
  const { ctx, width, height } = setupCanvas(canvas);
  ctx.clearRect(0, 0, width, height);

  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) / 2 - 12;
  const colors = [COLORS.accent, COLORS.warm, COLORS.dim];

  if (total === 0) {
    ctx.fillStyle = COLORS.dim;
    ctx.font = "13px Inter, sans-serif";
    ctx.fillText("No clicks yet.", cx - 40, cy);
    return;
  }

  let startAngle = -Math.PI / 2;
  entries.forEach(([, value], i) => {
    const sliceAngle = (value / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, radius, startAngle, startAngle + sliceAngle);
    ctx.closePath();
    ctx.fillStyle = colors[i % colors.length];
    ctx.fill();
    startAngle += sliceAngle;
  });

  // Donut hole
  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.55, 0, Math.PI * 2);
  ctx.fillStyle = "#171A22";
  ctx.fill();

  const legend = document.getElementById("device-legend");
  legend.innerHTML = entries
    .map(
      ([label, value], i) =>
        `<div class="legend-item"><span class="legend-dot" style="background:${colors[i % colors.length]}"></span>${label} (${value})</div>`
    )
    .join("");
}

async function loadAnalytics() {
  const days = document.getElementById("analytics-range").value;
  try {
    const data = await apiFetch(`/analytics/overview?days=${encodeURIComponent(days)}`);

    document.getElementById("stat-total-clicks").textContent = data.totalClicks;
    document.getElementById("stat-top-referrer").textContent = data.topReferrers[0]?.referrer || "-";
    const topDevice = Object.entries(data.deviceDistribution).sort((a, b) => b[1] - a[1])[0];
    document.getElementById("stat-top-device").textContent = topDevice && topDevice[1] > 0 ? topDevice[0] : "-";

    drawLineChart(document.getElementById("chart-clicks-over-time"), data.clicksOverTime);
    drawBarChart(document.getElementById("chart-referrers"), data.topReferrers, "referrer", "clicks");
    drawDeviceChart(document.getElementById("chart-devices"), data.deviceDistribution);
  } catch {
    document.getElementById("stat-total-clicks").textContent = "-";
    document.getElementById("stat-top-referrer").textContent = "-";
    document.getElementById("stat-top-device").textContent = "-";
    drawLineChart(document.getElementById("chart-clicks-over-time"), []);
    drawBarChart(document.getElementById("chart-referrers"), [], "referrer", "clicks");
    drawDeviceChart(document.getElementById("chart-devices"), { Mobile: 0, Desktop: 0, Tablet: 0 });
  }
}

export function initAnalytics() {
  document.getElementById("analytics-range").addEventListener("change", loadAnalytics);
  window.addEventListener("view:analytics:shown", () => loadAnalytics());
  if (!loaded) {
    loaded = true;
    loadAnalytics();
  }
  window.addEventListener("resize", debounce(() => {
    if (document.getElementById("view-analytics").classList.contains("active")) loadAnalytics();
  }, 200));
}
