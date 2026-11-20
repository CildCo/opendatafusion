export const ENTITY_META = {
  source: { icon: "Coin", color: "#0f766e" },
  datasource: { icon: "Coin", color: "#0f766e" },
  table: { icon: "Grid", color: "#1d4ed8" },
  dataset: { icon: "Collection", color: "#1d4ed8" },
  metric: { icon: "DataAnalysis", color: "#7c3aed" },
  pipeline: { icon: "Share", color: "#0e7490" },
  flow: { icon: "Switch", color: "#0e7490" },
  dashboard: { icon: "Odometer", color: "#b45309" },
  app: { icon: "Grid", color: "#b45309" },
  api: { icon: "Connection", color: "#1d4ed8" },
  interface: { icon: "Promotion", color: "#1d4ed8" },
  cdc: { icon: "DataLine", color: "#0f766e" },
  connector: { icon: "DataLine", color: "#0f766e" },
  quality: { icon: "CircleCheck", color: "#15803d" },
  alert: { icon: "Bell", color: "#b91c1c" },
  user: { icon: "User", color: "#475569" },
  file: { icon: "Document", color: "#475569" },
  engine: { icon: "Cpu", color: "#475569" },
  job: { icon: "Cpu", color: "#475569" },
  dependency: { icon: "Switch", color: "#475569" },
  webhook: { icon: "Promotion", color: "#7c3aed" },
  change: { icon: "Switch", color: "#0f766e" },
  tool: { icon: "Connection", color: "#475569" },
  audit: { icon: "Document", color: "#475569" },
  workspace: { icon: "Setting", color: "#475569" },
  security: { icon: "Lock", color: "#475569" },
  grant: { icon: "Key", color: "#1d4ed8" },
};

export function entityMeta(type) {
  return ENTITY_META[type] || { icon: "Grid", color: "#475569" };
}
