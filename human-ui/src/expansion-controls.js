import { el, field, input, select, button } from "./dom.js";
import { products } from "./labels.js";
const sides = ["left", "right", "top", "bottom"];
const sideLabels = ["左侧", "右侧", "上侧", "下侧"];
const names = {
  road_short: "两格直路",
  road_long: "四格直路",
  road_corner: "三格弯路",
  park_t: "T 形公园",
  park_left: "左弯公园",
  park_right: "右弯公园",
  park_long: "四格公园",
};
const opts = (xs) => xs.map((v) => ({ value: v, label: v }));
function coords(object, key, changed, label = "位置", min = 0) {
  return el(
    "div",
    { class: "form-grid" },
    [0, 1].map((i) =>
      field(
        `${label} ${i ? "Y" : "X"}`,
        input(
          object[key]?.[i] ?? "",
          (v) => {
            object[key] ??= [0, 0];
            object[key][i] = Number(v);
            changed();
          },
          { type: "number", min },
        ),
      ),
    ),
  );
}
function toggle(title, obj, key, initial, changed) {
  return field(
    title,
    el("input", {
      type: "checkbox",
      checked: !!obj[key],
      onchange: (e) => {
        if (e.target.checked) obj[key] = structuredClone(initial);
        else delete obj[key];
        changed();
      },
    }),
  );
}
function shopFields(shop, p, changed) {
  return el(
    "div",
    {},
    coords(shop, "position", changed, "咖啡店"),
    p.coffee_shops?.length === 3 &&
      field(
        "移动哪家店",
        select(
          [
            { value: "", label: "请选择" },
            ...p.coffee_shops.map((v) => ({
              value: v.id,
              label: `咖啡店 ${v.cells[0]}`,
            })),
          ],
          shop.shop_id || "",
          (v) => {
            shop.shop_id = v;
            changed();
          },
        ),
      ),
  );
}
function campaignFields(a, s, kind, changed, product = false) {
  return el(
    "div",
    {},
    field(
      "广告组件",
      select(
        [
          { value: "", label: "请选择" },
          ...Object.entries(s.campaign_tiles)
            .filter(
              ([id, t]) =>
                t.kind === kind && !s.campaigns.some((c) => c.id === id),
            )
            .map(([id]) => ({ value: id, label: `#${id}` })),
        ],
        a.campaign_id || "",
        (v) => {
          a.campaign_id = v;
          changed();
        },
      ),
    ),
    coords(a, "position", changed),
    product &&
      field(
        "推广商品",
        select(
          opts(["burger", "pizza", "beer", "lemonade", "soda"]).map((o) => ({
            ...o,
            label: products[o.value],
          })),
          a.product,
          (v) => {
            a.product = v;
            changed();
          },
        ),
      ),
    field(
      "旋转组件",
      el("input", {
        type: "checkbox",
        checked: a.rotate,
        onchange: (e) => {
          a.rotate = e.target.checked;
          changed();
        },
      }),
    ),
  );
}
export function expansionWorkFields(ctx, tab, r, e) {
  const { state: s, pid, changed } = ctx,
    p = s.players[pid],
    out = el("div", { class: "expansion-fields" });
  const fresh = (id) =>
    !p.milestones.includes(id) && !s.closed_milestones.includes(id);
  if (tab === "train" && s.modules?.includes("coffee")) {
    const n = (r.path || []).filter((k) =>
      ["barista", "lead_barista"].includes(k),
    ).length;
    if (n) {
      out.append(
        el(
          "p",
          {},
          `本次晋升可建 ${n} 家咖啡店（道路距离 2 内），也可以不建。`,
        ),
      );
      (r.coffee_shops || []).forEach((shop, i) =>
        out.append(
          shopFields(shop, p, changed),
          button(
            "取消这家店",
            () => {
              r.coffee_shops.splice(i, 1);
              changed();
            },
            "text",
          ),
        ),
      );
      if ((r.coffee_shops || []).length < n)
        out.append(
          button("添加咖啡店选址", () => {
            (r.coffee_shops ??= []).push({ position: [0, 0] });
            changed();
          }),
        );
    }
  }
  if (tab === "lobby") {
    out.append(
      field(
        "建设组件",
        select(
          Object.entries(names)
            .filter(([id]) => s.lobby_supply?.[id] > 0)
            .map(([id, name]) => ({
              value: id,
              label: `${name} · 剩余 ${s.lobby_supply[id]}`,
            })),
          r.piece,
          (v) => {
            r.piece = v;
            changed();
          },
        ),
      ),
      coords(r, "position", changed),
      field(
        "旋转",
        select(
          [0, 1, 2, 3].map((v) => ({ value: v, label: `${v * 90}°` })),
          r.rotation || 0,
          (v) => {
            r.rotation = Number(v);
            changed();
          },
        ),
      ),
    );
    if (fresh("first_lobbyist_used") && s.board.available_tiles?.length) {
      out.append(
        toggle(
          "领取首次建设的新城区板块（仅第一项建设填写）",
          r,
          "city",
          {
            tile_id: s.board.available_tiles[0],
            tile: [s.board.width / 5, 0],
            rotation: 0,
          },
          changed,
        ),
      );
      if (r.city)
        out.append(
          field(
            "地图板块",
            select(
              s.board.available_tiles.map((id) => ({ value: id, label: id })),
              r.city.tile_id,
              (v) => {
                r.city.tile_id = v;
                changed();
              },
            ),
          ),
          coords(r.city, "tile", changed, "板块列 / 行", -1),
          field(
            "新板块旋转",
            select(
              [0, 1, 2, 3].map((v) => ({ value: v, label: `${v * 90}°` })),
              r.city.rotation,
              (v) => {
                r.city.rotation = Number(v);
                changed();
              },
            ),
          ),
          el(
            "p",
            { class: "hint" },
            "在左侧或上侧新增板块后，原坐标相应加 5；后续计划按新坐标填写。",
          ),
        );
    }
  }
  if (
    tab === "market" &&
    s.campaign_tiles[r.campaign_id]?.kind === "airplane" &&
    s.modules?.includes("lobbyists")
  ) {
    out.append(
      toggle("选择非矩形地图的飞机停靠板块", r, "edge_tile", [0, 0], changed),
    );
    if (r.edge_tile) out.append(coords(r, "edge_tile", changed, "停靠板块"));
  }
  if (tab === "market" && e?.kind === "rural_marketeer") {
    r.rural_side ??= "left";
    out.append(
      field(
        "乡村广告边位",
        select(
          sides.map((v, i) => ({ value: v, label: sideLabels[i] })),
          r.rural_side || "left",
          (v) => {
            r.rural_side = v;
            changed();
          },
        ),
      ),
    );
    if (fresh("first_rural_marketeer_used") && (s.offramps?.length || 0) < 3) {
      out.append(
        toggle(
          "首次使用：放置高速出口",
          r,
          "offramp",
          { tile: [0, 0], side: "left" },
          changed,
        ),
      );
      if (r.offramp)
        out.append(
          coords(r.offramp, "tile", changed, "相邻城市板块"),
          field(
            "出口方向",
            select(
              sides.map((v, i) => ({ value: v, label: sideLabels[i] })),
              r.offramp.side,
              (v) => {
                r.offramp.side = v;
                changed();
              },
            ),
          ),
        );
    }
  }
  if (s.modules?.includes("new_milestones")) {
    if (
      tab === "market" &&
      e?.kind === "brand_manager" &&
      s.campaign_tiles[r.campaign_id]?.kind === "airplane" &&
      fresh("new_first_brand_manager_used")
    ) {
      out.append(
        field(
          "首次品牌经理：第二种商品（可不选）",
          select(
            [
              { value: "", label: "不推广第二种商品" },
              ...Object.entries(products)
                .filter(([k]) =>
                  ["burger", "pizza", "beer", "lemonade", "soda"].includes(k),
                )
                .map(([value, label]) => ({ value, label })),
            ],
            r.second_product || "",
            (v) => {
              if (v) r.second_product = v;
              else delete r.second_product;
              changed();
            },
          ),
        ),
      );
    }
    if (
      tab === "market" &&
      e?.kind === "campaign_manager" &&
      fresh("new_first_campaign_manager_used")
    ) {
      out.append(
        toggle(
          "首次活动经理：额外放置同类广告",
          r,
          "second_campaign",
          { campaign_id: "", position: [0, 0], rotate: false },
          changed,
        ),
      );
      if (r.second_campaign)
        out.append(
          campaignFields(
            r.second_campaign,
            s,
            s.campaign_tiles[r.campaign_id]?.kind,
            changed,
          ),
        );
    }
    if (
      tab === "restaurants" &&
      !r.restaurant_id &&
      fresh("new_first_restaurant")
    ) {
      out.append(
        toggle(
          "首次新开餐厅：放置永久邮箱",
          r,
          "mailbox",
          {
            campaign_id: "",
            position: [0, 0],
            product: "burger",
            rotate: false,
          },
          changed,
        ),
      );
      if (r.mailbox)
        out.append(campaignFields(r.mailbox, s, "mailbox", changed, true));
    }
  }
  return out;
}
export function expansionPhaseFields(ctx) {
  const { state: s, pid, draft: d, options: o, changed } = ctx,
    p = s.players[pid],
    out = el("div", {});
  if (s.phase === "bonus") {
    out.append(
      el(
        "p",
        {},
        o.bonus?.kind === "coffee"
          ? "首次售出咖啡：选择奖励咖啡店位置。"
          : "首次售出披萨：在顾客所在板块放置两轮披萨电台。",
      ),
    );
    const choices = o.choices || [];
    const index = choices.findIndex(
      (c) => JSON.stringify(c) === JSON.stringify(d.bonusChoice),
    );
    out.append(
      field(
        "合法选址",
        select(
          [
            {
              value: "",
              label: choices.length ? "请选择位置" : "没有合法位置",
            },
            ...choices.map((c, i) => ({
              value: i,
              label: `(${c.position})${c.campaign_id ? ` · 电台 #${c.campaign_id}` : ""}${c.shop_id ? ` · 移动 ${c.shop_id.split(":").at(-1)}` : ""}`,
            })),
          ],
          index < 0 ? "" : index,
          (v) => {
            d.bonusChoice = v === "" ? null : choices[Number(v)];
            changed();
          },
        ),
      ),
    );
  }
  if (s.phase === "payday" && p.milestones.includes("new_first_beer_sold")) {
    out.append(
      el(
        "p",
        {},
        "可用食品 / 饮料付工资，每份支付一名员工。咖啡不能支付工资。",
      ),
    );
    for (const [k, n] of Object.entries(p.inventory).filter(
      ([k, n]) => k !== "coffee" && n > 0,
    ))
      out.append(
        field(
          `${products[k]}（库存 ${n}）`,
          input(
            d.food?.[k] || 0,
            (v) => {
              (d.food ??= {})[k] = Number(v);
              changed();
            },
            { type: "number", min: 0, max: n },
          ),
        ),
      );
  }
  return out;
}
