import { el, badge, button } from "./dom.js";
import { milestones, colors } from "./labels.js";

export function milestonePanel(room, viewer, openRules) {
  const state = room.state;
  const pool = state.introductory ? [] : state.milestone_pool || [];
  const closed = new Set(state.closed_milestones || []);
  const members = new Map(
    (room.members || []).map((member) => [member.id, member]),
  );
  const players = Object.entries(state.players);
  const entries = pool.map((id) => {
    const owners = players.filter(([, player]) =>
      player.milestones.includes(id),
    );
    const status = state.finished
      ? "finished"
      : closed.has(id)
        ? "closed"
        : owners.length
          ? "claimed"
          : "available";
    return { id, owners, status };
  });
  const remaining = entries.filter((entry) =>
    ["available", "claimed"].includes(entry.status),
  ).length;
  return el(
    "section",
    { class: "milestones-panel card", "aria-label": "本局里程碑" },
    el(
      "div",
      { class: "section-title" },
      el(
        "div",
        {},
        el("h2", {}, "本局里程碑"),
        el(
          "p",
          { class: "muted small" },
          state.introductory
            ? "入门模式不启用里程碑。"
            : `共 ${pool.length} 项 · ${remaining} 项仍可领取`,
        ),
      ),
      openRules && button("查看规则", openRules, "text small"),
    ),
    !state.introductory &&
      el(
        "p",
        { class: "milestones-note" },
        "同一回合可以有多人获得；关闭后不再发放，已有奖励保留。",
      ),
    el(
      "ul",
      { class: "milestones-list" },
      entries.map(({ id, owners, status }) =>
        el(
          "li",
          { class: `milestone-item ${status}`, dataset: { milestone: id } },
          el(
            "div",
            { class: "milestone-item-heading" },
            el("strong", {}, milestones[id] || id),
            badge(
              {
                available: "尚可领取",
                claimed: "本轮可跟进",
                closed: "已关闭",
                finished: "对局已结束",
              }[status],
              status === "available"
                ? "green"
                : status === "claimed"
                  ? "sand"
                  : "",
            ),
          ),
          el(
            "div",
            { class: "milestone-owners" },
            el("span", { class: "small muted" }, "获得者"),
            owners.length
              ? owners.map(([pid]) => {
                  const seat =
                    members.get(pid)?.seat ??
                    players.findIndex(([key]) => key === pid);
                  return el(
                    "span",
                    {
                      class: `milestone-owner${pid === viewer ? " is-you" : ""}`,
                    },
                    el("span", {
                      class: "milestone-owner-dot",
                      style: { background: colors[seat % colors.length] },
                      "aria-hidden": "true",
                    }),
                    members.get(pid)?.name || pid,
                    pid === viewer && el("small", {}, "（你）"),
                  );
                })
              : el("span", { class: "small muted" }, "暂无"),
          ),
        ),
      ),
    ),
  );
}
