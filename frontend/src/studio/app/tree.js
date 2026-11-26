export const CONTAINER_TYPES = ["container", "tabs", "modal"];

export function isContainer(component) {
  return CONTAINER_TYPES.includes(component?.type);
}

export function flatten(components, depth = 0, parent = null,
                        tabId = null, path = [], out = []) {
  for (const [index, comp] of (components || []).entries()) {
    if (!comp || typeof comp !== "object") continue;
    const row = {
      comp, depth, index, list: components, parent, tabId,
      path: [...path, comp.id],
    };
    out.push(row);
    if (comp.type === "container" || comp.type === "modal") {
      flatten(comp.children || [], depth + 1, comp, null,
              row.path, out);
    } else if (comp.type === "tabs") {
      for (const tab of comp.tabs || []) {
        flatten(tab.components || [], depth + 1, comp, tab.id,
                row.path, out);
      }
    }
  }
  return out;
}

export function findComponent(components, id) {
  return flatten(components).find((row) => row.comp.id === id)?.comp || null;
}

export function findRow(components, id) {
  return flatten(components).find((row) => row.comp.id === id) || null;
}

export function collectIds(components) {
  return new Set(flatten(components).map((row) => row.comp.id));
}

export function removeComponent(components, id) {
  const row = findRow(components, id);
  if (!row) return false;
  const index = row.list.indexOf(row.comp);
  if (index >= 0) row.list.splice(index, 1);
  return true;
}

export function childListFor(component, tabId = null) {
  if (!component) return null;
  if (component.type === "container" || component.type === "modal") {
    if (!Array.isArray(component.children)) component.children = [];
    return component.children;
  }
  if (component.type === "tabs") {
    const tab = (component.tabs || []).find((item) => item.id === tabId)
      || component.tabs?.[0];
    if (!tab) return null;
    if (!Array.isArray(tab.components)) tab.components = [];
    return tab.components;
  }
  return null;
}

export function labelOf(comp, typeLabel) {
  return comp?.title || comp?.label || (typeLabel ? typeLabel(comp.type) : comp?.type);
}
