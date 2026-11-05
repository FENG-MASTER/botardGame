import test from "node:test";
import assert from "node:assert/strict";
import { installDOM, inputLabel, clickText } from "./dom.mjs";
import { preview } from "../src/preview.js";
import {
  expansionWorkFields,
  expansionPhaseFields,
} from "../src/expansion-controls.js";
import { freshDraft, buildAction, draftStamp } from "../src/model.js";
import { renderBoard } from "../src/board.js";

function context() {
  const state = structuredClone(preview.room.state),
    pid = "preview-human";
  state.modules = ["lobbyists", "coffee", "new_milestones", "rural_marketeers"];
  state.phase = "work";
  state.lobby_supply = { road_short: 4 };
  state.offramps = [];
  state.built_features = [];
  state.board.available_tiles = ["district-142d26"];
  state.players[pid].coffee_shops = [];
  state.campaign_tiles["21"] = { kind: "giant_billboard", width: 1, height: 1 };
  return { state, pid, draft: freshDraft(state), options: {}, changed() {} };
}
test("lobby and rural forms build placement choices into the atomic plan", () => {
  const dom = installDOM();
  try {
    const ctx = context();
    const row = {
      employee: "l",
      piece: "road_short",
      position: [3, 4],
      rotation: 0,
    };
    ctx.draft.work.lobby.push(row);
    ctx.changed = () =>
      document
        .querySelector("#app")
        .replaceChildren(
          expansionWorkFields(ctx, "lobby", row, { kind: "lobbyist" }),
        );
    ctx.changed();
    document.querySelector("input[type=checkbox]").click();
    inputLabel("板块列 / 行 X", 3);
    inputLabel("板块列 / 行 Y", 0);
    const action = buildAction("work", ctx.draft);
    assert.equal(action.lobby[0].city.tile_id, "district-142d26");
    assert.deepEqual(action.lobby[0].city.tile, [3, 0]);
    const rural = {
      employee: "r",
      campaign_id: "21",
      product: "burger",
      duration: 1,
      rural_side: "left",
      position: null,
    };
    ctx.draft.work.market = [rural];
    ctx.changed = () =>
      document.querySelector("#app").replaceChildren(
        expansionWorkFields(ctx, "market", rural, {
          kind: "rural_marketeer",
        }),
      );
    ctx.changed();
    document.querySelector("input[type=checkbox]").click();
    inputLabel("出口方向", "top");
    assert.equal(buildAction("work", ctx.draft).market[0].offramp.side, "top");
    assert.equal("position" in buildAction("work", ctx.draft).market[0], false);
  } finally {
    dom.window.close();
  }
});
test("training coffee shops, food wages and explicit bonus selection preserve user choices", () => {
  const dom = installDOM();
  try {
    const ctx = context(),
      row = {
        trainer: "t",
        target: "barista",
        path: ["barista", "lead_barista"],
      };
    ctx.draft.work.train = [row];
    ctx.changed = () =>
      document
        .querySelector("#app")
        .replaceChildren(
          expansionWorkFields(ctx, "train", row, { kind: "coach" }),
        );
    ctx.changed();
    clickText("添加咖啡店选址");
    inputLabel("咖啡店 X", 6);
    inputLabel("咖啡店 Y", 3);
    assert.deepEqual(buildAction("work", ctx.draft).train[0].coffee_shops, [
      { position: [6, 3] },
    ]);
    ctx.state.phase = "bonus";
    ctx.state.bonus = { kind: "radio", player: ctx.pid, house: { id: 2 } };
    ctx.options = {
      bonus: ctx.state.bonus,
      choices: [{ position: [1, 3], campaign_id: "1" }],
    };
    ctx.changed = () =>
      document.querySelector("#app").replaceChildren(expansionPhaseFields(ctx));
    ctx.changed();
    inputLabel("合法选址", "0");
    assert.deepEqual(buildAction("bonus", ctx.draft), {
      type: "choose_bonus",
      choice: ctx.options.choices[0],
    });
    const stamp = draftStamp(ctx.state);
    ctx.state.bonus.house.id = 4;
    assert.notEqual(draftStamp(ctx.state), stamp);
    ctx.state.phase = "payday";
    ctx.state.players[ctx.pid].milestones.push("new_first_beer_sold");
    ctx.state.players[ctx.pid].inventory.burger = 3;
    ctx.changed();
    inputLabel("汉堡（库存 3）", 2);
    assert.deepEqual(buildAction("payday", ctx.draft).food, { burger: 2 });
  } finally {
    dom.window.close();
  }
});
test("expansion board displays coffee shops, construction, roadworks and rural demand without invalid bounds", () => {
  const dom = installDOM();
  try {
    const ctx = context();
    ctx.state.players[ctx.pid].coffee_shops = [{ id: "c1", cells: [[1, 3]] }];
    ctx.state.roadworks = [[2, 4]];
    ctx.state.built_features = [
      {
        kind: "road",
        cells: [
          [3, 4],
          [4, 4],
        ],
      },
    ];
    ctx.state.board.cells[4][3] = "construction";
    ctx.state.rural = { demand: ["burger", "burger"] };
    ctx.state.campaigns.push({
      id: "21",
      kind: "giant_billboard",
      product: "burger",
      cells: [],
      rural_side: "left",
      eternal: true,
    });
    const node = renderBoard(ctx.state, {
      pid: ctx.pid,
      options: {},
      draft: ctx.draft,
      onCell() {},
      onZoom() {},
      onInspect() {},
    });
    assert.match(node.textContent, /乡村区域/);
    assert.match(node.textContent, /☕/);
    assert.match(node.textContent, /⚠/);
    assert.doesNotMatch(node.outerHTML, /NaN|Infinity/);
  } finally {
    dom.window.close();
  }
});

test("same-turn active promotion exposes the new employee ability in work forms", async () => {
  const { actionPanel } = await import("../src/fcm.js");
  const dom = installDOM();
  try {
    const ctx = context(),
      p = ctx.state.players[ctx.pid];
    p.milestones.push("new_first_lemonade_sold");
    p.employees.push({ id: "promoted", kind: "marketing_trainee", busy: null });
    p.active.push("promoted");
    ctx.draft.work.train.push({
      trainer: "trainer",
      target: "promoted",
      path: ["rural_marketeer"],
    });
    ctx.catalog = {
      ...preview.catalog.employees,
      rural_marketeer: {
        ...preview.catalog.employees.marketing_trainee,
        marketing: 1,
        upgrades: [],
      },
    };
    ctx.options = { can_act: true, actions: [{ type: "work" }] };
    ctx.workTab = "market";
    ctx.setWorkTab = () => {};
    ctx.cancelPick = () => {};
    ctx.openRules = () => {};
    ctx.submit = () => {};
    ctx.validate = () => {};
    document.querySelector("#app").replaceChildren(actionPanel(ctx));
    clickText("+ 添加");
    const row = ctx.draft.work.market[0];
    assert.equal(row.employee, "promoted");
    assert.equal(row.campaign_id, "21");
    assert.equal(row.rural_side, "left");
  } finally {
    dom.window.close();
  }
});
