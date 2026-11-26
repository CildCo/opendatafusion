export function cellWidthFor(width, columns) {
  return Math.max(32, (width - 8) / columns);
}

export function gridStyleFor(layout, cellWidth, rowHeight) {
  return {
    left: `${layout.x * cellWidth + 4}px`,
    top: `${layout.y * rowHeight + 4}px`,
    width: `${layout.w * cellWidth - 8}px`,
    height: `${layout.h * rowHeight - 8}px`,
  };
}

export function maxGridBottom(items, getLayout) {
  return (items || []).reduce(
    (bottom, item) => Math.max(bottom, getLayout(item).y + getLayout(item).h),
    0);
}

export function resolveGridCollisions(items, moved, getLayout) {
  const target = getLayout(moved);
  const others = (items || [])
    .filter((item) => item.id !== moved.id)
    .sort((a, b) => {
      const left = getLayout(a);
      const right = getLayout(b);
      return left.y - right.y || left.x - right.x;
    });
  let floor = target.y + target.h;
  for (const item of others) {
    const layout = getLayout(item);
    const xOverlap = target.x < layout.x + layout.w
      && layout.x < target.x + target.w;
    if (!xOverlap) continue;
    if (layout.y < floor && layout.y + layout.h > target.y) {
      layout.y = floor;
    }
    floor = Math.max(floor, layout.y + layout.h);
  }
}
