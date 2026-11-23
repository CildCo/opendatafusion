const PREFIX = "odf_pref_";

export function loadPrefs(key, defaults) {
  try {
    const raw = JSON.parse(localStorage.getItem(PREFIX + key) || "null");
    return raw && typeof raw === "object" ? { ...defaults, ...raw } : defaults;
  } catch {
    return defaults;
  }
}

export function savePrefs(key, value) {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    /* storage may be unavailable */
  }
}
