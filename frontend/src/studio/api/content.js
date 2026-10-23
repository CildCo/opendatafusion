export function emptyContent() {
  return {
    mode: "visual",
    query: {
      datasource_id: null, table: "", select: [], filters: [],
      group_by: [], order_by: [], limit: 1000,
    },
    sql: "",
    params: [],
    auth: { type: "aksk", rate_limit_per_min: 60 },
  };
}

export function normalizeContent(c) {
  const out = JSON.parse(JSON.stringify(c || emptyContent()));
  out.params = out.params || [];
  out.mode = out.mode || "visual";
  out.query = out.query || emptyContent().query;
  out.query.select = out.query.select || [];
  out.query.filters = out.query.filters || [];
  out.query.group_by = out.query.group_by || [];
  out.query.order_by = out.query.order_by || [];
  out.sql = out.sql || "";
  return out;
}
