const TOKEN = /\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\}\}/g;

function display(value) {
  if (value === null || value === undefined) return "";
  return String(value);
}

function resolvePath(context, path) {
  if (path.startsWith("params.")) {
    const rest = path.slice(7).split(".");
    let value = context.params;
    for (const key of rest) {
      if (value === null || value === undefined) return undefined;
      value = value[key];
    }
    return value;
  }
  if (path.startsWith("components.")) {
    const rest = path.slice(11).split(".");
    let value = context.components;
    for (const key of rest) {
      if (value === null || value === undefined) return undefined;
      value = value[key];
    }
    return value;
  }
  return Object.prototype.hasOwnProperty.call(context.params || {}, path)
    ? context.params[path] : undefined;
}

export function interpolate(text, params, {
  keepMissing = false, components = {},
} = {}) {
  if (typeof text !== "string") return "";
  const context = { params: params || {}, components: components || {} };
  return text.replace(TOKEN, (match, path) => {
    const value = resolvePath(context, path);
    if (value === undefined) return keepMissing ? match : "";
    return display(value);
  });
}

function same(a, b) {
  return display(a) === display(b);
}

export function rolesAllow(item, role = "") {
  const roles = item?.visible_roles;
  return !roles || !roles.length || roles.includes(role);
}

export function isVisible(component, params, role = "") {
  if (!rolesAllow(component, role)) return false;
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

export function highlightTone(component, params) {
  const rule = component?.highlight_when;
  if (!rule || !rule.param) return "";
  const enabled = isVisible({ visible_when: rule }, params);
  return enabled ? (rule.tone || "") : "";
}

export function visualStyle(component) {
  const style = component?.style;
  if (!style || typeof style !== "object") return {};
  const out = {};
  if (style.background) out.background = style.background;
  if (style.color) out.color = style.color;
  if (style.align) out.textAlign = style.align;
  if (style.padding !== undefined) out.padding = `${style.padding}px`;
  if (style.radius !== undefined) {
    out.borderRadius = `${style.radius}px`;
  }
  if (style.font_size !== undefined) {
    out.fontSize = `${style.font_size}px`;
  }
  return out;
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
    case "container":
      return { w: 6, h: 4 };
    case "tabs":
      return { w: 12, h: 5 };
    case "modal":
      return { w: 3, h: 2 };
    case "upload":
      return { w: 4, h: 3 };
    case "approval":
      return { w: 12, h: 5 };
    case "list":
      return { w: 6, h: 6 };
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
