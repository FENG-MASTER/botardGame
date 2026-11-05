import { el, button, badge } from "./dom.js";
import { colors, products, productIcons, campaignNames } from "./labels.js";
const NS = "http://www.w3.org/2000/svg";
function svg(tag, props = {}, ...kids) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(props)) {
    if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const c of kids.flat())
    if (c !== null && c !== undefined)
      n.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return n;
}
const rect = (x, y, w, h, fill, more = {}) =>
  svg("rect", { x, y, width: w, height: h, fill, ...more });
const text = (x, y, value, more = {}) =>
  svg(
    "text",
    { x, y, "text-anchor": "middle", "dominant-baseline": "middle", ...more },
    value,
  );
const bounds = (cells) => {
  const xs = cells.map((c) => c[0]),
    ys = cells.map((c) => c[1]);
  return {
    x: Math.min(...xs),
    y: Math.min(...ys),
    w: Math.max(...xs) - Math.min(...xs) + 1,
    h: Math.max(...ys) - Math.min(...ys) + 1,
  };
};
export function renderBoard(
  state,
  {
    pid,
    options,
    draft,
    pick,
    onCell,
    onPickEnd,
    zoom = 100,
    onZoom,
    inspected,
    onInspect,
  },
) {
  const b = state.board;
  const unit = 36;
  const pad = 24;
  const canvas = svg("svg", {
    viewBox: `0 0 ${b.width * unit + pad * 2} ${b.height * unit + pad * 2}`,
    class: "city-board",
    role: "img",
    "aria-label": "城市地图，可点击格子选择餐厅和广告位置",
  });
  canvas.append(
    svg(
      "defs",
      {},
      svg(
        "pattern",
        { id: "grain", width: 8, height: 8, patternUnits: "userSpaceOnUse" },
        rect(0, 0, 8, 8, "#e6ecdf"),
        svg("circle", { cx: 2, cy: 3, r: 0.55, fill: "#cfd9c4" }),
      ),
    ),
  );
  canvas.append(
    rect(0, 0, b.width * unit + pad * 2, b.height * unit + pad * 2, "#f7f4eb", {
      rx: 12,
    }),
  );
  const scene = svg("g", { transform: `translate(${pad},${pad})` });
  canvas.append(scene);
  for (let y = 0; y < b.height; y++)
    for (let x = 0; x < b.width; x++) {
      const c = b.cells[y][x],
        isRoad = c === "road" || c === "bridge";
      scene.append(
        rect(
          x * unit,
          y * unit,
          unit,
          unit,
          isRoad ? "#dedbd0" : "url(#grain)",
          { stroke: "#f2f1e8", "stroke-width": 0.6 },
        ),
      );
      if (isRoad) {
        const road = (a, z) =>
          b.cells[z]?.[a] === "road" || b.cells[z]?.[a] === "bridge";
        if (road(x - 1, y) || road(x + 1, y))
          scene.append(
            svg("path", {
              d: `M${x * unit},${y * unit + 18}h36`,
              stroke: "#f8f6ee",
              "stroke-dasharray": "5 4",
              "stroke-width": 1.4,
            }),
          );
        if (road(x, y - 1) || road(x, y + 1))
          scene.append(
            svg("path", {
              d: `M${x * unit + 18},${y * unit}v36`,
              stroke: "#f8f6ee",
              "stroke-dasharray": "5 4",
              "stroke-width": 1.4,
            }),
          );
        if (c === "bridge")
          scene.append(
            rect(x * unit + 11, y * unit, 14, 36, "#bab9b0", {
              stroke: "#f4f0e4",
              "stroke-width": 2,
            }),
          );
      } else if (products[c]) {
        scene.append(
          svg("circle", {
            cx: x * unit + 18,
            cy: y * unit + 18,
            r: 12,
            fill: "#fff9e8",
          }),
          text(x * unit + 18, y * unit + 19, productIcons[c], {
            "font-size": 17,
          }),
        );
      }
    }
  for (const tile of b.tiles || []) {
    const size = 5 * unit,
      x = tile.x * size,
      y = tile.y * size;
    scene.append(
      svg("image", {
        href: `/assets/fcm/tiles/${tile.id}.jpg`,
        x,
        y,
        width: size,
        height: size,
        transform: `rotate(${tile.rotation * 90} ${x + size / 2} ${y + size / 2})`,
      }),
    );
  }
  for (const feature of state.built_features || []) {
    for (const [x, y] of feature.cells) {
      const c = b.cells[y][x];
      scene.append(
        rect(
          x * unit,
          y * unit,
          unit,
          unit,
          c === "construction"
            ? "#eac573"
            : feature.kind === "park"
              ? "#7d9a60"
              : "#b9b8ad",
          { stroke: "#f5edd8", "stroke-width": 1 },
        ),
      );
      if (c === "construction")
        scene.append(
          text(x * unit + 18, y * unit + 18, "⚒", { "font-size": 22 }),
        );
    }
  }
  for (const [x, y] of state.roadworks || [])
    scene.append(
      text(x * unit + 18, y * unit + 18, "⚠", {
        "font-size": 22,
        fill: "#a8472a",
      }),
    );
  for (const [i, ramp] of (state.offramps || []).entries()) {
    const [x, y] = ramp.cells[2];
    scene.append(
      text(x * unit + 18, y * unit + 18, `↗${i + 1}`, {
        "font-size": 13,
        fill: "#24554a",
      }),
    );
  }
  Object.entries(state.players).forEach(([owner, p], i) => {
    for (const shop of p.coffee_shops || []) {
      const [x, y] = shop.cells[0];
      scene.append(
        rect(
          x * unit + 3,
          y * unit + 3,
          unit - 6,
          unit - 6,
          colors[i % colors.length],
          { rx: 7 },
        ),
        text(x * unit + 18, y * unit + 18, "☕", { "font-size": 20 }),
      );
    }
  });
  for (const h of b.houses) {
    const box = bounds(h.cells);
    const x = box.x * unit + 6,
      y = box.y * unit + 6,
      w = box.w * unit - 12,
      height = box.h * unit - 12;
    if (
      !b.tiles?.some((t) =>
        h.cells.some(
          ([x, y]) => Math.floor(x / 5) === t.x && Math.floor(y / 5) === t.y,
        ),
      ) ||
      !h.printed
    ) {
      scene.append(
        rect(x + 2, y + 3, w, height, "#b9bcaa", { rx: 7, opacity: 0.45 }),
        rect(x, y, w, height, h.garden ? "#b6c798" : "#e4cba3", {
          rx: 6,
          stroke: "#c8b189",
          "stroke-width": 1,
        }),
      );
      scene.append(
        svg("path", {
          d: `M ${x + w / 2 - 17},${y + 24} l17,-12 l17,12`,
          fill: "none",
          stroke: "#9e7859",
          "stroke-width": 3,
          "stroke-linecap": "round",
        }),
        rect(x + w / 2 - 13, y + 24, 26, 20, "#faf2dc", { rx: 2 }),
        rect(x + w / 2 - 3, y + 31, 6, 13, "#b59770", { rx: 1 }),
        text(x + 11, y + 11, h.id, {
          "font-size": 10,
          fill: "#74593e",
          "font-weight": 700,
        }),
      );
      if (h.garden)
        scene.append(
          text(x + w - 12, y + 13, "♣", { "font-size": 19, fill: "#628254" }),
        );
    } else if (h.garden) {
      scene.append(
        rect(
          box.x * unit,
          box.y * unit,
          box.w * unit,
          box.h * unit,
          "#6d99441c",
          { stroke: "#618c3e", "stroke-width": 2 },
        ),
      );
    }
    h.demand.forEach((p, i) =>
      scene.append(
        svg("circle", {
          cx: x + 9 + i * 12,
          cy: y + height - 5,
          r: 8,
          fill: "#fffdf7",
          stroke: "#decba9",
        }),
        text(x + 9 + i * 12, y + height - 5, productIcons[p], {
          "font-size": 11,
        }),
      ),
    );
  }
  Object.entries(state.players).forEach(([player, p], index) =>
    p.restaurants.forEach((r) => {
      const box = bounds(r.cells),
        x = box.x * unit + 4,
        y = box.y * unit + 5,
        w = box.w * unit - 8,
        h = box.h * unit - 10,
        c = colors[index % colors.length];
      scene.append(
        rect(x + 2, y + 3, w, h, "#8b9584", { rx: 6, opacity: 0.35 }),
        rect(x, y, w, h, "#fffaf0", { rx: 5, stroke: c, "stroke-width": 2 }),
        rect(x, y, w, 15, c, { rx: 4 }),
      );
      for (let i = 0; i < 5; i++)
        scene.append(rect(x + (i * w) / 5, y + 13, w / 10, 8, c));
      scene.append(
        text(x + w / 2, y + 38, r.open ? "餐 厅" : "筹备中", {
          "font-size": 12,
          fill: c,
          "font-weight": 700,
        }),
        text(
          x + w / 2,
          y + 52,
          player === pid ? "你的连锁" : String(index + 1).padStart(2, "0"),
          { "font-size": 8, fill: c },
        ),
      );
      scene.append(
        svg("circle", {
          cx: r.entrance[0] * unit + 18,
          cy: r.entrance[1] * unit + 18,
          r: 5,
          fill: "#fffaf0",
          stroke: c,
          "stroke-width": 2,
        }),
      );
    }),
  );
  for (const c of state.campaigns) {
    if (c.kind === "giant_billboard") continue;
    if (c.kind === "guide") {
      scene.append(
        text(
          (Number(c.id) - 16) * 80,
          -12,
          `${campaignNames[c.kind]} #${c.id} ${productIcons[c.product]}`,
          {
            "font-size": 11,
            fill: "#365b49",
          },
        ),
      );
      continue;
    }
    if (c.kind === "airplane") {
      const horizontal = ["left", "right"].includes(c.side);
      const x = horizontal
        ? c.side === "left"
          ? (c.edge_line || 0) * unit - 17
          : (c.edge_line ?? b.width) * unit + 17
        : c.offset * unit + 18;
      const y = horizontal
        ? c.offset * unit + 18
        : c.side === "top"
          ? (c.edge_line || 0) * unit - 12
          : (c.edge_line ?? b.height) * unit + 12;
      scene.append(text(x, y, "✈", { "font-size": 19, fill: "#836a91" }));
      continue;
    }
    const box = bounds(c.cells);
    scene.append(
      rect(
        box.x * unit + 3,
        box.y * unit + 3,
        box.w * unit - 6,
        box.h * unit - 6,
        "#f2ddb8",
        { rx: 4, stroke: "#b98b50", "stroke-width": 2 },
      ),
      text(
        box.x * unit + (box.w * unit) / 2,
        box.y * unit + (box.h * unit) / 2,
        productIcons[c.product],
        { "font-size": 16 },
      ),
      text(box.x * unit + 7, box.y * unit + 7, c.id, {
        "font-size": 8,
        fill: "#795934",
      }),
    );
  }
  for (let x = 0; x <= b.width; x += 5)
    scene.append(
      svg("path", {
        d: `M${x * unit},0V${b.height * unit}`,
        stroke: "#778d73",
        "stroke-width": 1.7,
        opacity: 0.5,
      }),
    );
  for (let y = 0; y <= b.height; y += 5)
    scene.append(
      svg("path", {
        d: `M0,${y * unit}H${b.width * unit}`,
        stroke: "#778d73",
        "stroke-width": 1.7,
        opacity: 0.5,
      }),
    );
  if (state.phase === "setup_restaurants" && options?.can_act) {
    const positions = new Set(
      options.placements.map((p) => p.position.join(",")),
    );
    for (const pos of positions) {
      const [x, y] = pos.split(",").map(Number);
      scene.append(
        svg("circle", {
          cx: x * unit + 18,
          cy: y * unit + 18,
          r: 5,
          fill: "#2f725a",
          opacity: 0.75,
        }),
      );
    }
  }
  const position = pick?.section
    ? draft?.work[pick.section]?.[pick.index]?.position
    : state.phase === "setup_restaurants"
      ? draft?.position
      : null;
  if (position) {
    const size =
      state.phase === "setup_restaurants" || pick?.section === "restaurants"
        ? 2
        : 1;
    scene.append(
      rect(
        position[0] * unit + 2,
        position[1] * unit + 2,
        unit * size - 4,
        unit * size - 4,
        "#e9a87e44",
        { rx: 4, stroke: "#df744d", "stroke-width": 3 },
      ),
    );
  }
  if (state.phase === "setup_restaurants" && draft?.position) {
    const [x, y] = draft.position;
    scene.append(
      svg("circle", {
        cx: (x + (draft.entrance % 2)) * unit + 18,
        cy: (y + Math.floor(draft.entrance / 2)) * unit + 18,
        r: 7,
        fill: "#de744f",
        stroke: "white",
        "stroke-width": 2,
      }),
    );
  }
  if (pick?.mode === "route") {
    const route = draft.work.produce[pick.index]?.route || [];
    const coords = route.map(([x, y]) =>
      pick.tiles
        ? [x * 5 * unit + 2.5 * unit, y * 5 * unit + 2.5 * unit]
        : [x * unit + 18, y * unit + 18],
    );
    if (coords.length)
      scene.append(
        svg("polyline", {
          points: coords.map((p) => p.join(",")).join(" "),
          fill: "none",
          stroke: "#d96f49",
          "stroke-width": 4,
          "stroke-dasharray": "5 3",
        }),
      );
    coords.forEach(([x, y], i) =>
      scene.append(
        svg("circle", { cx: x, cy: y, r: 10, fill: "#da7754" }),
        text(x, y, i + 1, {
          "font-size": 10,
          fill: "white",
          "font-weight": 700,
        }),
      ),
    );
  }
  for (let x = 0; x < b.width; x++)
    scene.append(
      text(x * unit + 18, -10, x, { "font-size": 8, fill: "#88917e" }),
    );
  for (let y = 0; y < b.height; y++)
    scene.append(
      text(-12, y * unit + 18, y, { "font-size": 8, fill: "#88917e" }),
    );
  for (let y = 0; y < b.height; y++)
    for (let x = 0; x < b.width; x++)
      scene.append(
        rect(x * unit, y * unit, unit, unit, "transparent", {
          class: "map-hit",
          onclick: () => onCell([x, y]),
          onkeydown: (e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onCell([x, y]);
            }
          },
          tabindex: pick || state.phase === "setup_restaurants" ? 0 : -1,
          role: "button",
          "aria-label": `格子 ${x}, ${y}，${products[b.cells[y][x]] || b.cells[y][x]}`,
        }),
      );
  const detail = inspected
    ? describeCell(state, inspected)
    : "点击房屋查看需求 · 绿色圆点代表可选店址";
  return el(
    "section",
    { class: "map-panel" },
    el(
      "div",
      { class: "panel-heading" },
      el(
        "div",
        {},
        el("h2", {}, "城市地图"),
        el(
          "span",
          { class: "muted small" },
          `${b.width / 5} × ${b.height / 5} 板块 · ${b.houses.length} 户居民`,
        ),
      ),
      el(
        "div",
        { class: "zoom-controls" },
        button("−", () => onZoom(Math.max(70, zoom - 15)), "icon", {
          title: "缩小地图",
        }),
        el("span", {}, `${zoom}%`),
        button("+", () => onZoom(Math.min(180, zoom + 15)), "icon", {
          title: "放大地图",
        }),
      ),
    ),
    pick &&
      el(
        "div",
        { class: "pick-banner" },
        el(
          "span",
          {},
          pick.mode === "route"
            ? "在地图上依次点选采购路线"
            : "点击地图，为这项计划选择位置",
        ),
        button("完成选取", onPickEnd, "small"),
      ),
    el(
      "div",
      { class: "map-scroll" },
      el(
        "div",
        { style: { width: `${zoom}%`, minWidth: "360px", margin: "auto" } },
        canvas,
        state.modules?.includes("rural_marketeers") &&
          el(
            "div",
            { class: "rural-area" },
            el("strong", {}, "乡村区域 · 最后消费"),
            el(
              "p",
              {},
              (state.rural?.demand || [])
                .map((k) => productIcons[k])
                .join(" ") || "暂无需求",
            ),
            el("small", {}, `高速出口 ${(state.offramps || []).length} / 3`),
            state.campaigns
              .filter((c) => c.kind === "giant_billboard")
              .map((c) =>
                el(
                  "p",
                  {},
                  `广告 #${c.id} · ${c.rural_side} · ${products[c.product]} ×2 / 永久`,
                ),
              ),
          ),
      ),
    ),
    el(
      "div",
      { class: "map-footer" },
      el(
        "div",
        { class: "legend" },
        badge("● 可选店址", "green"),
        badge("▣ 餐厅", "coral"),
        badge("⌂ 居民", "sand"),
      ),
      el("span", { class: "small muted", "aria-live": "polite" }, detail),
    ),
  );
}
function describeCell(s, [x, y]) {
  const house = s.board.houses.find((h) =>
    h.cells.some((p) => p[0] === x && p[1] === y),
  );
  if (house)
    return `房屋 ${house.id}${house.garden ? " · 有花园" : ""}：${house.demand.length ? house.demand.map((p) => products[p]).join("、") : "暂无需求"}`;
  const campaign = s.campaigns.find((c) =>
    c.cells?.some((p) => p[0] === x && p[1] === y),
  );
  if (campaign)
    return `${campaignNames[campaign.kind]} #${campaign.id} · ${products[campaign.product]} · ${campaign.eternal ? "永久" : `剩余 ${campaign.remaining} 轮`}`;
  return `格子 (${x}, ${y}) · ${products[s.board.cells[y][x]] || { road: "道路", bridge: "立交桥", empty: "空地", house: "房屋" }[s.board.cells[y][x]]}`;
}
