// Geometry mirrors board.py reached(); this previews reach, not placement legality.
export function marketingPreviews(state, draft) {
  if (state.phase !== "work") return [];
  const b = state.board;
  return (draft?.work?.market || []).flatMap((row, index) => {
    const tile = state.campaign_tiles[row.campaign_id];
    if (!tile) return [];
    const width = row.rotate ? tile.height : tile.width;
    const height = row.rotate ? tile.width : tile.height;
    const cells = [];
    const plane = tile.kind === "airplane";
    if (!["airplane", "guide", "giant_billboard"].includes(tile.kind)) {
      if (!row.position?.every(Number.isInteger)) return [];
      for (let y = 0; y < height; y++)
        for (let x = 0; x < width; x++)
          cells.push([row.position[0] + x, row.position[1] + y]);
    }
    const side = row.side || "left",
      offset = Number(row.offset || 0);
    if (plane && !Number.isInteger(offset)) return [];
    const horizontal = ["left", "right"].includes(side);
    const line = row.edge_tile
      ? {
          left: row.edge_tile[0] * 5,
          right: row.edge_tile[0] * 5 + 5,
          top: row.edge_tile[1] * 5,
          bottom: row.edge_tile[1] * 5 + 5,
        }[side]
      : { left: 0, right: b.width, top: 0, bottom: b.height }[side];
    const seen = new Set(cells.map((p) => p.join(",")));
    if (tile.kind === "mailbox") {
      const queue = [...cells];
      for (let i = 0; i < queue.length; i++) {
        const [x, y] = queue[i];
        for (const q of [
          [x - 1, y],
          [x + 1, y],
          [x, y - 1],
          [x, y + 1],
        ]) {
          const [a, z] = q,
            key = q.join(",");
          if (
            a >= 0 &&
            z >= 0 &&
            a < b.width &&
            z < b.height &&
            !["road", "bridge"].includes(b.cells[z][a]) &&
            !seen.has(key)
          ) {
            seen.add(key);
            queue.push(q);
          }
        }
      }
    }
    const houses = b.houses.filter((h) => {
      if (tile.kind === "guide") return h.garden;
      if (tile.kind === "giant_billboard") return false;
      return h.cells.some((p) => {
        if (plane)
          return (
            p[horizontal ? 1 : 0] >= offset &&
            p[horizontal ? 1 : 0] < offset + tile.width
          );
        if (tile.kind === "mailbox") return seen.has(p.join(","));
        return cells.some((a) =>
          tile.kind === "billboard"
            ? Math.abs(a[0] - p[0]) + Math.abs(a[1] - p[1]) === 1
            : Math.max(
                Math.abs(Math.floor(a[0] / 5) - Math.floor(p[0] / 5)),
                Math.abs(Math.floor(a[1] / 5) - Math.floor(p[1] / 5)),
              ) <= 1,
        );
      });
    });
    return [
      {
        ...row,
        index,
        kind: tile.kind,
        width,
        height,
        cells,
        houses,
        horizontal,
        line,
        offset,
        side,
        span: tile.width,
      },
    ];
  });
}
