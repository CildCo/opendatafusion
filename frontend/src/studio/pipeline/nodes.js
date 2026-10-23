export const NODE_DEFS = {
  source: { label: "数据源", color: "#2563eb" },
  filter: { label: "过滤", color: "#7c3aed" },
  select: { label: "选列", color: "#0891b2" },
  rename: { label: "重命名", color: "#0891b2" },
  cast: { label: "类型转换", color: "#0891b2" },
  join: { label: "关联", color: "#db2777" },
  aggregate: { label: "聚合", color: "#db2777" },
  union: { label: "并集", color: "#db2777" },
  dedupe: { label: "去重", color: "#db2777" },
  quality: { label: "质量校验", color: "#db2777" },
  sink: { label: "目标", color: "#059669" },
};

export function newNode(type, index) {
  const def = NODE_DEFS[type];
  return {
    id: `${type}_${Date.now()}_${index}`,
    type: "default",
    label: `${def.label} ${index}`,
    position: { x: 120 + index * 60, y: 120 + index * 40 },
    data: { kind: type, name: `${def.label} ${index}`, config: {} },
  };
}

export function toFlowNodes(nodes) {
  return (nodes || []).map((n) => ({
    id: n.id,
    type: "default",
    label: n.name || n.id,
    position: n.position || { x: 0, y: 0 },
    data: {
      kind: n.type,
      name: n.name || n.id,
      config: n.config || {},
    },
  }));
}

export function toFlowEdges(edges) {
  return (edges || []).map((e, i) => ({
    id: `e${i}`,
    source: e.from,
    target: e.to,
    data: { to_port: e.to_port },
  }));
}
