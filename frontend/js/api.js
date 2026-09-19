/**
 * Thin fetch wrapper around the JSON API.
 *
 * The access token lives in memory + sessionStorage (never localStorage,
 * never a cookie) so it survives a page refresh within the same tab but
 * disappears when the tab closes -- the refresh token in the httpOnly
 * cookie is what actually re-establishes a session long-term.
 */
const API_BASE = "/api";
const REQUEST_TIMEOUT_MS = 12000;
let accessToken = sessionStorage.getItem("ln_access_token") || null;
let refreshInFlight = null;

export function setAccessToken(token) {
  accessToken = token;
  if (token) sessionStorage.setItem("ln_access_token", token);
  else sessionStorage.removeItem("ln_access_token");
}

export function getAccessToken() {
  return accessToken;
}

async function refreshAccessToken() {
  // De-dupe concurrent refreshes (e.g. three panels all get a 401 at once).
  if (!refreshInFlight) {
    refreshInFlight = apiFetch("/auth/refresh", { method: "POST", skipAuthRetry: true })
      .then(async (res) => {
        if (!res?.accessToken) throw new Error("refresh_failed");
        setAccessToken(res.accessToken);
        return res.accessToken;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

/**
 * apiFetch(path, { method, body, skipAuthRetry }) -> parsed JSON
 * Throws an ApiError with .status and .payload on non-2xx responses.
 */
export class ApiError extends Error {
  constructor(status, payload) {
    super(payload?.message || "Request failed.");
    this.status = status;
    this.payload = payload;
  }
}

export async function apiFetch(path, { method = "GET", body, skipAuthRetry = false } = {}) {
  if (!path.startsWith("/")) throw new ApiError(400, { message: "Invalid API path." });

  const headers = { "Content-Type": "application/json" };
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      credentials: "include",
      signal: controller.signal,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    const message = err.name === "AbortError" ? "Request timed out. Please try again." : "Network error. Please try again.";
    throw new ApiError(0, { message });
  } finally {
    window.clearTimeout(timeout);
  }

  // Transparent token refresh: one retry, only once per call chain.
  if (res.status === 401 && !skipAuthRetry && path !== "/auth/refresh" && path !== "/auth/login") {
    try {
      await refreshAccessToken();
      return apiFetch(path, { method, body, skipAuthRetry: true });
    } catch {
      setAccessToken(null);
      window.location.href = "/login.html?sessionExpired=1";
      throw new ApiError(401, { message: "Session expired." });
    }
  }

  let payload = null;
  try {
    payload = await res.json();
  } catch {
    payload = null;
  }

  if (!res.ok) throw new ApiError(res.status, payload);
  return payload;
}
