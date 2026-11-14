export async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (res.status === 401 && location.pathname !== "/login") {
    location.href = "/login?next=" + encodeURIComponent(location.pathname + location.hash);
    throw new Error("Not signed in");
  }
  if (!res.ok) {
    const msg = (data && data.detail) ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

export const get = (p) => api(p);
export const post = (p, body = {}) => api(p, { method: "POST", body });
export const put = (p, body) => api(p, { method: "PUT", body });
export const del = (p) => api(p, { method: "DELETE" });

export const fileUrl = (pid, rel) => (rel ? `/api/projects/${pid}/file/${rel}?t=${Date.now() % 100000}` : null);

export async function waitJob(jobId, onUpdate, intervalMs = 1200) {
  for (;;) {
    const j = await get(`/jobs/${jobId}`);
    onUpdate && onUpdate(j);
    if (["done", "failed", "cancelled", "needs_approval"].includes(j.status)) return j;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

export const fmtTime = (ts) => (ts ? new Date(ts * 1000).toLocaleString() : "");
export const usd = (v) => `$${Number(v || 0).toFixed(v >= 1 ? 2 : 3)}`;

export const isLocal = () => ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
