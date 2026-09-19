import { apiFetch, ApiError } from "./api.js";
import { escapeAttr, escapeHtml } from "./dom.js";
import { showToast } from "./toast.js";

let username = "";
let selectedTheme = "minimal_light";
let loaded = false;
let initialized = false;

function refreshPreview() {
  const iframe = document.getElementById("bio-preview-iframe");
  iframe.src = `/bio/${encodeURIComponent(username)}?t=${Date.now()}`;
}

function renderSocialLinks(links = []) {
  const list = document.getElementById("social-links-list");
  if (!links.length) {
    list.innerHTML = `<p class="field-hint">No social links yet. Add your first one below.</p>`;
    return;
  }

  list.innerHTML = links
    .map(
      (link) => `
      <div class="social-link-row" data-id="${escapeAttr(link.id)}">
        <span class="grip" aria-hidden="true">::</span>
        <div class="info">
          <div class="label">${escapeHtml(link.label)}</div>
          <div class="url">${escapeHtml(link.url)}</div>
        </div>
        <button class="btn btn-sm btn-danger-ghost remove-social-btn" type="button" data-id="${escapeAttr(link.id)}">Remove</button>
      </div>`
    )
    .join("");
}

function selectTheme(theme) {
  selectedTheme = theme;
  document.querySelectorAll(".theme-option").forEach((el) => el.classList.toggle("selected", el.dataset.theme === theme));
}

function clearFormErrors(form) {
  form.querySelectorAll(".field").forEach((f) => f.classList.remove("has-error"));
  form.querySelectorAll(".field-error").forEach((el) => (el.textContent = ""));
}

function applyFieldErrors(form, fields = {}) {
  Object.entries(fields).forEach(([name, message]) => {
    const input = form.elements.namedItem(name);
    if (!input) return;
    const field = input.closest(".field");
    if (!field) return;
    field.classList.add("has-error");
    const error = field.querySelector(".field-error");
    if (error) error.textContent = message;
  });
}

async function loadBio() {
  try {
    const { bio } = await apiFetch("/bio");
    document.getElementById("bioDisplayName").value = bio.displayName || "";
    document.getElementById("bioAvatarUrl").value = bio.avatarUrl || "";
    document.getElementById("bioText").value = bio.bio || "";
    selectTheme(bio.theme);
    renderSocialLinks(bio.socialLinks);
    refreshPreview();
  } catch (err) {
    showToast(err.payload?.message || "Couldn't load your bio profile.", "error");
  }
}

function wireProfileForm() {
  const form = document.getElementById("bio-profile-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearFormErrors(form);
    const data = Object.fromEntries(new FormData(form).entries());
    data.theme = selectedTheme;

    const submitBtn = form.querySelector("button[type=submit]");
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = "Saving...";
    try {
      await apiFetch("/bio", { method: "PUT", body: data });
      showToast("Profile saved.");
      refreshPreview();
    } catch (err) {
      if (err instanceof ApiError && err.payload?.fields) {
        applyFieldErrors(form, err.payload.fields);
      } else {
        showToast(err.payload?.message || "Couldn't save profile.", "error");
      }
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = originalText;
    }
  });
}

function wireThemePicker() {
  document.getElementById("theme-grid").addEventListener("click", (e) => {
    const option = e.target.closest(".theme-option");
    if (option) selectTheme(option.dataset.theme);
  });
}

function wireSocialLinks() {
  const addForm = document.getElementById("add-social-form");
  addForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearFormErrors(addForm);
    const data = Object.fromEntries(new FormData(addForm).entries());
    const submitBtn = addForm.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    try {
      const { bio } = await apiFetch("/bio/social-links", { method: "POST", body: data });
      renderSocialLinks(bio.socialLinks);
      addForm.reset();
      refreshPreview();
      showToast("Social link added.");
    } catch (err) {
      if (err instanceof ApiError && err.payload?.fields) applyFieldErrors(addForm, err.payload.fields);
      const firstFieldError = err.payload?.fields ? Object.values(err.payload.fields)[0] : null;
      showToast(err.payload?.message || firstFieldError || "Couldn't add that link.", "error");
    } finally {
      submitBtn.disabled = false;
    }
  });

  document.getElementById("social-links-list").addEventListener("click", async (e) => {
    if (!e.target.classList.contains("remove-social-btn")) return;
    const id = e.target.dataset.id;
    try {
      const { bio } = await apiFetch(`/bio/social-links/${encodeURIComponent(id)}`, { method: "DELETE" });
      renderSocialLinks(bio.socialLinks);
      refreshPreview();
    } catch {
      showToast("Couldn't remove that link.", "error");
    }
  });
}

export function initBioEditor(currentUsername) {
  username = currentUsername;
  if (!initialized) {
    wireProfileForm();
    wireThemePicker();
    wireSocialLinks();
    window.addEventListener("view:bio:shown", () => {
      if (!loaded) {
        loaded = true;
        loadBio();
      }
    });
    initialized = true;
  }
}
