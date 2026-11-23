const KEY = "odf_recent";
const LIMIT = 8;

export function loadRecent() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(raw) ? raw.slice(0, LIMIT) : [];
  } catch {
    return [];
  }
}

export function pushRecent(entry) {
  if (!entry || !entry.route) return;
  const items = loadRecent().filter((x) => x.route !== entry.route);
  items.unshift(entry);
  localStorage.setItem(KEY, JSON.stringify(items.slice(0, LIMIT)));
}
