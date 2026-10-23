const TOKEN_KEY = "odf_token";
const ROLE_KEY = "odf_role";
const PROJECT_KEY = "odf_project";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const getRole = () => localStorage.getItem(ROLE_KEY);
export const getProject = () => Number(localStorage.getItem(PROJECT_KEY) || 0);
export const setProject = (id) => localStorage.setItem(PROJECT_KEY, String(id));
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearSession = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(PROJECT_KEY);
};

async function request(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = "Bearer " + token;
  let r;
  try {
    r = await fetch("/api/v1" + path, { ...opts, headers });
  } catch (e) {
    throw new Error("网络不可达，请检查服务是否在运行");
  }
  if (r.status === 401) {
    clearSession();
    if (!location.hash.startsWith("#/login")) location.hash = "#/login";
    throw new Error("未登录或会话已过期");
  }
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const body = await r.json();
      const detail = body.detail || body.message;
      if (typeof detail === "string") msg = detail;
      else if (detail && Array.isArray(detail.errors)) {
        msg = detail.errors
          .map((e) => (typeof e === "string" ? e : e.message || JSON.stringify(e)))
          .join("; ");
      } else if (detail) {
        msg = JSON.stringify(detail);
      }
    } catch (e) {
      /* keep default */
    }
    throw new Error(msg);
  }
  if (r.status === 204) return null;
  const text = await r.text();
  return text ? JSON.parse(text) : null;
}

async function applyChange(action, target, payload = {}) {
  const c = await request("/changes", {
    method: "POST",
    body: JSON.stringify({ project_id: 1, action, target, payload }),
  });
  const a = await request(`/changes/${c.id}/approve`, {
    method: "POST",
    body: "{}",
  });
  return request(
    `/changes/${c.id}/apply?approval_token=${encodeURIComponent(a.approval_token)}`,
    { method: "POST", body: "{}" }
  );
}

export const api = {
  get: (p) => request(p),
  post: (p, b) => request(p, { method: "POST", body: JSON.stringify(b ?? {}) }),
  put: (p, b) => request(p, { method: "PUT", body: JSON.stringify(b ?? {}) }),
  del: (p) => request(p, { method: "DELETE" }),
  applyChange,
  tablesOf: (dsId) => request(`/datasources/${dsId}/tables`),
  datasetDetail: (id) => request(`/catalog/datasets/${id}`),
  flowRuns: (id) => request(`/flows/${id}/runs`),
  flowVersions: (id) => request(`/flows/${id}/versions`),
  switchProject: async (project_id) => {
    const r = await request("/auth/switch-project", {
      method: "POST",
      body: JSON.stringify({ project_id }),
    });
    setToken(r.token);
    setProject(project_id);
    return r;
  },
  login: async (username, password, project_id = 1, otp = "") => {
    const r = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, project_id, otp }),
    });
    if (!r.ok) {
      let msg = "用户名或密码错误";
      try {
        const b = await r.json();
        msg = b.detail || msg;
      } catch (e) {
        /* ignore */
      }
      throw new Error(msg);
    }
    const data = await r.json();
    setToken(data.token);
    const me = await request("/auth/me");
    localStorage.setItem(ROLE_KEY, me.role || "viewer");
    setProject(project_id);
    return me;
  },
};

export function errMsg(e) {
  return e && e.message ? e.message : String(e);
}
