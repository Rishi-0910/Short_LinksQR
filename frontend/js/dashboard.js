import { apiFetch, setAccessToken, getAccessToken } from "./api.js";
import { initLinkLibrary } from "./linkLibrary.js";
import { initAnalytics } from "./analyticsCharts.js";
import { initBioEditor } from "./bioEditor.js";
import { initThemeToggle } from "./theme.js";

const views = {
  overview: document.getElementById("view-links"),
  insights: document.getElementById("view-analytics"),
  bio: document.getElementById("view-bio"),
};

initThemeToggle();

function switchView(name) {
  Object.entries(views).forEach(([key, el]) => el?.classList.toggle("active", key === name));
  document.querySelectorAll(".nav-link").forEach((link) => link.classList.toggle("active", link.dataset.view === name));
  if (name === "insights") window.dispatchEvent(new CustomEvent("view:analytics:shown"));
  if (name === "bio") window.dispatchEvent(new CustomEvent("view:bio:shown"));
}

document.querySelectorAll(".nav-link").forEach((link) => {
  link.addEventListener("click", () => switchView(link.dataset.view));
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  try {
    await apiFetch("/auth/logout", { method: "POST" });
  } finally {
    setAccessToken(null);
    window.location.href = "/login.html";
  }
});

async function bootstrap() {
  // No access token yet? Try the httpOnly refresh cookie before giving up --
  // this is what lets a returning visitor skip the login form entirely.
  if (!getAccessToken()) {
    try {
      const refreshed = await apiFetch("/auth/refresh", { method: "POST", skipAuthRetry: true });
      setAccessToken(refreshed.accessToken);
    } catch {
      window.location.href = "/login.html";
      return;
    }
  }

  try {
    const { user } = await apiFetch("/auth/me");
    document.getElementById("user-name").textContent = user.displayName || user.username;
    document.getElementById("user-email").textContent = user.email;
    document.getElementById("user-initial").textContent = (user.displayName || user.username || "?")[0].toUpperCase();
    document.getElementById("public-bio-link").href = `/bio/${user.username}`;
    document.getElementById("public-bio-link").textContent = `/bio/${user.username}`;

    initLinkLibrary();
    initAnalytics();
    initBioEditor(user.username);
  } catch {
    window.location.href = "/login.html";
  }
}

bootstrap();
