const TOKEN = /\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g;

function display(value) {
  if (value === null || value === undefined) return "";
  return String(value);
}

export function interpolate(text, params, { keepMissing = false } = {}) {
  if (typeof text !== "string") return "";
  const values = params || {};
  return text.replace(TOKEN, (match, name) => {
    if (!Object.prototype.hasOwnProperty.call(values, name)) {
      return keepMissing ? match : "";
    }
    return display(values[name]);
  });
}

function same(a, b) {
  return display(a) === display(b);
}

export function isVisible(component, params) {
  const rule = component?.visible_when;
  if (!rule || !rule.param) return true;
  const value = (params || {})[rule.param];
  if (rule.op === "!=") return !same(value, rule.value);
  if (rule.op === "in") {
    const list = Array.isArray(rule.value) ? rule.value : [rule.value];
    return list.some((item) => same(item, value));
  }
  return same(value, rule.value);
}

export function progressValue(component, params) {
  if (component?.value_param) {
    const raw = Number((params || {})[component.value_param]);
    if (Number.isFinite(raw)) return Math.max(0, Math.min(100, raw));
  }
  const value = Number(component?.value);
  return Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0;
}

export const LAYOUT_WIDTHS = 12;

export function defaultSize(type) {
  switch (type) {
    case "heading":
    case "divider":
      return { w: 12, h: 1 };
    case "text":
      return { w: 6, h: 3 };
    case "image":
      return { w: 4, h: 3 };
    case "button":
      return { w: 3, h: 2 };
    case "progress":
      return { w: 4, h: 1 };
    case "metric":
      return { w: 3, h: 2 };
    case "form":
      return { w: 6, h: 5 };
    default:
      return { w: 12, h: 5 };
  }
}

export function nextLayout(components, type) {
  const size = defaultSize(type);
  let bottom = 0;
  for (const item of components || []) {
    if (item.layout) bottom = Math.max(bottom, item.layout.y + item.layout.h);
  }
  return { x: 0, y: bottom, w: size.w, h: size.h };
}

export function normalizeLayouts(content) {
  for (const page of content?.pages || []) {
    for (const item of page.components || []) {
      if (!item.layout) item.layout = nextLayout(page.components, item.type);
    }
  }
  return content;
}
