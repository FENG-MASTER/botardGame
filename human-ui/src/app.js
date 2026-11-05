import { API, APIError, makeTransaction, definitive } from "./api.js";
import {
  el,
  button,
  field,
  input,
  select,
  badge,
  empty,
  toast,
  money,
  short,
  copy,
} from "./dom.js";
import {
  products,
  productIcons,
  employees,
  phases,
  steps,
  colors,
  milestones,
  ability,
} from "./labels.js";
import { freshDraft, buildAction, draftStamp } from "./model.js";
import { renderBoard } from "./board.js";
import { actionPanel } from "./fcm.js";
import { preview } from "./preview.js";
import { modulePicker, moduleProblem } from "./modules.js";

const stored = JSON.parse(sessionStorage.getItem("table.identity") || "null");
const api = new API(stored?.token || "");
const state = {
  identity: stored,
  ready: false,
  connection: "checking",
  games: [],
  rooms: [],
  room: null,
  options: null,
  draft: null,
  pending: null,
  events: [],
  cursor: 0,
  pick: null,
  inspected: null,
  zoom: 100,
  workTab: "hire",
  busy: false,
  authMode: "new",
  name: "",
  token: "",
  registrationKey: "",
  joinId: "",
  joinCode: "",
  capacity: 2,
  intro: false,
  modules: [],
  seed: "",
  selectedGame: "fcm",
  rules: null,
  showRules: false,
};
const app = document.getElementById("app");
let syncRunning = false;
let currentRoute = "";
let generation = 0;
const sessionKey = (id) => `table.pending.${state.identity?.id}.${id}`;
const draftKey = (id) => `table.draft.${state.identity?.id}.${id}`;
const route = () => location.hash.slice(1) || "lobby";
const isPreview = () => route() === "preview";
const isRoom = () => route().startsWith("room/");
const navigate = (path) => {
  location.hash = path;
};
function persistDraft() {
  if (state.room && !isPreview() && state.draft)
    sessionStorage.setItem(
      draftKey(state.room.id),
      JSON.stringify(state.draft),
    );
}
function changed() {
  persistDraft();
  render();
}
function error(e) {
  toast(
    e.code === "version_conflict"
      ? "对局已更新，计划已保留。请检查后重新提交。"
      : e.message || "操作失败，请重试。",
    true,
  );
}
function setIdentity(identity) {
  state.identity = identity;
  api.token = identity?.token || "";
  if (identity)
    sessionStorage.setItem("table.identity", JSON.stringify(identity));
  else sessionStorage.removeItem("table.identity");
}
async function busy(fn) {
  if (state.busy) return;
  state.busy = true;
  render();
  try {
    await fn();
  } catch (e) {
    error(e);
  } finally {
    state.busy = false;
    render();
  }
}
async function authenticate() {
  await busy(async () => {
    if (state.authMode === "new") {
      const identity = await api.register(
        state.name.trim(),
        state.registrationKey,
      );
      setIdentity(identity);
    } else {
      api.token = state.token.trim();
      try {
        const me = await api.me();
        setIdentity({ ...me, token: api.token });
      } catch (e) {
        api.token = "";
        throw e;
      }
    }
    state.connection = "online";
    navigate("lobby");
    await syncLobby();
    toast("入座成功，欢迎来到围桌。");
  });
}
async function syncLobby() {
  const [rooms, games] = await Promise.all([api.rooms(), api.games()]);
  state.rooms = rooms.rooms;
  state.games = games.games;
  state.connection = "online";
}
async function loadRoute() {
  const myGeneration = ++generation;
  const path = route();
  currentRoute = path;
  state.showRules = false;
  state.rules = null;
  state.pick = null;
  state.workTab = "hire";
  state.room = null;
  state.options = null;
  state.events = [];
  state.cursor = 0;
  state.draft = null;
  state.pending = null;
  render();
  if (path === "preview") {
    state.room = structuredClone(preview.room);
    state.options = structuredClone(preview.options);
    state.draft = freshDraft(state.room.state);
    render();
    return;
  }
  if (!state.identity) {
    render();
    return;
  }
  try {
    if (path.startsWith("room/")) {
      const id = path.slice(5);
      if (!/^[a-f0-9]{32}$/.test(id)) throw new Error("房间编号格式不正确。");
      const [room, options] = await Promise.all([
        api.room(id),
        api.actions(id),
      ]);
      if (myGeneration !== generation) return;
      state.room = room;
      state.options = options;
      state.pending = JSON.parse(
        sessionStorage.getItem(sessionKey(id)) || "null",
      );
      const saved = JSON.parse(sessionStorage.getItem(draftKey(id)) || "null");
      state.draft = room.state
        ? saved?.stamp === draftStamp(room.state)
          ? saved
          : freshDraft(room.state)
        : null;
      if (!state.games.length) {
        const response = await api.games();
        if (myGeneration !== generation) return;
        state.games = response.games;
      }
      await fetchEvents(id, myGeneration);
    } else await syncLobby();
    if (myGeneration === generation) {
      state.connection = "online";
      render();
    }
  } catch (e) {
    if (myGeneration === generation) {
      state.connection = "offline";
      error(e);
      render();
    }
  }
}
async function fetchEvents(id, g = generation) {
  const result = await api.events(id, state.cursor);
  if (g !== generation) return;
  state.cursor = result.cursor;
  state.events = [...state.events, ...result.events].slice(-60);
}
async function refresh() {
  if (syncRunning || state.busy || isPreview() || !state.identity) return;
  syncRunning = true;
  const g = generation;
  try {
    if (isRoom() && state.room) {
      const id = state.room.id;
      const room = await api.room(id);
      if (g !== generation) return;
      if (room.version !== state.room.version || !state.options) {
        const options = await api.actions(id);
        if (g !== generation) return;
        state.room = room;
        state.options = options;
        const stamp = room.state && draftStamp(room.state);
        if (stamp && state.draft?.stamp !== stamp) {
          state.draft = freshDraft(room.state);
          state.pick = null;
          persistDraft();
        }
        await fetchEvents(id, g);
        if (g === generation) render();
      }
    } else if (!isRoom()) {
      const rooms = await api.rooms();
      if (g !== generation) return;
      if (JSON.stringify(rooms.rooms) !== JSON.stringify(state.rooms)) {
        state.rooms = rooms.rooms;
        render();
      }
    }
    if (state.connection !== "online") {
      state.connection = "online";
      render();
    }
  } catch (e) {
    if (g === generation && state.connection !== "offline") {
      state.connection = "offline";
      render();
    }
  } finally {
    syncRunning = false;
  }
}
async function createRoom() {
  await busy(async () => {
    const game = state.games.find((g) => g.id === state.selectedGame);
    const problem =
      game?.modules &&
      moduleProblem(
        game?.modules || [],
        state.modules,
        Number(state.capacity),
        state.intro,
      );
    if (problem) throw new Error(problem);
    const room = await api.create({
      game: state.selectedGame,
      capacity: Number(state.capacity),
      config: {
        introductory: state.intro,
        ...(game?.modules ? { modules: state.modules } : {}),
      },
      ...(state.seed !== "" ? { seed: Number(state.seed) } : {}),
    });
    sessionStorage.setItem(`table.invite.${room.id}`, room.join_code);
    navigate(`room/${room.id}`);
  });
}
async function joinRoom() {
  await busy(async () => {
    const room = await api.join(state.joinId.trim(), state.joinCode.trim());
    navigate(`room/${room.id}`);
  });
}
async function transact(action, operation = "actions") {
  if (isPreview()) {
    toast("这是演示棋盘。入座并加入真实房间后即可开始游戏。");
    return;
  }
  await busy(async () => {
    const id = state.room.id;
    if (!state.pending) {
      if (operation === "actions")
        await api.validate(id, state.room.version, action);
      state.pending = makeTransaction(operation, state.room.version, action);
      sessionStorage.setItem(sessionKey(id), JSON.stringify(state.pending));
    }
    try {
      await api.mutate(id, state.pending);
      state.pending = null;
      sessionStorage.removeItem(sessionKey(id));
      sessionStorage.removeItem(draftKey(id));
      state.draft = null;
      await loadRoute();
      toast("已提交，游戏桌已更新。");
    } catch (e) {
      if (definitive(e)) {
        state.pending = null;
        sessionStorage.removeItem(sessionKey(id));
        if (e.code === "version_conflict") {
          const [room, options] = await Promise.all([
            api.room(id),
            api.actions(id),
          ]);
          state.room = room;
          state.options = options;
          if (state.draft?.stamp !== (room.state ? draftStamp(room.state) : ""))
            state.draft = room.state ? freshDraft(room.state) : null;
        }
      }
      throw e;
    }
  });
}
async function validatePlan() {
  if (isPreview()) {
    toast("演示模式不提交校验。实际房间会由服务器校验完整计划。");
    return;
  }
  await busy(async () => {
    await api.validate(
      state.room.id,
      state.room.version,
      buildAction(state.room.state.phase, state.draft),
    );
    toast("计划合法，可以提交。");
  });
}
async function openRules() {
  state.showRules = true;
  render();
  try {
    const rules = await api.rules(
      state.room?.game || state.selectedGame,
      isPreview() ? undefined : state.room?.id,
    );
    state.rules = rules;
    render();
  } catch (e) {
    state.rules = { error: e.message };
    render();
  }
}
function mapCell(point) {
  state.inspected = point;
  const { room, draft, pick } = state;
  if (!draft || !state.options?.can_act || state.pending || state.busy) {
    render();
    return;
  }
  if (pick?.mode === "route") {
    const row = draft.work.produce[pick.index];
    if (row) {
      const p = pick.tiles ? point.map((v) => Math.floor(v / 5)) : point;
      row.route.push(p);
    }
    changed();
    return;
  }
  if (pick?.mode === "position") {
    draft.work[pick.section][pick.index].position = point;
    state.pick = null;
    changed();
    return;
  }
  if (room.state.phase === "setup_restaurants") {
    const valid = state.options.placements?.filter(
      (a) => a.position[0] === point[0] && a.position[1] === point[1],
    );
    if (valid?.length) {
      draft.position = point;
      draft.entrance = valid[0].entrance;
      changed();
      return;
    }
    toast("这里不能放置起始餐厅，请选择绿色标记。", true);
  }
  render();
}
function render() {
  const focus = document.activeElement;
  const inputs = [...document.querySelectorAll("input,select,textarea")];
  const focusIndex = inputs.indexOf(focus);
  let start, end;
  try {
    start = focus.selectionStart;
    end = focus.selectionEnd;
  } catch {}
  app.replaceChildren(
    el(
      "div",
      { class: "shell" },
      sidebar(),
      el(
        "main",
        { class: "main" },
        topbar(),
        isPreview() || isRoom()
          ? roomPage()
          : state.identity
            ? lobby()
            : welcome(),
      ),
    ),
  );
  if (state.showRules) app.append(rulesModal());
  if (focusIndex >= 0) {
    const next = document.querySelectorAll("input,select,textarea")[focusIndex];
    if (next) {
      next.focus({ preventScroll: true });
      try {
        if (start !== null) next.setSelectionRange(start, end);
      } catch {}
    }
  }
}
function sidebar() {
  const logo = el(
    "a",
    { href: "#lobby", class: "brand" },
    el("img", { src: "/favicon.svg", alt: "围桌标志" }),
    el(
      "span",
      {},
      el("strong", {}, "围桌"),
      el("small", {}, "A SEAT FOR EVERYONE"),
    ),
  );
  return el(
    "aside",
    { class: "sidebar" },
    logo,
    el("div", { class: "nav-caption" }, "一起，玩一局"),
    el(
      "nav",
      {},
      button(
        el("span", {}, el("i", {}, "▦"), "游戏大厅"),
        () => navigate("lobby"),
        `nav-item ${!isRoom() && !isPreview() ? "selected" : ""}`,
      ),
      button(
        el("span", {}, el("i", {}, "◈"), "当前游戏桌"),
        () =>
          state.room && !isPreview()
            ? navigate(`room/${state.room.id}`)
            : navigate("preview"),
        `nav-item ${isRoom() || isPreview() ? "selected" : ""}`,
      ),
      button(
        el("span", {}, el("i", {}, "☷"), "玩法手册"),
        openRules,
        "nav-item",
      ),
    ),
    el(
      "div",
      { class: "sidebar-note" },
      el("div", { class: "table-glyph" }, "◌"),
      el("strong", {}, "人类与 Agent，", el("br"), "同一张游戏桌。"),
      el("p", {}, "相同的规则，平等的座位。", el("br"), "把好奇心带上就好。"),
    ),
    el(
      "div",
      { class: "sidebar-bottom" },
      el(
        "span",
        { class: `connection ${state.connection}` },
        el("span", {}),
        state.connection === "online"
          ? "已连接游戏服务器"
          : state.connection === "offline"
            ? "连接中断 · 自动重试"
            : "正在连接",
      ),
      el(
        "div",
        { class: "profile" },
        el(
          "div",
          { class: "avatar" },
          state.identity?.name?.slice(0, 1) || "客",
        ),
        el(
          "div",
          {},
          el("strong", {}, state.identity?.name || "还没有入座"),
          el("small", {}, state.identity ? "人类玩家" : "欢迎来玩"),
        ),
      ),
      state.identity && button("账户与身份凭证", account, "text small"),
    ),
  );
}
function account() {
  const identity = state.identity;
  const dialog = el(
    "dialog",
    { class: "modal account-modal" },
    el(
      "div",
      { class: "modal-heading" },
      el("h2", {}, "你的玩家身份"),
      button("×", () => dialog.close(), "icon"),
    ),
    el(
      "p",
      { class: "muted" },
      "请保存身份凭证。下次可用它恢复玩家身份和对局。不要分享给其他玩家。",
    ),
    field(
      "身份凭证",
      el("input", { type: "password", value: identity.token, readOnly: true }),
    ),
    el(
      "div",
      { class: "button-row" },
      button("复制凭证", () => copy(identity.token), "primary"),
      button(
        "退出此标签页",
        () => {
          dialog.close();
          setIdentity(null);
          state.room = null;
          state.games = [];
          state.rooms = [];
          navigate("lobby");
          render();
        },
        "secondary",
      ),
    ),
  );
  document.body.append(dialog);
  dialog.addEventListener("close", () => dialog.remove());
  dialog.showModal();
}
function topbar() {
  return el(
    "header",
    { class: "topbar" },
    el(
      "div",
      { class: "breadcrumb" },
      el("span", {}, "围桌"),
      el("span", {}, "/"),
      el(
        "strong",
        {},
        isPreview() ? "游戏桌预览" : isRoom() ? "正在游戏" : "游戏大厅",
      ),
    ),
    el(
      "div",
      { class: "topbar-right" },
      el("span", { class: "small muted" }, "留一点时间，给好玩的事。"),
      badge("HUMAN + AGENT", "outline"),
    ),
  );
}
function townArt() {
  return el(
    "div",
    { class: "town-art", "aria-hidden": "true" },
    el("div", { class: "art-orbit" }),
    el(
      "div",
      { class: "art-board" },
      Array.from({ length: 25 }, (_, i) =>
        el(
          "div",
          {
            class: `art-tile ${Math.floor(i / 5) === 2 || i % 5 === 2 ? "art-road" : ""}`,
          },
          [0, 4, 16, 24].includes(i)
            ? "⌂"
            : i === 8
              ? "♣"
              : i === 18
                ? "🍋"
                : i === 6
                  ? "🍔"
                  : "",
        ),
      ),
    ),
    el(
      "div",
      { class: "floating-label" },
      el("span", { class: "status-dot active" }),
      "下一桌，有你。",
    ),
  );
}
function welcome() {
  return el(
    "div",
    { class: "welcome page" },
    el(
      "section",
      { class: "welcome-hero" },
      el(
        "div",
        { class: "hero-copy" },
        el("p", { class: "eyebrow" }, "LESS SCROLLING. MORE PLAYING."),
        el("h1", {}, "好游戏，", el("br"), "值得坐下来。"),
        el(
          "p",
          { class: "hero-subtitle" },
          "与朋友，或一位聪明的 Agent。",
          el("br"),
          "经营你的餐厅，展开一场认真又轻松的较量。",
        ),
        button("先看看游戏桌 ↗", () => navigate("preview"), "secondary"),
        el(
          "div",
          { class: "hero-footnote" },
          el("span", {}, "01"),
          "从食物链大亨开始，更多桌游正在路上。",
        ),
      ),
      townArt(),
    ),
    el(
      "div",
      { class: "welcome-lower" },
      el(
        "section",
        { class: "featured-game" },
        el("p", { class: "eyebrow" }, "FIRST ON THE TABLE"),
        el("div", { class: "game-icon" }, "🍔"),
        el("h2", {}, "食物链大亨"),
        el("p", { class: "serif-sub" }, "Food Chain Magnate"),
        el(
          "p",
          { class: "muted" },
          "一张城市地图，一家小餐厅。",
          el("br"),
          "从招聘第一名员工，到打造自己的餐饮帝国。",
        ),
        el(
          "div",
          { class: "game-meta" },
          badge("2–5 人"),
          badge("经营策略"),
          badge("基础规则 · 开发版", "sand"),
        ),
      ),
      el(
        "section",
        { class: "auth-card" },
        el(
          "div",
          { class: "section-title" },
          el(
            "div",
            {},
            el("p", { class: "eyebrow" }, "YOUR SEAT IS READY"),
            el("h2", {}, "先认识一下"),
          ),
          badge("人类玩家", "green"),
        ),
        el(
          "div",
          { class: "segmented" },
          button(
            "第一次来",
            () => {
              state.authMode = "new";
              render();
            },
            state.authMode === "new" ? "selected" : "",
          ),
          button(
            "恢复身份",
            () => {
              state.authMode = "token";
              render();
            },
            state.authMode === "token" ? "selected" : "",
          ),
        ),
        el(
          "form",
          {
            onsubmit: (e) => {
              e.preventDefault();
              authenticate();
            },
          },
          state.authMode === "new"
            ? [
                field(
                  "怎么称呼你？",
                  input(state.name, (v) => (state.name = v), {
                    placeholder: "例如：林间小馆",
                    maxLength: 80,
                    required: true,
                    autocomplete: "nickname",
                  }),
                ),
                el(
                  "details",
                  {},
                  el("summary", {}, "服务器设置了注册口令？"),
                  field(
                    "注册口令",
                    input(
                      state.registrationKey,
                      (v) => (state.registrationKey = v),
                      { type: "password", autocomplete: "off" },
                    ),
                  ),
                ),
              ]
            : field(
                "你的身份凭证",
                input(state.token, (v) => (state.token = v), {
                  type: "password",
                  placeholder: "粘贴之前保存的 token",
                  required: true,
                  autocomplete: "off",
                }),
              ),
          el(
            "button",
            { class: "btn primary full", type: "submit", disabled: state.busy },
            state.busy ? "正在入座…" : "入座，开始玩 →",
          ),
        ),
        el(
          "p",
          { class: "auth-note" },
          "凭证仅保存在当前标签页的会话中。",
          el("br"),
          "入座后可在账户中复制保存。",
        ),
      ),
    ),
  );
}
function lobby() {
  const games = state.games.length ? state.games : [preview.catalog];
  const selected = games.find((g) => g.id === state.selectedGame) || games[0];
  return el(
    "div",
    { class: "page lobby-page" },
    el(
      "div",
      { class: "page-title" },
      el(
        "div",
        {},
        el("p", { class: "eyebrow" }, "FIND YOUR NEXT GAME"),
        el("h1", {}, `你好，${state.identity.name}。`),
        el("p", { class: "muted" }, "开一张新桌，或回到还没结束的故事。"),
      ),
      button("刷新房间", () => busy(syncLobby), "secondary"),
    ),
    el(
      "div",
      { class: "lobby-layout" },
      el(
        "div",
        {},
        el(
          "section",
          { class: "game-choice card" },
          el("div", { class: "game-choice-art" }, "🍔"),
          el(
            "div",
            {},
            el("p", { class: "eyebrow" }, "FOOD CHAIN MAGNATE"),
            el("h2", {}, "从一家小餐厅开始"),
            el(
              "p",
              { class: "muted" },
              "招聘、营销、生产。在这座城市里，做出你的生意。",
            ),
            el(
              "div",
              { class: "game-meta" },
              badge("2–5 位玩家"),
              badge("支持 Agent 同桌", "green"),
              badge("开发版场景", "sand"),
            ),
          ),
        ),
        el(
          "section",
          { class: "rooms-section" },
          el(
            "div",
            { class: "section-title" },
            el("h2", {}, "我的游戏桌"),
            el(
              "span",
              { class: "muted small" },
              `${state.rooms.length} 张桌子`,
            ),
          ),
          state.rooms.length
            ? el(
                "div",
                { class: "room-list" },
                state.rooms.map((r) =>
                  el(
                    "button",
                    {
                      class: "room-list-item",
                      onclick: () => navigate(`room/${r.id}`),
                    },
                    el("span", { class: "room-icon" }, "♜"),
                    el(
                      "div",
                      {},
                      el(
                        "strong",
                        {},
                        `${r.game === "fcm" ? "食物链大亨" : r.game} · ${short(r.id)}`,
                      ),
                      el("small", {}, `最多 ${r.capacity} 位玩家`),
                    ),
                    badge(
                      {
                        lobby: "等待入座",
                        active: "对局进行中",
                        finished: "已结束",
                      }[r.status],
                      r.status === "active" ? "green" : "",
                    ),
                    el("span", { class: "room-arrow" }, "↗"),
                  ),
                ),
              )
            : empty(
                "还没有开始的故事",
                "创建一张游戏桌，邀请朋友或 Agent 入座。",
              ),
        ),
      ),
      el(
        "div",
        { class: "lobby-forms" },
        el(
          "section",
          { class: "card" },
          el("p", { class: "eyebrow" }, "MAKE A TABLE"),
          el("h2", {}, "开一张新桌"),
          el(
            "form",
            {
              onsubmit: (e) => {
                e.preventDefault();
                createRoom();
              },
            },
            field(
              "选择桌游",
              select(
                games.map((g) => ({
                  value: g.id,
                  label: g.name,
                  disabled: g.id !== "fcm",
                })),
                state.selectedGame,
                (v) => {
                  state.selectedGame = v;
                  state.modules = [];
                  render();
                },
              ),
            ),
            field(
              "入座人数",
              select(
                Array.from(
                  { length: selected.max_players - selected.min_players + 1 },
                  (_, i) => ({
                    value: i + selected.min_players,
                    label: `${i + selected.min_players} 位玩家`,
                  }),
                ),
                state.capacity,
                (v) => {
                  state.capacity = Number(v);
                  render();
                },
              ),
            ),
            el(
              "label",
              { class: "check-field" },
              el("input", {
                type: "checkbox",
                checked: state.intro,
                onchange: (e) => {
                  state.intro = e.target.checked;
                  if (state.intro) state.modules = [];
                  render();
                },
              }),
              "入门模式（不发薪、无里程碑）",
            ),
            selected.modules &&
              modulePicker(selected.modules, state.modules, {
                capacity: Number(state.capacity),
                introductory: state.intro,
                onChange: (value) => {
                  state.modules = value;
                  render();
                },
              }),
            el(
              "details",
              {},
              el("summary", {}, "地图设置"),
              field(
                "随机种子（可选）",
                input(state.seed, (v) => (state.seed = v), {
                  type: "number",
                  min: 0,
                  max: 2147483647,
                  placeholder: "留空生成新地图",
                }),
              ),
            ),
            el(
              "button",
              {
                class: "btn primary full",
                disabled:
                  state.busy ||
                  (selected.modules &&
                    !!moduleProblem(
                      selected.modules || [],
                      state.modules,
                      Number(state.capacity),
                      state.intro,
                    )),
                type: "submit",
              },
              "创建游戏桌 →",
            ),
          ),
        ),
        el(
          "section",
          { class: "card join-card" },
          el("h3", {}, "朋友已经开桌了？"),
          el(
            "form",
            {
              onsubmit: (e) => {
                e.preventDefault();
                joinRoom();
              },
            },
            field(
              "房间编号",
              input(state.joinId, (v) => (state.joinId = v), {
                placeholder: "粘贴完整房间 ID",
                required: true,
                pattern: "[a-f0-9]{32}",
              }),
            ),
            field(
              "邀请码",
              input(state.joinCode, (v) => (state.joinCode = v), {
                placeholder: "向房主索取邀请码",
                required: true,
              }),
            ),
            el(
              "button",
              {
                class: "btn secondary full",
                type: "submit",
                disabled: state.busy,
              },
              "加入这张桌",
            ),
          ),
        ),
      ),
    ),
  );
}
function roomPage() {
  if (!state.identity && !isPreview()) return welcome();
  if (!state.room)
    return el(
      "div",
      { class: "page" },
      empty(
        state.connection === "offline" ? "暂时无法进入房间" : "正在铺好游戏桌…",
        "请确认游戏服务器在线，且当前身份已加入此房间。",
      ),
      button("重新连接", loadRoute, "primary"),
    );
  const room = state.room;
  if (room.status === "lobby") return waitingRoom(room);
  const s = room.state;
  const pid = isPreview() ? "preview-human" : state.identity.id;
  const p = s.players[pid];
  const fullCatalog = (
    isPreview() ? preview.catalog : state.games.find((g) => g.id === room.game)
  )?.employees;
  const catalog =
    fullCatalog &&
    Object.fromEntries(
      Object.entries(fullCatalog).filter(
        ([key]) => key === "ceo" || Object.hasOwn(s.stock, key),
      ),
    );
  if (room.game !== "fcm" || !catalog)
    return el(
      "div",
      { class: "page" },
      empty(
        "这款游戏暂未安装可视化插件",
        "平台已识别这张游戏桌；当前前端提供 FCM 的完整操作界面。",
      ),
    );
  const ctx = {
    state: s,
    pid,
    options: state.options || {},
    draft: state.draft || freshDraft(s),
    catalog,
    changed,
    submit: transact,
    validate: validatePlan,
    busy: state.busy,
    pending: state.pending,
    retry: () => transact(),
    error,
    openRules,
    workTab: state.workTab,
    setWorkTab: (v) => {
      state.workTab = v;
      state.pick = null;
      render();
    },
    pick: (v) => {
      state.pick = v;
      render();
      document
        .querySelector(".map-panel")
        ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    },
    cancelPick: () => (state.pick = null),
  };
  return el(
    "div",
    { class: "page game-page" },
    isPreview() &&
      el(
        "div",
        { class: "preview-banner" },
        el("span", {}, "演示棋盘 · 可探索界面，不会影响任何真实对局"),
        button(
          state.identity ? "去创建游戏桌" : "入座开始游戏",
          () => navigate("lobby"),
          "small",
        ),
      ),
    el(
      "div",
      { class: "game-title" },
      el(
        "div",
        {},
        el(
          "p",
          { class: "eyebrow" },
          `FOOD CHAIN MAGNATE / ${isPreview() ? "PREVIEW" : short(room.id)}`,
        ),
        el("h1", {}, "食物链大亨", badge("基础版", "sand")),
      ),
      el(
        "div",
        { class: "game-stats" },
        el(
          "div",
          {},
          el("small", {}, "当前回合"),
          el("strong", {}, String(s.round).padStart(2, "0")),
        ),
        el(
          "div",
          {},
          el("small", {}, "银行资金"),
          el("strong", {}, money(s.bank)),
        ),
        el(
          "div",
          {},
          el("small", {}, "银行破产"),
          el("strong", {}, `${s.bank_breaks} / ${s.introductory ? 1 : 2}`),
        ),
      ),
    ),
    el(
      "div",
      { class: "phase-track" },
      steps.map((phase, i) =>
        el(
          "div",
          {
            class: `phase-step ${s.phase === phase ? "current" : ""} ${steps.indexOf(s.phase) > i ? "done" : ""}`,
          },
          el("span", {}, String(i + 1).padStart(2, "0")),
          phases[phase],
        ),
      ),
    ),
    el(
      "div",
      { class: "game-layout" },
      el(
        "div",
        { class: "game-main" },
        renderBoard(s, {
          pid,
          options: state.options,
          draft: state.draft,
          pick: state.pick,
          onCell: mapCell,
          onPickEnd: () => {
            state.pick = null;
            render();
          },
          zoom: state.zoom,
          onZoom: (v) => {
            state.zoom = v;
            render();
          },
          inspected: state.inspected,
        }),
        companyPanel(s, pid, catalog),
        tablePlayers(room, pid),
        eventPanel(room),
      ),
      actionPanel(ctx),
    ),
  );
}
function companyPanel(s, pid, cards) {
  const p = s.players[pid];
  return el(
    "section",
    { class: "company-panel card" },
    el(
      "div",
      { class: "section-title" },
      el(
        "div",
        {},
        el("p", { class: "eyebrow" }, "YOUR LITTLE EMPIRE"),
        el("h2", {}, "我的餐饮连锁"),
      ),
      el(
        "div",
        { class: "cash-pill" },
        el("small", {}, "现金"),
        el("strong", {}, money(p.cash)),
      ),
    ),
    el(
      "div",
      { class: "inventory-strip" },
      Object.entries(products).map(([k, label]) =>
        el(
          "div",
          { class: "inventory-item" },
          el("span", { class: "product-icon" }, productIcons[k]),
          el(
            "span",
            {},
            el("strong", {}, p.inventory[k]),
            el("small", {}, label),
          ),
        ),
      ),
    ),
    el(
      "div",
      { class: "staff-heading" },
      el("strong", {}, "员工团队"),
      el(
        "span",
        { class: "muted small" },
        `${p.employees.length} 人 · ${p.active.length} 人工作中`,
      ),
    ),
    el(
      "div",
      { class: "employee-grid" },
      p.employees.map((e) =>
        el(
          "div",
          { class: `employee-card ${p.active.includes(e.id) ? "active" : ""}` },
          el(
            "div",
            { class: "employee-card-top" },
            el(
              "span",
              { class: "employee-icon" },
              e.kind === "ceo"
                ? "♜"
                : cards[e.kind].marketing
                  ? "◉"
                  : cards[e.kind].train
                    ? "↗"
                    : cards[e.kind].quantity
                      ? "♨"
                      : "◇",
            ),
            badge(
              e.busy ? "营销中" : p.active.includes(e.id) ? "工作中" : "在海滩",
              e.busy ? "sand" : p.active.includes(e.id) ? "green" : "",
            ),
          ),
          el("strong", {}, employees[e.kind] || e.kind),
          el("small", {}, ability(cards[e.kind])),
          el(
            "div",
            { class: "employee-bottom" },
            el("span", {}, e.kind === "ceo" ? "CEO" : e.id),
            el("span", {}, cards[e.kind].salary ? "$5 / 轮" : "无需工资"),
          ),
        ),
      ),
    ),
    el(
      "div",
      { class: "milestone-row" },
      el("span", { class: "small muted" }, "已获里程碑"),
      p.milestones.length
        ? p.milestones.map((m) => badge(`✦ ${milestones[m] || m}`, "sand"))
        : el("span", { class: "small muted" }, "下一项成就，等你达成。"),
    ),
    el(
      "details",
      { class: "supply-details" },
      el("summary", {}, "查看公共员工库存与能力"),
      el(
        "div",
        { class: "supply-grid" },
        Object.entries(s.stock).map(([kind, count]) =>
          el(
            "div",
            {},
            el("strong", {}, employees[kind] || kind),
            badge(`${count} 张`),
            el(
              "small",
              {},
              `${ability(cards[kind])} · ${cards[kind].salary ? "工资 $5" : "无需工资"}`,
            ),
            el(
              "small",
              {},
              `可晋升：${cards[kind].upgrades.map((k) => employees[k] || k).join("、") || "无"}`,
            ),
          ),
        ),
      ),
    ),
  );
}
function tablePlayers(room, pid) {
  const s = room.state;
  return el(
    "section",
    { class: "players-panel card" },
    el(
      "div",
      { class: "section-title" },
      el("h2", {}, "同桌玩家"),
      badge(`${room.members.length} 人`),
    ),
    el(
      "div",
      { class: "player-grid" },
      room.members.map((m, index) => {
        const p = s.players[m.id];
        return el(
          "details",
          { class: "player-summary" },
          el(
            "summary",
            {},
            el(
              "div",
              {
                class: "avatar",
                style: {
                  background: colors[index] + "20",
                  color: colors[index],
                },
              },
              m.name.slice(0, 1),
            ),
            el(
              "div",
              {},
              el("strong", {}, `${m.name}${m.id === pid ? " · 你" : ""}`),
              el(
                "small",
                {},
                `${m.kind === "agent" ? "Agent" : "人类"} · ${p.eliminated ? "已退出" : s.actors?.includes(m.id) ? "正在决策" : "在桌上"}`,
              ),
            ),
            el("strong", {}, money(p.cash)),
          ),
          el(
            "div",
            { class: "player-detail" },
            el(
              "p",
              {},
              `库存：${Object.entries(p.inventory)
                .map(([k, v]) => `${productIcons[k]} ${v}`)
                .join("  ")}`,
            ),
            el(
              "p",
              {},
              `员工：${p.employees.map((e) => `${employees[e.kind] || e.kind}${e.busy ? "（营销中）" : p.active.includes(e.id) ? "（工作）" : ""}`).join("、")}`,
            ),
            el(
              "p",
              {},
              `里程碑：${p.milestones.map((m) => milestones[m] || m).join("、") || "暂无"}`,
            ),
            el(
              "p",
              {},
              `储备卡：${s.reserves[m.id] === null || s.reserves[m.id] === undefined ? "保密" : money(s.reserves[m.id])}`,
            ),
          ),
        );
      }),
    ),
  );
}
function eventPanel(room) {
  const name = (id) => room.members.find((m) => m.id === id)?.name || "玩家";
  const entries = state.events
    .flatMap((batch) =>
      batch.events.map((e) => ({ ...e, version: batch.version })),
    )
    .filter((e) => e.type !== "action_submitted");
  return el(
    "details",
    { class: "event-panel card", open: false },
    el(
      "summary",
      {},
      "对局记录",
      el("span", { class: "muted small" }, `${entries.length} 条`),
    ),
    entries.length
      ? el(
          "div",
          { class: "event-list" },
          entries
            .slice(-30)
            .reverse()
            .map((e) =>
              el(
                "div",
                {},
                el("span", { class: "event-dot" }),
                el("span", {}, eventText(e, name)),
                el("small", {}, `#${e.version}`),
              ),
            ),
        )
      : el(
          "p",
          { class: "muted" },
          isPreview() ? "演示棋盘不产生真实记录。" : "新的故事从这里开始。",
        ),
  );
}
function eventText(e, name) {
  return (
    {
      game_started: "所有人已入座，游戏开始。",
      player_joined: `${name(e.player)} 加入了游戏桌。`,
      structures_revealed: "所有公司结构已公开。",
      decision_automated: `${name(e.player)} 的${phases[e.phase] || e.phase}已自动完成：${{ no_available_employees: "没有可安排的员工", only_position: "只剩一个顺位", no_firing_choice: "没有裁员选择", empty_inventory: "没有剩余库存", no_freezer: "没有可用冰柜，按规则丢弃库存" }[e.reason] || e.reason}。`,
      work_completed: `${name(e.player)} 完成了今日工作。`,
      milestone: `${name(e.player)} 达成「${milestones[e.milestone] || e.milestone}」。`,
      house_served: `房屋 ${e.house} 在 ${name(e.player)} 用餐，收入 ${money(e.income)}。`,
      salaries_paid: `${name(e.player)} 支付了 ${money(e.amount)} 工资。`,
      marketing_resolved: "营销活动已结算，居民需求已更新。",
      bank_broken: `银行第 ${e.number} 次破产。`,
      game_finished: `本局结束，${name(e.winner)} 获胜。`,
      chain_bankrupt: `${name(e.player)} 的连锁破产退出。`,
      structure_overflow: `${name(e.player)} 的组织超出容量，只剩 CEO 工作。`,
    }[e.type] || e.type
  );
}
function waitingRoom(room) {
  const code = sessionStorage.getItem(`table.invite.${room.id}`);
  const game = state.games.find((g) => g.id === room.game);
  const selectedModules = room.config?.modules || [];
  return el(
    "div",
    { class: "page waiting-page" },
    el(
      "div",
      { class: "page-title" },
      el(
        "div",
        {},
        el("p", { class: "eyebrow" }, "GOOD COMPANY, GREAT GAMES"),
        el("h1", {}, "等大家坐好。"),
        el("p", { class: "muted" }, "人齐了，今天的故事就开始。"),
        el(
          "p",
          { class: "muted" },
          selectedModules.length
            ? `已启用 ${selectedModules.length} 个扩展：${selectedModules.map((id) => game?.modules?.find((m) => m.id === id)?.name || id).join("、")}`
            : "规则：基础版",
        ),
      ),
      badge(`${room.members.length} / ${room.capacity} 已入座`, "green"),
    ),
    el(
      "div",
      { class: "waiting-layout" },
      el(
        "section",
        { class: "card seats-card" },
        el(
          "div",
          { class: "table-illustration" },
          el("span", {}, "围桌", el("small", {}, "FOOD CHAIN MAGNATE")),
        ),
        el(
          "div",
          { class: "seats" },
          Array.from({ length: room.capacity }, (_, i) => {
            const p = room.members[i];
            return el(
              "div",
              { class: `seat ${p ? "occupied" : ""}` },
              el("div", { class: "avatar" }, p ? p.name.slice(0, 1) : "+"),
              el("strong", {}, p?.name || "等一位玩家"),
              el(
                "small",
                {},
                p
                  ? p.kind === "agent"
                    ? "Agent 玩家"
                    : "人类玩家"
                  : "朋友或 Agent 都可以",
              ),
            );
          }),
        ),
      ),
      el(
        "section",
        { class: "card invite-card" },
        el("h2", {}, "邀请同桌"),
        field("房间编号", el("input", { readOnly: true, value: room.id })),
        button("复制房间编号", () => copy(room.id), "secondary full"),
        code
          ? [
              field("邀请码", el("input", { readOnly: true, value: code })),
              button(
                "复制完整邀请",
                () => copy(`房间编号：${room.id}\n邀请码：${code}`),
                "secondary full",
              ),
            ]
          : el(
              "p",
              { class: "hint" },
              "邀请码由创建房间的标签页保存；若你已加入，等待房主开始即可。",
            ),
        el("hr"),
        room.owner === state.identity.id
          ? button(
              state.busy ? "正在准备…" : "开始营业 →",
              () => transact(undefined, "start"),
              "primary full",
              { disabled: state.busy || room.members.length !== room.capacity },
            )
          : el("p", { class: "hint" }, "等待房主开始游戏。"),
        state.pending &&
          button("重试上次开始请求", () => transact(), "secondary full", {
            disabled: state.busy,
          }),
        el(
          "p",
          { class: "small muted" },
          "所有参与者需使用各自的身份。同一 token 对应同一位玩家。",
        ),
      ),
    ),
  );
}
function rulesModal() {
  const content = state.rules?.error
    ? empty("暂时无法读取规则", state.rules.error)
    : state.rules
      ? el(
          "div",
          { class: "rule-content" },
          ...markdown(
            state.rules.room_rules_text ||
              state.rules.rules_text ||
              state.rules.implementation_notes ||
              "此游戏暂未提供完整规则说明。",
          ),
          el(
            "details",
            {},
            el("summary", {}, "规则实现差异"),
            el("pre", {}, state.rules.implementation_notes || ""),
          ),
        )
      : empty("正在翻开玩法手册…", "规则说明来自游戏服务器。");
  return el(
    "div",
    {
      class: "modal-backdrop",
      onclick: (e) => {
        if (e.target === e.currentTarget) {
          state.showRules = false;
          render();
        }
      },
    },
    el(
      "section",
      {
        class: "modal rules-modal",
        role: "dialog",
        "aria-modal": true,
        "aria-label": "游戏玩法手册",
      },
      el(
        "div",
        { class: "modal-heading" },
        el(
          "div",
          {},
          el("p", { class: "eyebrow" }, "THE RULEBOOK"),
          el("h2", {}, "玩法手册"),
        ),
        button(
          "关闭 ×",
          () => {
            state.showRules = false;
            render();
          },
          "secondary",
        ),
      ),
      content,
    ),
  );
}
function markdown(text) {
  return text
    .split("\n")
    .filter((l) => l.trim() && !l.startsWith("```"))
    .map((line) => {
      const match = line.match(/^(#{1,3})\s+(.*)/);
      if (match)
        return el(`h${Math.min(match[1].length + 1, 4)}`, {}, match[2]);
      if (line.startsWith("|"))
        return el("p", { class: "rule-table-row" }, line);
      return el("p", {}, line.replace(/\*\*/g, "").replace(/`/g, ""));
    });
}
window.addEventListener("hashchange", loadRoute);
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && state.showRules) {
    state.showRules = false;
    render();
  }
});
window.addEventListener("online", refresh);
setInterval(refresh, 3500);
async function boot() {
  render();
  if (isPreview()) {
    await loadRoute();
    return;
  }
  try {
    const games = await api.games();
    state.games = games.games;
    state.connection = "online";
    if (state.identity) {
      const me = await api.me();
      setIdentity({ ...me, token: api.token });
    }
  } catch (e) {
    if (e instanceof APIError && e.status === 401) {
      setIdentity(null);
      toast("身份凭证已失效，请重新入座。", true);
    } else state.connection = "offline";
  }
  state.ready = true;
  await loadRoute();
}
boot();
