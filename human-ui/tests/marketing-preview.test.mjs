import test from "node:test";
import assert from "node:assert/strict";
import { marketingPreviews } from "../src/marketing-preview.js";
import { renderBoard } from "../src/board.js";
import { installDOM } from "./dom.mjs";

test("marketing draft remains visible after picking and rotates the complete footprint", () => {
  const dom = installDOM();
  try {
    const state = {
      phase: "work",
      players: {},
      campaigns: [],
      board: {
        width: 10,
        height: 10,
        cells: Array.from({ length: 10 }, () => Array(10).fill("empty")),
        houses: [
          { id: "A", cells: [[3, 1]], demand: [] },
          { id: "B", cells: [[1, 3]], demand: [] },
        ],
      },
      campaign_tiles: {
        1: { kind: "billboard", width: 2, height: 1 },
        2: { kind: "airplane", width: 2, height: 1 },
      },
    };
    const row = { campaign_id: "1", position: [1, 1], product: "burger" };
    const draft = { work: { market: [row] } };
    assert.deepEqual(
      marketingPreviews(state, draft)[0].houses.map((h) => h.id),
      ["A"],
    );
    let board = renderBoard(state, { draft, pick: null });
    assert.equal(
      board.querySelector(".marketing-footprint").getAttribute("width"),
      "72",
    );
    assert.match(board.textContent, /尚未提交/);
    row.rotate = true;
    assert.deepEqual(
      marketingPreviews(state, draft)[0].houses.map((h) => h.id),
      ["B"],
    );
    board = renderBoard(state, { draft, pick: null });
    assert.equal(
      board.querySelector(".marketing-footprint").getAttribute("height"),
      "72",
    );
    draft.work.market = [
      {
        campaign_id: "2",
        side: "top",
        offset: 1,
        product: "pizza",
        edge_tile: [0, 1],
      },
    ];
    const plane = marketingPreviews(state, draft)[0];
    assert.equal(plane.line, 5);
    assert.deepEqual(
      plane.houses.map((h) => h.id),
      ["B"],
    );
    board = renderBoard(state, { draft });
    assert.equal(
      board.querySelector(".marketing-flight-strip").getAttribute("width"),
      "72",
    );
    draft.work.market = [];
    assert.equal(
      renderBoard(state, { draft }).querySelector(".marketing-preview"),
      null,
    );
  } finally {
    dom.window.close();
  }
});
