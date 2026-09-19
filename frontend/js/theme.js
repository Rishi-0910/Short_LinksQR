const STORAGE_KEY = "linknest-theme";

export function getStoredTheme() {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function systemPrefersDark() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

export function applyTheme(theme) {
  const resolved = theme === "dark" || theme === "light" ? theme : (systemPrefersDark() ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", resolved);
  return resolved;
}

function setStoredTheme(theme) {
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Storage can be unavailable (private browsing, quota) -- theme still
    // applies for this page load, it just won't persist across visits.
  }
}

function updateToggleUi(button, theme) {
  if (!button) return;
  const isDark = theme === "dark";
  button.setAttribute("aria-pressed", String(isDark));
  button.setAttribute("title", isDark ? "Switch to light mode" : "Switch to dark mode");
  const icon = button.querySelector(".theme-toggle-icon");
  if (icon) icon.textContent = isDark ? "☀️" : "🌙";
  const label = button.querySelector(".theme-toggle-label");
  if (label) label.textContent = isDark ? "Light mode" : "Dark mode";
}

/**
 * Wires up a theme toggle button by id. Safe to call on pages that don't
 * have the button (e.g. if a page opts out) -- it just no-ops.
 */
export function initThemeToggle(buttonId = "theme-toggle-btn") {
  const current = applyTheme(getStoredTheme());
  const button = document.getElementById(buttonId);
  updateToggleUi(button, current);

  button?.addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
    setStoredTheme(next);
    updateToggleUi(button, next);
  });
}
