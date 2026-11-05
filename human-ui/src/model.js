export function draftStamp(state) {
  return (
    `${state.round}:${state.phase}` +
    (state.phase === "bonus"
      ? `:${state.bonus?.kind}:${state.bonus?.player}:${state.bonus?.house?.id || ""}`
      : "")
  );
}
export function freshDraft(state) {
  return {
    reserve: state.modules?.includes("reserve_prices") ? 10 : 100,
    position: null,
    entrance: 0,
    order: null,
    structure: {},
    fire: [],
    keep: {},
    food: {},
    bonusChoice: null,
    work: {
      hire: [],
      train: [],
      market: [],
      produce: [],
      develop: [],
      lobby: [],
      restaurants: [],
    },
    stamp: draftStamp(state),
  };
}
export function projectedActive(state, pid, draft) {
  const p = state.players[pid];
  const people = p.employees
    .filter((e) => p.active.includes(e.id) && !e.busy)
    .map((e) => ({ ...e }));
  if (p.milestones.includes("new_first_lemonade_sold")) {
    for (const train of draft.work.train) {
      const target = people.find((e) => e.id === train.target);
      if (target && train.path.length) target.kind = train.path.at(-1);
    }
  }
  return people;
}
export function previewBeach(state, pid, draft, catalog, before = Infinity) {
  const p = state.players[pid];
  let next = state.next_employee;
  const stock = { ...state.stock };
  const people = p.employees
    .filter(
      (e) =>
        (!p.active.includes(e.id) ||
          p.milestones.includes("new_first_lemonade_sold")) &&
        !e.busy,
    )
    .map((e) => ({ ...e, ref: e.id }));
  const fresh = (id) =>
    state.modules?.includes("new_milestones") &&
    !p.milestones.includes(id) &&
    !state.closed_milestones.includes(id);
  let recruiterBonus = fresh("new_first_recruiting_girl_used");
  let trainerBonus = fresh("new_first_trainer_used");
  const gift = (kind) => {
    const id = `e${next++}`;
    people.push({ id, kind, ref: id, bonus: true });
    stock[kind] = Math.max(0, (stock[kind] || 0) - 1);
  };
  draft.work.hire.forEach((h, i) => {
    people.push({
      id: `e${next++}`,
      kind: h.kind,
      ref: `hire:${i}`,
      newHire: true,
    });
    stock[h.kind] = (stock[h.kind] || 0) - 1;
    if (
      recruiterBonus &&
      p.employees.find((e) => e.id === h.recruiter)?.kind === "recruiting_girl"
    ) {
      gift("executive_vice_president");
      recruiterBonus = false;
    }
  });
  if (
    !state.modules?.includes("new_milestones") &&
    draft.work.hire.length >= 3 &&
    !state.introductory &&
    !p.milestones.includes("first_hire_three") &&
    !state.closed_milestones.includes("first_hire_three")
  ) {
    for (
      let i = 0;
      i < Math.min(2, Math.max(0, stock.management_trainee));
      i++
    ) {
      const id = `e${next++}`;
      people.push({ id, kind: "management_trainee", ref: id, bonus: true });
    }
  }
  for (const train of draft.work.train.slice(0, before)) {
    const person = people.find((e) => e.ref === train.target);
    if (person && train.path.length) person.kind = train.path.at(-1);
    if (
      person &&
      train.path.length &&
      trainerBonus &&
      p.employees.find((e) => e.id === train.trainer)?.kind === "trainer"
    ) {
      if (stock.trainer > 0) gift("trainer");
      trainerBonus = false;
    }
  }
  return people;
}
export function buildAction(phase, draft) {
  if (phase === "setup_restaurants") {
    if (!draft.position) throw new Error("请先在地图上选择餐厅位置。");
    return {
      type: "place_restaurant",
      position: draft.position,
      entrance: draft.entrance,
    };
  }
  if (phase === "reserve")
    return { type: "choose_reserve", amount: draft.reserve };
  if (phase === "restructure")
    return { type: "restructure", structure: draft.structure };
  if (phase === "order") {
    if (draft.order === null) throw new Error("请选择行动顺序。");
    return { type: "choose_order", position: draft.order };
  }
  if (phase === "payday")
    return {
      type: "payday",
      fire: draft.fire,
      ...(Object.values(draft.food || {}).some(Boolean)
        ? { food: draft.food }
        : {}),
    };
  if (phase === "bonus") {
    if (!draft.bonusChoice) throw new Error("请选择奖励的合法选址。");
    return { type: "choose_bonus", choice: draft.bonusChoice };
  }
  if (phase === "cleanup") return { type: "cleanup", keep: draft.keep };
  if (phase === "work") {
    const a = { type: "work" };
    for (const section of Object.keys(draft.work))
      a[section] = draft.work[section].map((row) => {
        const r = structuredClone(row);
        if (section === "train") {
          if (!r.target || !r.path.length)
            throw new Error("请为每项培训选择员工和晋升路径。");
          if (r.target.startsWith("hire:"))
            r.hire_index = Number(r.target.slice(5));
          else r.employee = r.target;
          delete r.target;
        }
        if (section === "market") {
          if (r.position === null) delete r.position;
          if (r.side) {
            delete r.position;
            delete r.rotate;
          } else {
            delete r.side;
            delete r.offset;
          }
        }
        if (section === "produce" && r.route) {
          delete r.product;
        }
        if (section === "develop") {
          if (r.mode === "house") delete r.house_id;
          else delete r.new_house_id;
          delete r.mode;
        }
        if (r.restaurant_id === "") delete r.restaurant_id;
        return r;
      });
    return a;
  }
  throw new Error("当前阶段不需要提交操作。");
}
export function companySlots(state, pid, structure, cards) {
  const em = Object.fromEntries(
    state.players[pid].employees.map((e) => [e.id, e]),
  );
  const managers = Object.keys(structure).filter(
    (id) => cards[em[id]?.kind]?.slots,
  );
  const capacity =
    (state.players[pid].milestones.includes("new_first_burger_sold")
      ? 4
      : state.ceo_slots) +
    managers.reduce((n, id) => n + cards[em[id].kind].slots, 0);
  const used = Object.keys(structure).length;
  const counts = {};
  for (const parent of Object.values(structure))
    counts[parent] = (counts[parent] || 0) + 1;
  const valid =
    Object.entries(structure).every(([id, parent]) => {
      if (!em[id] || em[id].busy) return false;
      if (parent === `${pid}:ceo`) return true;
      return (
        structure[parent] === `${pid}:ceo` &&
        !!cards[em[parent]?.kind]?.slots &&
        !(cards[em[id].kind].manager || cards[em[id].kind].slots)
      );
    }) &&
    Object.entries(counts).every(
      ([parent, n]) =>
        n <=
        (parent === `${pid}:ceo`
          ? state.players[pid].milestones.includes("new_first_burger_sold")
            ? 4
            : state.ceo_slots
          : cards[em[parent]?.kind]?.slots || 0),
    );
  return { capacity, used, free: capacity - used, valid };
}
