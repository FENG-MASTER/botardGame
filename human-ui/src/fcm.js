import {
  expansionWorkFields,
  expansionPhaseFields,
} from "./expansion-controls.js";
import {
  el,
  button,
  field,
  input,
  select,
  badge,
  money,
  empty,
} from "./dom.js";
import {
  employees,
  products,
  productIcons,
  campaignNames,
  employeeLabel,
  ability,
  phases,
} from "./labels.js";
import {
  buildAction,
  companySlots,
  previewBeach,
  projectedActive,
} from "./model.js";
const opts = (xs, label = (x) => x, value = (x) => x) =>
  xs.map((x) => ({ value: value(x), label: label(x) }));
const name = (k) => employees[k] || k;
const sectionNames = {
  hire: "招聘",
  train: "培训",
  market: "营销",
  produce: "生产",
  develop: "开发",
  lobby: "说客建设",
  restaurants: "开店",
};
const tips = {
  setup_restaurants:
    "好的位置，是生意的第一步。点选地图上的绿色标记，再选择朝向道路的入口。",
  reserve: "为银行选择一张秘密储备卡。金额越高，对局通常越长。",
  restructure:
    "安排本轮工作的员工。没安排的员工留在海滩上；所有玩家提交后同时公开。",
  order: "选择你这一轮的行动位置。较早行动可能抢到稀缺员工和广告。",
  work: "安排一天的生意。招聘、培训、营销、生产、开发和开店将按顺序一次执行。",
  payday: "员工在海滩上也可能需要薪资。可先裁员，再支付剩余工资。",
  cleanup: "一天结束了。选择放进冰柜的商品，其他库存会被丢弃。",
};
export function actionPanel(ctx) {
  const {
    state: s,
    pid,
    options: o,
    draft: d,
    catalog: cards,
    changed,
    submit,
    validate,
    busy,
    pending,
  } = ctx;
  const p = s.players[pid];
  if (s.finished)
    return el(
      "aside",
      { class: "action-panel" },
      el("div", { class: "finish-symbol" }, "✦"),
      el("p", { class: "eyebrow" }, "THE LAST ORDER"),
      el("h2", {}, s.winner === pid ? "恭喜，你赢了！" : "本局已结束"),
      el(
        "p",
        { class: "muted" },
        "最后一桌顾客已经离开。看看谁经营出了最成功的连锁餐厅。",
      ),
      el("div", { class: "final-cash" }, money(p.cash)),
      button("回到大厅", () => (location.hash = "#lobby"), "primary"),
    );
  const controls = el("div", { class: "phase-controls" });
  if (s.phase === "setup_restaurants") {
    controls.append(
      el(
        "div",
        { class: "selection-card" },
        el("span", { class: "muted small" }, "餐厅左上角"),
        el(
          "strong",
          {},
          d.position ? `(${d.position.join(", ")})` : "尚未选择",
        ),
        el("span", { class: "small muted" }, "在左侧地图点选位置"),
      ),
    );
    controls.append(
      field(
        "餐厅入口",
        select(
          ["左上角", "右上角", "左下角", "右下角"].map((label, value) => ({
            label,
            value,
          })),
          d.entrance,
          (v) => {
            d.entrance = Number(v);
            changed();
          },
        ),
      ),
    );
    if (o.actions?.some((a) => a.type === "pass"))
      controls.append(
        button(
          "先看看其他人的选址，本次跳过",
          () => submit({ type: "pass" }),
          "text full",
        ),
      );
  }
  if (s.phase === "reserve")
    controls.append(
      el(
        "div",
        { class: "reserve-cards" },
        (o.reserve_choices || [100, 200, 300]).map((amount) =>
          button(
            el(
              "span",
              {},
              el("small", {}, "RESERVE"),
              el("strong", {}, `$${amount}`),
              el(
                "small",
                {},
                s.modules?.includes("reserve_prices")
                  ? "首次银行耗尽后投票决定基础价格"
                  : `CEO ${amount / 100 + 1} 个槽位`,
              ),
            ),
            () => {
              d.reserve = amount;
              changed();
            },
            d.reserve === amount ? "reserve selected" : "reserve",
            { "aria-pressed": d.reserve === amount },
          ),
        ),
      ),
      el("p", { class: "hint" }, "🔒 仅你可见。银行首次破产时统一揭晓。"),
    );
  if (s.phase === "restructure") {
    const slots = companySlots(s, pid, d.structure, cards);
    controls.append(
      el(
        "div",
        { class: `slot-meter ${slots.valid ? "" : "invalid"}` },
        el("strong", {}, `${slots.used} / ${slots.capacity}`),
        el("span", {}, "工作员工 / 总槽位"),
        badge(`${slots.free} 空槽`, slots.valid ? "green" : "coral"),
      ),
    );
    controls.append(
      el(
        "div",
        { class: "ceo-card" },
        el("span", { class: "employee-icon" }, "♜"),
        el(
          "div",
          {},
          el("strong", {}, "你 · CEO"),
          el(
            "small",
            {},
            `始终工作 · 可管理 ${p.milestones.includes("new_first_burger_sold") ? 4 : s.ceo_slots} 人`,
          ),
        ),
      ),
    );
    const managers = p.employees.filter(
      (e) => cards[e.kind].slots && e.kind !== "ceo" && d.structure[e.id],
    );
    for (const e of p.employees.filter((e) => e.kind !== "ceo")) {
      controls.append(
        el(
          "div",
          { class: `staff-row ${d.structure[e.id] ? "working" : ""}` },
          el(
            "div",
            {},
            el("strong", {}, name(e.kind)),
            el(
              "small",
              {},
              `${e.id} · ${cards[e.kind].salary ? "工资 $5" : "无需工资"}${e.busy ? " · 广告执行中" : ""}`,
            ),
          ),
          select(
            [
              { value: "", label: e.busy ? "忙碌中" : "在海滩上" },
              { value: `${pid}:ceo`, label: "向 CEO 汇报" },
              ...(!(cards[e.kind].manager || cards[e.kind].slots)
                ? managers.map((m) => ({
                    value: m.id,
                    label: `向 ${name(m.kind)} ${m.id} 汇报`,
                  }))
                : []),
            ],
            d.structure[e.id] || "",
            (value) => {
              if (value) d.structure[e.id] = value;
              else {
                delete d.structure[e.id];
                for (const [id, parent] of Object.entries(d.structure))
                  if (parent === e.id) delete d.structure[id];
              }
              changed();
            },
            {
              disabled: !!e.busy,
              "aria-label": `${name(e.kind)} ${e.id} 的工作安排`,
            },
          ),
        ),
      );
    }
    if (p.employees.length === 1)
      controls.append(
        el(
          "p",
          { class: "hint" },
          "公司刚刚起步，本轮只有 CEO。工作阶段可以开始招聘。",
        ),
      );
    if (!slots.valid)
      controls.append(
        el(
          "p",
          { class: "inline-warning" },
          "结构超出管理能力。直接提交会使所有员工返回海滩，仅 CEO 工作。",
        ),
      );
  }
  if (s.phase === "order")
    controls.append(
      el(
        "div",
        { class: "order-choices" },
        (o.available_positions || []).map((v) =>
          button(
            el(
              "span",
              {},
              el("strong", {}, String(v + 1).padStart(2, "0")),
              el("small", {}, `第 ${v + 1} 位行动`),
            ),
            () => {
              d.order = v;
              changed();
            },
            `order-card ${d.order === v ? "selected" : ""}`,
            { "aria-pressed": d.order === v },
          ),
        ),
      ),
    );
  if (s.phase === "work") controls.append(workPanel(ctx));
  if (s.phase === "payday") {
    const remaining = p.employees.filter((e) => !d.fire.includes(e.id));
    const count = remaining.filter(
      (e) =>
        cards[e.kind].salary &&
        !e.salary_exempt &&
        !(cards[e.kind].marketing && p.milestones.includes("first_billboard")),
    ).length;
    const cost = Math.max(
      0,
      Math.max(
        0,
        count - Object.values(d.food || {}).reduce((a, b) => a + b, 0),
      ) *
        (p.milestones.includes("new_first_waitress_used") ? 3 : 5) -
        p.hire_discount -
        (p.milestones.includes("first_train") ? 15 : 0),
    );
    controls.append(
      el(
        "div",
        { class: "pay-summary" },
        el(
          "div",
          {},
          el("span", {}, "预计工资"),
          el("strong", {}, money(cost)),
        ),
        el(
          "div",
          {},
          el("span", {}, "手头现金"),
          el("strong", {}, money(p.cash)),
        ),
      ),
    );
    for (const e of p.employees.filter((e) => e.kind !== "ceo"))
      controls.append(
        el(
          "label",
          { class: "staff-row" },
          el(
            "div",
            {},
            el("strong", {}, name(e.kind)),
            el(
              "small",
              {},
              `${e.id}${e.busy ? " · 忙碌，裁员受限" : ""}${e.kind === "cfo" && p.milestones.includes("first_hundred") ? " · 必须解雇" : ""}`,
            ),
          ),
          el(
            "span",
            { class: "fire-check" },
            "解雇 ",
            el("input", {
              type: "checkbox",
              checked: d.fire.includes(e.id),
              onchange: (ev) => {
                d.fire = ev.target.checked
                  ? [...d.fire, e.id]
                  : d.fire.filter((v) => v !== e.id);
                changed();
              },
            }),
          ),
        ),
      );
    if (cost > p.cash)
      controls.append(
        el(
          "p",
          { class: "inline-warning" },
          p.milestones.includes("new_first_trainer_used")
            ? "须尽力支付现金和可用食品，剩余工资可欠付。"
            : p.milestones.includes("new_first_beer_sold")
              ? "可选择食品支付工资，或解雇员工。"
              : "现金不足，请选择更多员工解雇。",
        ),
      );
  }
  if (s.phase === "cleanup") {
    const count = Object.values(d.keep).reduce((a, b) => a + b, 0);
    controls.append(
      el(
        "div",
        { class: "slot-meter" },
        el("strong", {}, `${count} / ${o.freezer_capacity || 0}`),
        el("span", {}, "冰柜已用容量"),
      ),
    );
    for (const product of Object.keys(p.inventory).filter(k => k !== "coffee"))
      controls.append(
        el(
          "div",
          { class: "stock-row" },
          el("span", {}, `${productIcons[product]} ${products[product]}`),
          el("span", { class: "muted small" }, `现有 ${p.inventory[product]}`),
          input(
            d.keep[product] || 0,
            (v) => {
              d.keep[product] = Number(v) || 0;
              changed();
            },
            {
              type: "number",
              min: 0,
              max: p.inventory[product],
              disabled: !o.freezer_capacity || product === "coffee",
              "aria-label": `保留${products[product]}`,
            },
          ),
        ),
      );
    if (!o.freezer_capacity)
      controls.append(
        el(
          "p",
          { class: "hint" },
          "目前没有可用冰柜，库存将全部丢弃。首次获得冰柜需到以后的清理阶段才能使用。",
        ),
      );
  }
  controls.append(expansionPhaseFields(ctx));
  const names = {
    setup_restaurants: "在这里开店",
    reserve: "秘密提交储备",
    restructure: "确认公司结构",
    order: "确认行动顺序",
    work: "执行今日计划",
    payday: "裁员并支付工资",
    cleanup: "结束这一天",
    bonus: "确认奖励选址",
  };
  return el(
    "aside",
    { class: "action-panel" },
    el(
      "div",
      { class: "action-heading" },
      el("span", { class: `status-dot ${o.can_act ? "active" : ""}` }),
      el("span", { class: "eyebrow" }, o.can_act ? "轮到你了" : "等待其他玩家"),
      el("span", { class: "phase-number" }, "YOUR MOVE"),
    ),
    el("h2", {}, phases[s.phase] || s.phase),
    el(
      "p",
      { class: "action-description" },
      tips[s.phase] || "按当前游戏规则选择行动。",
    ),
    !o.can_act
      ? empty(
          s.submitted?.includes(pid) ? "已提交，等待其他玩家" : "还没轮到你",
          "可以查看地图、对手公司与规则。对局会自动更新。",
        )
      : el(
          "fieldset",
          { class: "action-fieldset", disabled: busy || !!pending },
          controls,
          el(
            "div",
            { class: "submit-bar" },
            button("检查计划", () => validate(), "secondary", {
              disabled: busy,
            }),
            button(
              busy ? "正在提交…" : names[s.phase] || "提交行动",
              () => {
                try {
                  submit(buildAction(s.phase, d));
                } catch (e) {
                  ctx.error(e);
                }
              },
              "primary",
              { disabled: busy },
            ),
          ),
        ),
    pending &&
      el(
        "div",
        { class: "retry-box" },
        el("strong", {}, "上次提交的结果尚未确认"),
        el("p", {}, "请重试同一笔提交，服务器不会重复执行。"),
        button("确认 / 重试上次提交", ctx.retry, "primary", { disabled: busy }),
      ),
    el(
      "div",
      { class: "rules-link" },
      button("↗ 查看本局玩法", ctx.openRules, "text"),
    ),
  );
}
function workPanel(ctx) {
  const { state: s, pid, draft: d, catalog: cards, changed } = ctx;
  const p = s.players[pid];
  const active = p.employees.filter((e) => p.active.includes(e.id) && !e.busy);
  const trained = projectedActive(s, pid, d);
  const relevant = {
    hire: active.filter((e) => cards[e.kind].hire),
    train: active.filter((e) => cards[e.kind].train),
    market: trained.filter((e) => cards[e.kind].marketing),
    produce: trained.filter((e) => cards[e.kind].quantity),
    develop: trained.filter((e) => e.kind === "new_business_developer"),
    lobby: trained.filter((e) => e.kind === "lobbyist"),
    restaurants: trained.filter((e) =>
      ["local_manager", "regional_manager"].includes(e.kind),
    ),
  };
  // Keep drafted rows visible so a stale plan can still be corrected.
  const visibleTabs = Object.keys(sectionNames).filter(
    (key) => relevant[key].length || (d.work[key] || []).length,
  );
  const tab = visibleTabs.includes(ctx.workTab)
    ? ctx.workTab
    : visibleTabs[0] || "hire";
  const rows = d.work[tab];
  const add = () => {
    const e = relevant[tab][0];
    if (!e) return;
    const row = { employee: e.id };
    if (tab === "hire") {
      delete row.employee;
      row.recruiter = e.id;
      row.kind = "waitress";
    }
    if (tab === "train") {
      delete row.employee;
      row.trainer = e.id;
      row.target = "";
      row.path = [];
    }
    if (tab === "market") {
      const tiles = Object.entries(s.campaign_tiles).filter(
        ([id, tile]) =>
          !s.campaigns.some((c) => c.id === id) &&
          (e.kind === "gourmet_food_critic"
            ? tile.kind === "guide"
            : e.kind === "rural_marketeer"
              ? tile.kind === "giant_billboard"
              : ["billboard", "mailbox", "airplane", "radio"].indexOf(
                  tile.kind,
                ) >= 0 &&
                ["billboard", "mailbox", "airplane", "radio"].indexOf(
                  tile.kind,
                ) < cards[e.kind].marketing),
      );
      const preferred =
        tiles.find(([, v]) => v.kind === "billboard") || tiles[0];
      row.campaign_id = preferred?.[0] || "";
      if (e.kind === "rural_marketeer") row.rural_side = "left";
      row.product = "burger";
      row.duration = 1;
      row.position = null;
      row.rotate = false;
      if (preferred?.[1].kind === "airplane") {
        row.side = "left";
        row.offset = 0;
      }
    }
    if (tab === "lobby") {
      row.piece = Object.keys(s.lobby_supply || {})[0];
      row.position = [0, 0];
      row.rotation = 0;
    }
    if (tab === "produce") {
      if (["cart_operator", "truck_driver", "zeppelin_pilot"].includes(e.kind))
        row.route = [];
      else
        row.product =
          cards[e.kind].product ||
          (e.kind === "errand_boy" ? "beer" : "burger");
    }
    if (tab === "develop") {
      row.mode = "house";
      row.position = null;
      row.rotate = false;
      row.new_house_id =
        (s.new_house_ids || [1, 2, 3, 4, 5, 6, 7, 8]).find(
          (id) => !s.board.houses.some((h) => h.id === id),
        ) || 1;
    }
    if (tab === "restaurants") {
      row.position = null;
      row.entrance = 0;
      row.restaurant_id = "";
    }
    rows.push(row);
    changed();
  };
  const panel = el(
    "div",
    {},
    el(
      "div",
      { class: "work-tabs" },
      Object.entries(sectionNames)
        .filter(([key]) => visibleTabs.includes(key))
        .map(([key, label]) =>
          button(
            el(
              "span",
              {},
              label,
              (d.work[key] || []).length
                ? el("sup", {}, (d.work[key] || []).length)
                : null,
            ),
            () => ctx.setWorkTab(key),
            key === tab ? "work-tab selected" : "work-tab",
            { "aria-pressed": key === tab },
          ),
        ),
    ),
    visibleTabs.length < Object.keys(sectionNames).length &&
      el(
        "p",
        { class: "muted small" },
        "没有可用员工能力的工作项已自动隐藏，无需逐项跳过。",
      ),
    el(
      "div",
      { class: "work-section-heading" },
      el(
        "div",
        {},
        el("strong", {}, sectionNames[tab]),
        el("small", {}, `${relevant[tab].length} 名员工提供能力`),
      ),
      button("+ 添加", add, "small", { disabled: !relevant[tab].length }),
    ),
    !rows.length &&
      el(
        "div",
        { class: "plan-empty" },
        el("span", {}, "＋"),
        el(
          "p",
          {},
          relevant[tab].length
            ? "这一步还没有安排"
            : "当前没有能执行此项工作的员工",
        ),
        el(
          "small",
          {},
          relevant[tab].length
            ? "可添加计划，也可以跳过此项工作。"
            : "可在未来回合招聘、培训并安排员工工作。",
        ),
      ),
  );
  rows.forEach((r, index) => {
    const row = el(
      "div",
      { class: "plan-card" },
      el(
        "div",
        { class: "plan-card-title" },
        el(
          "span",
          {},
          `${sectionNames[tab]} ${String(index + 1).padStart(2, "0")}`,
        ),
        button(
          "×",
          () => {
            rows.splice(index, 1);
            ctx.cancelPick();
            changed();
          },
          "icon",
          { title: "移除这项计划" },
        ),
      ),
    );
    const update = (key, value) => {
      r[key] = value;
      changed();
    };
    const empKey =
      tab === "hire" ? "recruiter" : tab === "train" ? "trainer" : "employee";
    const candidates = ["hire", "train"].includes(tab) ? active : trained;
    const e = candidates.find((e) => e.id === r[empKey]);
    const c = cards[e?.kind] || {};
    row.append(
      field(
        tab === "hire" ? "招聘者" : tab === "train" ? "培训者" : "执行员工",
        select(
          opts(relevant[tab], employeeLabel, (e) => e.id),
          r[empKey],
          (v) => {
            r[empKey] = v;
            const employee = candidates.find((e) => e.id === v);
            if (tab === "restaurants" && employee.kind === "local_manager")
              r.restaurant_id = "";
            if (tab === "produce") {
              delete r.route;
              delete r.product;
              if (
                ["cart_operator", "truck_driver", "zeppelin_pilot"].includes(
                  employee.kind,
                )
              )
                r.route = [];
              else
                r.product =
                  cards[employee.kind].product ||
                  (employee.kind === "errand_boy" ? "beer" : "burger");
            }
            changed();
          },
        ),
      ),
      el("p", { class: "ability-caption" }, ability(c)),
    );
    if (tab === "hire")
      row.append(
        field(
          "招聘职位",
          select(
            Object.entries(cards)
              .filter(([, c]) => c.entry)
              .map(([kind]) => ({
                value: kind,
                label: `${name(kind)} · 余 ${s.stock[kind]} 张`,
              })),
            r.kind,
            (v) => update("kind", v),
          ),
        ),
        el(
          "small",
          { class: "muted" },
          `招聘编号 ${index}，可在培训计划中引用。`,
        ),
      );
    if (tab === "train") {
      const targets = previewBeach(s, pid, d, cards, index);
      const target = targets.find((e) => e.ref === r.target);
      row.append(
        field(
          "培训目标",
          select(
            [
              {
                value: "",
                label: p.milestones.includes("new_first_lemonade_sold")
                  ? "选择可培训员工（工作员工限同色晋升）"
                  : "选择海滩员工 / 本轮新员工",
              },
              ...targets.map((e) => ({
                value: e.ref,
                label: `${name(e.kind)} · ${e.newHire ? `新招 #${Number(e.ref.slice(5)) + 1}` : e.bonus ? `里程碑奖励 ${e.id}` : e.id}`,
              })),
            ],
            r.target,
            (v) => {
              r.target = v;
              r.path = [];
              changed();
            },
          ),
        ),
      );
      let kind = target?.kind;
      for (let level = 0; kind && level < Math.min(c.train || 1, 3); level++) {
        const choices = (cards[kind]?.upgrades || []).filter(
          (k) =>
            Object.hasOwn(s.stock, k) &&
            (!p.active.includes(target?.id) ||
              cards[k]?.color === cards[target?.kind]?.color),
        );
        if (!choices.length) break;
        const index = level;
        row.append(
          field(
            `第 ${level + 1} 级晋升`,
            select(
              [
                { value: "", label: level ? "到此为止" : "选择晋升职位" },
                ...choices.map((k) => ({
                  value: k,
                  label: `${name(k)} · 余 ${s.stock[k]} 张`,
                })),
              ],
              r.path[level] || "",
              (v) => {
                r.path = r.path.slice(0, index);
                if (v) r.path.push(v);
                changed();
              },
            ),
          ),
        );
        kind = r.path[level];
      }
    }
    if (tab === "market") {
      const tiles = Object.entries(s.campaign_tiles).filter(
        ([id, tile]) =>
          !s.campaigns.some((v) => v.id === id) &&
          (e?.kind === "gourmet_food_critic"
            ? tile.kind === "guide"
            : e?.kind === "rural_marketeer"
              ? tile.kind === "giant_billboard"
              : ["billboard", "mailbox", "airplane", "radio"].indexOf(
                  tile.kind,
                ) >= 0 &&
                ["billboard", "mailbox", "airplane", "radio"].indexOf(
                  tile.kind,
                ) < c.marketing),
      );
      row.append(
        field(
          "营销板块",
          select(
            tiles.map(([id, v]) => ({
              value: id,
              label: `#${id} ${campaignNames[v.kind]} · ${v.width}×${v.height}`,
            })),
            r.campaign_id,
            (v) => {
              r.campaign_id = v;
              const plane = s.campaign_tiles[v]?.kind === "airplane";
              if (plane) {
                r.side = "left";
                r.offset = 0;
              } else {
                delete r.side;
                delete r.offset;
                r.position = null;
              }
              changed();
            },
          ),
        ),
        field(
          "推广产品",
          productSelect(r.product, (v) => update("product", v), [
            "burger",
            "pizza",
            "beer",
            "lemonade",
            "soda",
          ]),
        ),
        field(
          "持续轮数",
          input(r.duration, (v) => update("duration", Number(v)), {
            type: "number",
            min: 1,
            max: (c.marketing || 1) + 1,
          }),
        ),
      );
      if (s.campaign_tiles[r.campaign_id]?.kind === "airplane") {
        row.append(
          field(
            "飞越方向",
            select(
              [
                { value: "left", label: "从左侧飞入" },
                { value: "right", label: "从右侧飞入" },
                { value: "top", label: "从上方飞入" },
                { value: "bottom", label: "从下方飞入" },
              ],
              r.side || "left",
              (v) => update("side", v),
            ),
          ),
          field(
            "起始行 / 列（零起点）",
            input(r.offset || 0, (v) => update("offset", Number(v)), {
              type: "number",
              min: 0,
              max: Math.max(s.board.width, s.board.height) - 1,
            }),
          ),
        );
      } else if (
        !["guide", "giant_billboard"].includes(
          s.campaign_tiles[r.campaign_id]?.kind,
        )
      )
        row.append(
          positionFields(ctx, tab, index, r),
          check("旋转营销板块", r.rotate, (v) => update("rotate", v)),
        );
    }
    if (tab === "produce") {
      if (r.route) {
        row.append(
          el(
            "div",
            { class: "route-preview" },
            el(
              "strong",
              {},
              `采购路线 · ${r.route.length} ${e?.kind === "zeppelin_pilot" ? "板块" : "格"}`,
            ),
            el(
              "p",
              {},
              r.route.length
                ? r.route.map((p) => `(${p.join(",")})`).join(" → ")
                : "尚未规划路线",
            ),
            el(
              "div",
              { class: "button-row" },
              button(
                "在地图上规划",
                () =>
                  ctx.pick({
                    mode: "route",
                    section: "produce",
                    index,
                    tiles: e?.kind === "zeppelin_pilot",
                  }),
                "small",
              ),
              button(
                "撤销一步",
                () => {
                  r.route.pop();
                  changed();
                },
                "small",
              ),
              button(
                "清空",
                () => {
                  r.route = [];
                  changed();
                },
                "text small",
              ),
            ),
          ),
          el(
            "p",
            { class: "hint" },
            "从自家餐厅出发，依次点击路线。范围按跨板块次数计算。",
          ),
        );
      } else {
        const kinds =
          e?.kind === "errand_boy"
            ? ["beer", "lemonade", "soda"]
            : c.product
              ? [c.product]
              : ["burger", "pizza"];
        row.append(
          field(
            "生产商品",
            productSelect(r.product, (v) => update("product", v), kinds),
          ),
        );
      }
    }
    if (tab === "develop") {
      row.append(
        field(
          "开发项目",
          select(
            [
              { value: "house", label: "新建带花园的房屋" },
              { value: "garden", label: "给现有房屋添加花园" },
            ],
            r.mode,
            (v) => {
              r.mode = v;
              if (v === "garden")
                r.house_id = s.board.houses.find(
                  (h) => h.printed && !h.garden && !h.apartment,
                )?.id;
              changed();
            },
          ),
        ),
      );
      if (r.mode === "house")
        row.append(
          field(
            "房屋编号",
            select(
              (s.new_house_ids || [1, 2, 3, 4, 5, 6, 7, 8])
                .filter((id) => !s.board.houses.some((h) => h.id === id))
                .map((id) => ({ value: id, label: `房屋 ${id}` })),
              r.new_house_id,
              (v) => update("new_house_id", Number(v)),
            ),
          ),
        );
      else
        row.append(
          field(
            "目标房屋",
            select(
              s.board.houses
                .filter((h) => h.printed && !h.garden && !h.apartment)
                .map((h) => ({ value: h.id, label: `房屋 ${h.id}` })),
              r.house_id,
              (v) => update("house_id", Number(v)),
            ),
          ),
        );
      row.append(
        positionFields(ctx, tab, index, r),
        check("旋转占地", r.rotate, (v) => update("rotate", v)),
      );
    }
    if (tab === "restaurants") {
      if (e?.kind === "regional_manager")
        row.append(
          field(
            "新增或移动",
            select(
              [
                { value: "", label: "新建餐厅" },
                ...p.restaurants.map((v) => ({
                  value: v.id,
                  label: `移动餐厅 ${v.id.split(":").at(-1)}`,
                })),
              ],
              r.restaurant_id || "",
              (v) => update("restaurant_id", v),
            ),
          ),
        );
      row.append(
        positionFields(ctx, tab, index, r),
        field(
          "入口位置",
          select(
            ["左上角", "右上角", "左下角", "右下角"].map((label, value) => ({
              label,
              value,
            })),
            r.entrance,
            (v) => update("entrance", Number(v)),
          ),
        ),
      );
    }
    row.append(expansionWorkFields(ctx, tab, r, e));
    panel.append(row);
  });
  const total = Object.values(d.work).reduce((n, rows) => n + rows.length, 0);
  panel.append(
    el(
      "div",
      { class: "plan-total" },
      el("span", {}, "今日安排"),
      el("strong", {}, `${total} 项工作`),
    ),
  );
  return panel;
}
function productSelect(value, onChange, keys = Object.keys(products)) {
  return select(
    keys.map((k) => ({ value: k, label: `${productIcons[k]} ${products[k]}` })),
    value,
    onChange,
  );
}
function check(label, value, onChange) {
  return el(
    "label",
    { class: "check-field" },
    el("input", {
      type: "checkbox",
      checked: !!value,
      onchange: (e) => onChange(e.target.checked),
    }),
    label,
  );
}
function positionFields(ctx, section, index, r) {
  return el(
    "div",
    { class: "position-fields" },
    field(
      "X",
      input(
        r.position?.[0] ?? "",
        (v) => {
          r.position = [Number(v), r.position?.[1] ?? 0];
          ctx.changed();
        },
        { type: "number", min: 0, max: ctx.state.board.width - 1 },
      ),
    ),
    field(
      "Y",
      input(
        r.position?.[1] ?? "",
        (v) => {
          r.position = [r.position?.[0] ?? 0, Number(v)];
          ctx.changed();
        },
        { type: "number", min: 0, max: ctx.state.board.height - 1 },
      ),
    ),
    button(
      "地图选址",
      () => ctx.pick({ mode: "position", section, index }),
      "small",
    ),
  );
}
