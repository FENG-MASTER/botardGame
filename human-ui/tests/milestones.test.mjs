import test from "node:test";
import assert from "node:assert/strict";
import { installDOM } from "./dom.mjs";
import { milestonePanel } from "../src/milestones.js";

test("milestones show shared owners, closure and the selected expansion pool", () => {
  const dom = installDOM();
  try {
    const room = {
      members: [{ id: "human", name: "<b>玩家</b>", seat: 0 }, { id: "agent", name: "Atlas", seat: 1 }],
      state: {
        milestone_pool: ["first_train", "first_waitress", "first_burger_marketed"],
        closed_milestones: ["first_waitress"],
        players: {
          human: { milestones: ["first_train", "first_waitress"] },
          agent: { milestones: ["first_train"] },
        },
      },
    };
    let opened = false;
    const panel = milestonePanel(room, "human", () => { opened = true; });
    assert.equal(panel.querySelectorAll("li").length, 3);
    const shared = panel.querySelector('[data-milestone="first_train"]');
    assert.equal(shared.querySelectorAll(".milestone-owner").length, 2);
    assert.match(shared.textContent, /本轮可跟进/);
    assert.match(shared.textContent, /<b>玩家<\/b>（你）/);
    assert.equal(panel.querySelector("b"), null);
    const closed = panel.querySelector('[data-milestone="first_waitress"]');
    assert.match(closed.textContent, /已关闭/);
    assert.equal(closed.querySelectorAll(".milestone-owner").length, 1);
    assert.match(panel.textContent, /2 项仍可领取/);
    panel.querySelector("button").click();
    assert.equal(opened, true);
    room.state.milestone_pool = ["new_first_train"];
    const expanded = milestonePanel(room, "human");
    assert.equal(expanded.querySelectorAll("li").length, 1);
    assert.equal(expanded.querySelector('[data-milestone="first_train"]'), null);
    room.state.finished = true;
    assert.match(milestonePanel(room, "human").textContent, /0 项仍可领取.*对局已结束/);
    room.state.introductory = true;
    const intro = milestonePanel(room, "human");
    assert.equal(intro.querySelectorAll("li").length, 0);
    assert.match(intro.textContent, /入门模式不启用里程碑/);
  } finally {
    dom.window.close();
  }
});
