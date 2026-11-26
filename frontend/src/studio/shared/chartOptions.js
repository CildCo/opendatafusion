export const CHART_TYPES = ["card", "line", "bar", "area", "pie", "pivot",
                            "table", "map", "text"];

export const PALETTES = {
  default: ["#2563eb", "#0f766e", "#d97706", "#7c3aed", "#dc2626",
            "#0891b2", "#65a30d", "#9333ea"],
  blue: ["#1d4ed8", "#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe"],
  green: ["#047857", "#059669", "#10b981", "#34d399", "#6ee7b7"],
  warm: ["#b45309", "#d97706", "#ea580c", "#dc2626", "#be123c"],
  mono: ["#0f172a", "#334155", "#64748b", "#94a3b8", "#cbd5e1"],
};

export function paletteOf(format) {
  return PALETTES[format?.palette] || PALETTES.default;
}

export function numberFormatter(mode) {
  if (mode === "percent") {
    return (value) => `${Number(value).toLocaleString("zh-CN")}%`;
  }
  if (mode === "compact") {
    return (value) => new Intl.NumberFormat("zh-CN", {
      notation: "compact", maximumFractionDigits: 1,
    }).format(Number(value));
  }
  if (mode === "number") {
    return (value) => Number(value).toLocaleString("zh-CN");
  }
  return null;
}

function colorFor(index, colors) {
  return colors[index % colors.length];
}

export function buildChartOption({
  type, rows = [], columns = [], dimension, value, format = {},
  mapName = "", currentLabel = "", previousLabel = "",
}) {
  if (!dimension || !rows.length) return null;
  const colors = paletteOf(format);
  const number = numberFormatter(format.numberFormat);
  const labels = rows.map((row) => row[dimension]);
  const values = rows.map((row) => row[value]);
  const showLegend = format.legend !== false;
  const showLabels = format.labels === true;

  if (type === "map") {
    const numbers = values.filter((v) => typeof v === "number");
    return {
      color: colors,
      tooltip: {
        trigger: "item",
        valueFormatter: number || undefined,
      },
      visualMap: {
        min: numbers.length ? Math.min(...numbers) : 0,
        max: numbers.length ? Math.max(...numbers) : 1,
        left: 8, bottom: 8, calculable: true,
        inRange: { color: [colors[colors.length - 1], colors[0]] },
      },
      series: [{
        type: "map", map: mapName,
        data: rows.map((row) => ({
          name: row[dimension], value: row[value],
        })),
        label: { show: showLabels },
        emphasis: { label: { show: true } },
        select: { disabled: true },
      }],
    };
  }

  if (type === "pie") {
    return {
      color: colors,
      tooltip: {
        trigger: "item",
        valueFormatter: number || undefined,
      },
      legend: { show: showLegend },
      series: [{
        type: "pie", radius: format.labels ? "58%" : "65%",
        data: rows.map((row) => ({
          name: row[dimension], value: row[value],
        })),
        label: { show: showLabels },
        itemStyle: { borderColor: "#fff", borderWidth: 1 },
      }],
    };
  }

  const chartType = type === "area" ? "line" : type;
  const previousKey = `${value}_previous`;
  const hasPrevious = rows.some(
    (row) => row[previousKey] !== null && row[previousKey] !== undefined);
  const series = [{
    name: currentLabel || value,
    type: chartType,
    data: values,
    smooth: format.smooth !== false,
    label: { show: showLabels },
    itemStyle: { color: colorFor(0, colors) },
  }];
  if (type === "area") series[0].areaStyle = { opacity: 0.16 };
  if (hasPrevious) {
    series.push({
      name: previousLabel || `${value} (previous)`,
      type: chartType,
      data: rows.map((row) => row[previousKey]),
      smooth: format.smooth !== false,
      label: { show: showLabels },
      lineStyle: { type: "dashed" },
      itemStyle: { color: colorFor(1, colors), opacity: 0.75 },
      areaStyle: type === "area" ? { opacity: 0.08 } : undefined,
    });
  }
  return {
    color: colors,
    tooltip: {
      trigger: "axis",
      valueFormatter: number || undefined,
    },
    legend: hasPrevious || format.legend ? { show: showLegend } : undefined,
    grid: {
      left: 52, right: 20, top: hasPrevious || format.legend ? 42 : 24,
      bottom: 38,
    },
    xAxis: {
      type: "category", data: labels,
      name: format.xTitle || "",
      nameLocation: "middle", nameGap: 26,
    },
    yAxis: {
      type: "value",
      name: format.yTitle || "",
      nameLocation: "middle", nameGap: 42,
      axisLabel: number ? { formatter: number } : {},
    },
    series,
  };
}
