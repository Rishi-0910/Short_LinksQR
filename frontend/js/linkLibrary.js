import { apiFetch, ApiError } from "./api.js";
import { debounce, escapeAttr, escapeHtml } from "./dom.js";
import { showToast } from "./toast.js";

let currentPage = 1;
let currentSearch = "";
let initialized = false;
let activeQrUrl = "";

function absoluteUrl(value) {
  return new URL(value, window.location.origin).href;
}

function fmtDate(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function rowTemplate(link) {
  const qrUrl = absoluteUrl(link.shortUrl);
  const titlePrefix = link.title ? `${escapeHtml(link.title)} - ` : "";
  const originalUrl = escapeHtml(link.originalUrl);
  const shortUrl = escapeHtml(link.shortUrl.replace(/^https?:\/\//, ""));

  return `
    <tr data-id="${escapeAttr(link.id)}">
      <td>
        <span class="link-url" title="${escapeAttr(link.originalUrl)}">${titlePrefix}${originalUrl}</span>
      </td>
      <td>
        <div class="short-link-cell">
          <span class="mono">${shortUrl}</span>
          <button class="btn btn-sm copy-btn" type="button" title="Copy link" data-url="${escapeAttr(qrUrl)}">Copy</button>
          <button class="btn btn-sm qr-btn" type="button" title="Show QR code" data-url="${escapeAttr(qrUrl)}" data-code="${escapeAttr(link.shortCode)}">QR</button>
        </div>
      </td>
      <td>${Number(link.totalClicks) || 0}</td>
      <td>${fmtDate(link.createdAt)}</td>
      <td class="row-actions">
        <button class="btn btn-sm btn-danger-ghost delete-btn" type="button" data-id="${escapeAttr(link.id)}">Delete</button>
      </td>
    </tr>`;
}

async function loadLinks() {
  const tbody = document.getElementById("links-tbody");
  tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Loading your links...</td></tr>`;

  try {
    const params = new URLSearchParams({ page: String(currentPage), pageSize: "10" });
    if (currentSearch) params.set("search", currentSearch);
    const { links, pagination } = await apiFetch(`/links?${params.toString()}`);

    if (!links.length) {
      const message = currentSearch ? "No links match your search." : "No links yet. Create your first one above.";
      tbody.innerHTML = `<tr><td colspan="5" class="empty-state">${message}</td></tr>`;
    } else {
      // Values are escaped in rowTemplate before joining into one efficient DOM write.
      tbody.innerHTML = links.map(rowTemplate).join("");
    }
    renderPagination(pagination);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-state">${escapeHtml(err.payload?.message || "Couldn't load your links. Please refresh.")}</td></tr>`;
  }
}

function renderPagination(pagination) {
  const el = document.getElementById("links-pagination");
  if (!pagination || pagination.totalPages <= 1) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = `
    <button class="btn btn-sm" type="button" id="prev-page" ${pagination.page <= 1 ? "disabled" : ""}>Prev</button>
    <span>Page ${Number(pagination.page) || 1} of ${Number(pagination.totalPages) || 1}</span>
    <button class="btn btn-sm" type="button" id="next-page" ${pagination.page >= pagination.totalPages ? "disabled" : ""}>Next</button>
  `;
  document.getElementById("prev-page")?.addEventListener("click", () => {
    currentPage = Math.max(1, currentPage - 1);
    loadLinks();
  });
  document.getElementById("next-page")?.addEventListener("click", () => {
    currentPage += 1;
    loadLinks();
  });
}

function applyFieldErrors(form, fields = {}) {
  Object.entries(fields).forEach(([name, message]) => {
    const input = form.elements.namedItem(name);
    if (!input) return;
    const field = input.closest(".field");
    field.classList.add("has-error");
    field.querySelector(".field-error").textContent = message;
  });
}

function wireCreateForm() {
  const form = document.getElementById("create-link-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    form.querySelectorAll(".field").forEach((f) => f.classList.remove("has-error"));
    form.querySelectorAll(".field-error").forEach((el) => (el.textContent = ""));

    const data = Object.fromEntries(new FormData(form).entries());
    const submitBtn = form.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    submitBtn.textContent = "Shortening...";

    try {
      await apiFetch("/links", { method: "POST", body: data });
      form.reset();
      showToast("Short link created.");
      currentPage = 1;
      loadLinks();
    } catch (err) {
      if (err instanceof ApiError && err.payload?.fields) {
        applyFieldErrors(form, err.payload.fields);
      } else {
        showToast(err.payload?.message || "Couldn't create the link.", "error");
      }
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Shorten link";
    }
  });
}

function wireSearch() {
  document.getElementById("link-search").addEventListener("input", debounce((e) => {
    currentSearch = e.target.value.trim();
    currentPage = 1;
    loadLinks();
  }, 300));
}

function wireTableActions() {
  document.getElementById("links-tbody").addEventListener("click", async (e) => {
    const target = e.target;

    if (target.classList.contains("copy-btn")) {
      try {
        await navigator.clipboard.writeText(target.dataset.url);
        showToast("Copied to clipboard.");
      } catch {
        showToast("Clipboard is unavailable in this browser.", "error");
      }
    }

    if (target.classList.contains("qr-btn")) {
      openQrModal(target.dataset.url, target.dataset.code);
    }

    if (target.classList.contains("delete-btn")) {
      const linkId = target.dataset.id;
      if (!confirm("Delete this link? This can't be undone.")) return;
      try {
        await apiFetch(`/links/${encodeURIComponent(linkId)}`, { method: "DELETE" });
        showToast("Link deleted.");
        loadLinks();
      } catch {
        showToast("Couldn't delete the link.", "error");
      }
    }
  });
}

let activeQrCode = "link";

// Every render call below is fed the same absolute URL, so a scan or a
// download can never resolve to a relative path or bare hostname.
function openQrModal(url, shortCode) {
  activeQrUrl = absoluteUrl(url);
  activeQrCode = shortCode || "link";
  const modal = document.getElementById("qr-modal");
  const target = document.getElementById("qr-target");
  target.innerHTML = "";
  if (!window.QRCode) {
    showToast("QR generator failed to load. Check your network and try again.", "error");
    return;
  }
  // QRCode is loaded globally via the qrcodejs CDN script tag in index.html.
  // eslint-disable-next-line no-undef
  new QRCode(target, { text: activeQrUrl, width: 180, height: 180, correctLevel: QRCode.CorrectLevel.H });
  document.getElementById("qr-url").textContent = activeQrUrl;
  modal.classList.add("show");
}

/**
 * Renders a fresh, full-resolution QR code for `url` into an off-screen
 * canvas and resolves once pixels are actually painted (no fixed-delay
 * guessing, which is what let blank/half-drawn exports slip through
 * before). `quietZone` keeps a white margin around the code -- scanners
 * rely on it, and it's easy to lose if you crop straight to the modules.
 */
function buildQrCanvas(url, { size = 1200, quietZone = 80 } = {}) {
  return new Promise((resolve, reject) => {
    if (!window.QRCode) {
      reject(new Error("qr_unavailable"));
      return;
    }

    const absolute = absoluteUrl(url);
    const codeSize = size - quietZone * 2;
    const holder = document.createElement("div");
    holder.style.cssText = "position:fixed;left:-9999px;top:-9999px;width:0;height:0;overflow:hidden;";
    document.body.appendChild(holder);

    const finish = (source) => {
      const canvas = document.createElement("canvas");
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, size, size);
      ctx.drawImage(source, quietZone, quietZone, codeSize, codeSize);
      holder.remove();
      resolve(canvas);
    };

    const fail = (err) => {
      holder.remove();
      reject(err);
    };

    // eslint-disable-next-line no-undef
    new QRCode(holder, { text: absolute, width: codeSize, height: codeSize, correctLevel: QRCode.CorrectLevel.H });

    // qrcodejs draws into a <canvas> synchronously on every modern browser;
    // it only falls back to an async <img> (data-URI) on ancient engines
    // that can't do canvas at all. Handle both instead of assuming one.
    const sourceCanvas = holder.querySelector("canvas");
    if (sourceCanvas) {
      finish(sourceCanvas);
      return;
    }
    const sourceImage = holder.querySelector("img");
    if (!sourceImage) {
      fail(new Error("qr_render_failed"));
      return;
    }
    if (sourceImage.complete && sourceImage.naturalWidth > 0) {
      finish(sourceImage);
      return;
    }
    sourceImage.addEventListener("load", () => finish(sourceImage), { once: true });
    sourceImage.addEventListener("error", () => fail(new Error("qr_render_failed")), { once: true });
  });
}

