import test from "node:test";
import assert from "node:assert/strict";
import { installDOM, until, clickText, inputLabel } from "./dom.mjs";
import { preview } from "../src/preview.js";
import { actionPanel } from "../src/fcm.js";
import { renderBoard } from "../src/board.js";
import {
  freshDraft,
  buildAction,
  companySlots,
  previewBeach,
} from "../src/model.js";

test("preview renders without a server and work forms produce a human-authored plan", async () => {
  const dom = installDOM();
  const originalInterval = globalThis.setInterval;
  globalThis.setInterval = () => 0;
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    throw Error("Offline preview must not call a game API");
  };
  await import("../src/app.js");
  await until(() => document.querySelector(".city-board"), "map");
  assert.match(document.body.textContent, /演示棋盘/);
  assert.equal(document.querySelectorAll(".map-hit").length, 225);
  assert.equal(document.querySelectorAll(".employee-card").length, 6);
  clickText("+ 添加");
  assert.equal(document.querySelectorAll(".plan-card").length, 1);
  inputLabel("招聘职位", "kitchen_trainee");
  clickText("培训");
  clickText("+ 添加");
  inputLabel("培训目标", "hire:0");
  inputLabel("第 1 级晋升", "burger_cook");
  assert.match(document.querySelector(".plan-card").textContent, /汉堡厨师/);
  clickText("检查计划");
  assert.match(document.querySelector("#toast").textContent, /演示模式/);
  globalThis.setInterval = originalInterval;
  globalThis.fetch = previousFetch;
  dom.window.close();
});

test("every FCM decision phase renders usable controls and creates the correct action shape", () => {
  const dom = installDOM();
  const pid = "preview-human";
  const s = structuredClone(preview.room.state);
  const cards = preview.catalog.employees;
  const cases = {
    setup_restaurants: "place_restaurant",
    reserve: "choose_reserve",
    restructure: "restructure",
    order: "choose_order",
    work: "work",
    payday: "payday",
    cleanup: "cleanup",
  };
  for (const [phase, type] of Object.entries(cases)) {
    s.phase = phase;
    const draft = freshDraft(s);
    draft.position = [3, 0];
    draft.order = 0;
    let submitted = null;
    const ctx = {
      state: s,
      pid,
      catalog: cards,
      draft,
      options: {
        can_act: true,
        actions: [],
        available_positions: [0, 1],
        freezer_capacity: 10,
      },
      changed: () => {},
      submit: (a) => (submitted = a),
      validate: () => {},
      error: (e) => {
        throw e;
      },
      openRules: () => {},
      setWorkTab: () => {},
      cancelPick: () => {},
      pick: () => {},
    };
    const panel = actionPanel(ctx);
    document.querySelector("#app").replaceChildren(panel);
    const button = panel.querySelector(".submit-bar .primary");
    assert.ok(button, phase);
    button.click();
    assert.equal(submitted.type, type);
  }
  dom.window.close();
});

test("working plan supports all six steps including routes and newly hired trainees", () => {
  const d = freshDraft(preview.room.state);
  d.work.hire.push({ recruiter: "preview-human:ceo", kind: "kitchen_trainee" });
  d.work.train.push({ trainer: "e2", target: "hire:0", path: ["burger_cook"] });
  d.work.market.push({
    employee: "e7",
    campaign_id: "4",
    product: "beer",
    duration: 2,
    side: "left",
    offset: 0,
    position: null,
    rotate: false,
  });
  d.work.produce.push({
    employee: "e8",
    route: [
      [2, 0],
      [2, 1],
    ],
    product: "beer",
  });
  d.work.develop.push({
    employee: "e9",
    mode: "garden",
    house_id: 10,
    new_house_id: 1,
    position: [0, 3],
    rotate: false,
  });
  d.work.restaurants.push({
    employee: "e10",
    restaurant_id: "",
    position: [3, 5],
    entrance: 0,
  });
  const action = buildAction("work", d);
  assert.equal(action.train[0].hire_index, 0);
  assert.ok(!("target" in action.train[0]));
  assert.ok(!("position" in action.market[0]));
  assert.ok(!("product" in action.produce[0]));
  assert.ok(!("mode" in action.develop[0]));
  assert.ok(!("new_house_id" in action.develop[0]));
  assert.ok(!("restaurant_id" in action.restaurants[0]));
  assert.equal(
    d.work.market[0].position,
    null,
    "compilation must not mutate the draft",
  );
});

