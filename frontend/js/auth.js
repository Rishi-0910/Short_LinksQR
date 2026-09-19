import { apiFetch, setAccessToken, ApiError } from "./api.js";

function showBanner(el, message, type = "error") {
  if (!el) return;
  el.textContent = message;
  el.className = `banner show banner-${type}`;
}

function clearFieldErrors(form) {
  form.querySelectorAll(".field").forEach((f) => f.classList.remove("has-error"));
  form.querySelectorAll(".field-error").forEach((e) => (e.textContent = ""));
}

function applyFieldErrors(form, fields = {}) {
  Object.entries(fields).forEach(([name, message]) => {
    const input = form.querySelector(`[name="${name}"]`);
    if (!input) return;
    const field = input.closest(".field");
    field.classList.add("has-error");
    field.querySelector(".field-error").textContent = message;
  });
}

function setLoading(button, loading) {
  button.disabled = loading;
  button.dataset.originalText = button.dataset.originalText || button.textContent;
  button.innerHTML = loading
    ? `<span class="spinner"></span> Please wait...`
    : button.dataset.originalText;
}

/* ---------------------------- Real-time validation ---------------------------- */
function wireLiveValidation(form) {
  form.querySelectorAll("input[data-validate]").forEach((input) => {
    input.addEventListener("input", () => {
      const field = input.closest(".field");
      field.classList.remove("has-error");
      const rule = input.dataset.validate;
      let message = "";
      if (rule === "email" && input.value && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(input.value)) {
        message = "Enter a valid email address.";
      }
      if (rule === "username" && input.value && !/^[a-zA-Z0-9_]{3,30}$/.test(input.value)) {
        message = "3-30 characters: letters, numbers, underscore only.";
      }
      if (rule === "password" && input.value && input.value.length < 8) {
        message = "At least 8 characters.";
      }
      if (message) {
        field.classList.add("has-error");
        field.querySelector(".field-error").textContent = message;
      }
    });
  });
}

/* ---------------------------- Signup ---------------------------- */
const signupForm = document.getElementById("signup-form");
if (signupForm) {
  wireLiveValidation(signupForm);
  signupForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearFieldErrors(signupForm);
    const banner = document.getElementById("auth-banner");
    const submitBtn = signupForm.querySelector("button[type=submit]");
    const data = Object.fromEntries(new FormData(signupForm).entries());

    setLoading(submitBtn, true);
    try {
      const result = await apiFetch("/auth/signup", { method: "POST", body: data });
      // Dev-mode convenience: since there's no real inbox, surface the
      // verification link right in the UI instead of a 500-step email hunt.
      const devBanner = document.getElementById("dev-hint");
      if (result.devVerificationToken && devBanner) {
        const link = document.createElement("a");
        link.href = `/verify-email.html?token=${encodeURIComponent(result.devVerificationToken)}`;
        link.textContent = "verify now";
        devBanner.replaceChildren("Simulated email sent. Dev shortcut: ", link, ".");
        devBanner.classList.add("show");
      }
      showBanner(banner, "Account created. Check the verification link above.", "success");
      signupForm.reset();
    } catch (err) {
      if (err instanceof ApiError && err.payload?.fields) applyFieldErrors(signupForm, err.payload.fields);
      showBanner(banner, err.payload?.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(submitBtn, false);
    }
  });
}

/* ---------------------------- Login ---------------------------- */
const loginForm = document.getElementById("login-form");
if (loginForm) {
  const params = new URLSearchParams(window.location.search);
  if (params.get("sessionExpired")) {
    showBanner(document.getElementById("auth-banner"), "Your session expired. Please log in again.");
  }

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearFieldErrors(loginForm);
    const banner = document.getElementById("auth-banner");
    const submitBtn = loginForm.querySelector("button[type=submit]");
    const data = Object.fromEntries(new FormData(loginForm).entries());

    setLoading(submitBtn, true);
    try {
      const result = await apiFetch("/auth/login", { method: "POST", body: data, skipAuthRetry: true });
      setAccessToken(result.accessToken);
      window.location.href = "/index.html";
    } catch (err) {
      showBanner(banner, err.payload?.message || "Unable to log in.");
    } finally {
      setLoading(submitBtn, false);
    }
  });
}

/* ---------------------------- Forgot password ---------------------------- */
const forgotForm = document.getElementById("forgot-form");
if (forgotForm) {
  forgotForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const banner = document.getElementById("auth-banner");
    const submitBtn = forgotForm.querySelector("button[type=submit]");
    const data = Object.fromEntries(new FormData(forgotForm).entries());

    setLoading(submitBtn, true);
    try {
      const result = await apiFetch("/auth/forgot-password", { method: "POST", body: data });
      showBanner(banner, result.message, "success");
      forgotForm.reset();
    } catch (err) {
      showBanner(banner, err.payload?.message || "Something went wrong.");
    } finally {
      setLoading(submitBtn, false);
    }
  });
}

/* ---------------------------- Reset password ---------------------------- */
const resetForm = document.getElementById("reset-form");
if (resetForm) {
  const token = new URLSearchParams(window.location.search).get("token") || "";
  resetForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearFieldErrors(resetForm);
    const banner = document.getElementById("auth-banner");
    const submitBtn = resetForm.querySelector("button[type=submit]");
    const password = new FormData(resetForm).get("password");

    setLoading(submitBtn, true);
    try {
      await apiFetch("/auth/reset-password", { method: "POST", body: { token, password } });
      showBanner(banner, "Password updated. Redirecting to login...", "success");
      setTimeout(() => (window.location.href = "/login.html"), 1500);
    } catch (err) {
      showBanner(banner, err.payload?.message || "This reset link is invalid or expired.");
    } finally {
      setLoading(submitBtn, false);
    }
  });
}

/* ---------------------------- Verify email ---------------------------- */
const verifyStatus = document.getElementById("verify-status");
if (verifyStatus) {
  const token = new URLSearchParams(window.location.search).get("token") || "";
  (async () => {
    if (!token) {
      showBanner(verifyStatus, "Missing verification token.");
      return;
    }
    try {
      const result = await apiFetch("/auth/verify-email", { method: "POST", body: { token } });
      showBanner(verifyStatus, result.message, "success");
    } catch (err) {
      showBanner(verifyStatus, err.payload?.message || "Verification failed.");
    }
  })();
}