function triggerDownload(href, filename) {
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

async function withButtonBusy(button, busyLabel, task) {
  if (!button) return task();
  const original = button.textContent;
  button.disabled = true;
  button.textContent = busyLabel;
  try {
    return await task();
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function downloadQrPng(button) {
  if (!activeQrUrl) return;
  await withButtonBusy(button, "Preparing…", async () => {
    try {
      const canvas = await buildQrCanvas(activeQrUrl, { size: 1200, quietZone: 80 });
      triggerDownload(canvas.toDataURL("image/png"), `linknest-qr-${activeQrCode}.png`);
      showToast("QR code downloaded.");
    } catch {
      showToast("Couldn't download the QR code.", "error");
    }
  });
}

async function downloadQrSvg(button) {
  if (!activeQrUrl) return;
  await withButtonBusy(button, "Preparing…", async () => {
    try {
      // qrcodejs only draws raster output, so the vector wrapper embeds
      // that high-resolution PNG as its image payload -- still a real,
      // scalable .svg file scanners and browsers open directly.
      const canvas = await buildQrCanvas(activeQrUrl, { size: 1200, quietZone: 80 });
      const pngDataUrl = canvas.toDataURL("image/png");
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${canvas.width}" height="${canvas.height}" viewBox="0 0 ${canvas.width} ${canvas.height}"><image width="${canvas.width}" height="${canvas.height}" href="${pngDataUrl}"/></svg>`;
      const blobUrl = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
      triggerDownload(blobUrl, `linknest-qr-${activeQrCode}.svg`);
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 4000);
      showToast("QR code downloaded.");
    } catch {
      showToast("Couldn't download the QR code.", "error");
    }
  });
}

async function shareQrLink(button) {
  if (!activeQrUrl) return;
  await withButtonBusy(button, "Sharing…", async () => {
    const shareData = { title: "LinkNest QR link", text: "Open this link:", url: activeQrUrl };

    // Prefer sharing the actual QR image (not just the URL) wherever the
    // platform's share sheet supports file attachments.
    if (navigator.share && navigator.canShare) {
      try {
        const canvas = await buildQrCanvas(activeQrUrl, { size: 1200, quietZone: 80 });
        const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
        const file = blob && new File([blob], `linknest-qr-${activeQrCode}.png`, { type: "image/png" });
        const withFile = file ? { ...shareData, files: [file] } : shareData;
        if (file && navigator.canShare(withFile)) {
          await navigator.share(withFile);
          return;
        }
      } catch (err) {
        if (err?.name === "AbortError") return;
        // Fall through to a link-only share below.
      }
    }

    if (navigator.share) {
      try {
        await navigator.share(shareData);
        return;
      } catch (err) {
        if (err?.name === "AbortError") return;
      }
    }

    // No Web Share API (typically desktop): fall back to the always-visible
    // WhatsApp / Email / Copy buttons instead of guessing a channel.
    showToast("Native sharing isn't available here — use WhatsApp, Email, or Copy Link below.");
  });
}

async function copyQrLink() {
  if (!activeQrUrl) return;
  try {
    await navigator.clipboard.writeText(activeQrUrl);
    showToast("Link copied to clipboard!");
  } catch {
    showToast("Clipboard is unavailable in this browser.", "error");
  }
}

document.getElementById("qr-close-btn")?.addEventListener("click", () => {
  document.getElementById("qr-modal").classList.remove("show");
});
document.getElementById("qr-modal")?.addEventListener("click", (e) => {
  if (e.target.id === "qr-modal") e.target.classList.remove("show");
});
document.getElementById("qr-download-btn")?.addEventListener("click", (e) => downloadQrPng(e.currentTarget));
document.getElementById("qr-download-svg-btn")?.addEventListener("click", (e) => downloadQrSvg(e.currentTarget));
document.getElementById("qr-share-btn")?.addEventListener("click", (e) => shareQrLink(e.currentTarget));
document.getElementById("qr-copy-btn")?.addEventListener("click", copyQrLink);
document.getElementById("qr-whatsapp-btn")?.addEventListener("click", () => {
  if (activeQrUrl) window.open(`https://api.whatsapp.com/send?text=${encodeURIComponent(activeQrUrl)}`, "_blank", "noopener,noreferrer");
});
document.getElementById("qr-email-btn")?.addEventListener("click", () => {
  if (activeQrUrl) window.location.href = `mailto:?subject=${encodeURIComponent("LinkNest QR link")}&body=${encodeURIComponent(activeQrUrl)}`;
});

export function initLinkLibrary() {
  if (!initialized) {
    wireCreateForm();
    wireSearch();
    wireTableActions();
    initialized = true;
  }
  loadLinks();
}