test("organization slots, payroll selections, and milestone trainee previews", () => {
  const s = structuredClone(preview.room.state);
  const pid = "preview-human";
  const d = freshDraft(s);
  const cards = preview.catalog.employees;
  const mgmt = s.players[pid].employees.find(
    (e) => e.kind === "management_trainee",
  );
  assert.equal(
    companySlots(s, pid, { [mgmt.id]: `${pid}:ceo`, e1: mgmt.id }, cards).free,
    3,
  );
  assert.equal(companySlots(s, pid, { e1: "unknown" }, cards).valid, false);
  d.work.hire = [
    { kind: "kitchen_trainee" },
    { kind: "waitress" },
    { kind: "trainer" },
  ];
  const candidates = previewBeach(s, pid, d, cards);
  assert.equal(candidates.filter((e) => e.newHire).length, 3);
  assert.equal(candidates.filter((e) => e.bonus).length, 2);
  d.fire = ["e1"];
  assert.deepEqual(buildAction("payday", d), { type: "payday", fire: ["e1"] });
});

test("SVG map represents houses, marketing routes and separate player restaurants without HTML injection", () => {
  const dom = installDOM();
  const s = structuredClone(preview.room.state);
  const draft = freshDraft(s);
  draft.work.produce = [
    {
      route: [
        [2, 0],
        [2, 1],
        [2, 2],
      ],
    },
  ];
  let clicked;
  const board = renderBoard(s, {
    pid: "preview-human",
    options: { can_act: true },
    draft,
    pick: { mode: "route", section: "produce", index: 0 },
    onCell: (p) => (clicked = p),
    onPickEnd: () => {},
    onZoom: () => {},
  });
  document.querySelector("#app").replaceChildren(board);
  board.querySelectorAll(".map-hit")[4].dispatchEvent(new MouseEvent("click"));
  assert.deepEqual(clicked, [4, 0]);
  assert.equal(board.querySelectorAll("polyline").length, 1);
  assert.match(board.textContent, /你的连锁/);
  dom.window.close();
});

test("work panel hides unavailable abilities but preserves drafted rows for correction", () => {
  const dom = installDOM();
  try {
    const s = structuredClone(preview.room.state),
      pid = "preview-human";
    s.phase = "work";
    s.players[pid].active = [`${pid}:ceo`];
    const draft = freshDraft(s);
    const ctx = {
      state: s,
      pid,
      catalog: preview.catalog.employees,
      draft,
      workTab: "produce",
      options: { can_act: true },
      changed: () => {},
      submit: () => {},
      validate: () => {},
      error: (e) => {
        throw e;
      },
      openRules: () => {},
      setWorkTab: () => {},
      cancelPick: () => {},
      pick: () => {},
    };
    let panel = actionPanel(ctx);
    assert.deepEqual(
      [...panel.querySelectorAll(".work-tab")].map((n) => n.textContent),
      ["招聘"],
    );
    assert.match(panel.textContent, /已自动隐藏/);
    draft.work.produce.push({ employee: "unavailable", product: "burger" });
    panel = actionPanel(ctx);
    assert.equal(panel.querySelectorAll(".work-tab").length, 2);
    assert.equal(panel.querySelectorAll(".plan-card").length, 1);
    assert.equal(draft.work.produce.length, 1);
  } finally {
    dom.window.close();
  }
});
