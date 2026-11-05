import { el, button } from "./dom.js";

export function moduleProblem(modules, selected, capacity, introductory) {
  const ids = new Set(selected);
  if (introductory && ids.size) return "入门模式不能同时启用扩展。";
  for (const id of ids) {
    const module = modules.find((m) => m.id === id);
    if (!module?.available) return "选择中包含尚未开放的扩展。";
    if (module.requires?.some((dep) => !ids.has(dep)))
      return `${module.name}需要同时启用新城区。`;
    if (module.incompatible_with?.some((other) => ids.has(other)))
      return "艰难抉择与新里程碑不能同时启用。";
  }
  if (capacity === 6 && (!ids.has("six_players") || !ids.has("new_districts")))
    return "六人局需要启用六人游戏和新城区。";
  if (capacity !== 6 && ids.has("six_players"))
    return "六人游戏扩展需要把入座人数设为六人。";
  if (capacity >= 5 && ids.has("lobbyists") && !ids.has("new_districts"))
    return "五人或六人使用说客时，需要同时启用新城区。";
  return null;
}

export function modulePicker(
  modules,
  selected,
  { capacity, introductory, onChange },
) {
  const selectedSet = new Set(selected);
  return el(
    "fieldset",
    { class: "module-picker" },
    el("legend", {}, `扩展设置 · 已选 ${selected.length} 个`),
    el(
      "p",
      { class: "muted small" },
      "不选就是基础版。可同时选择多个扩展，规则组合会在创建前检查。",
    ),
    el(
      "div",
      { class: "module-grid" },
      modules.map((module) =>
        el(
          "label",
          { class: `module-option ${module.available ? "" : "unavailable"}` },
          el("input", {
            type: "checkbox",
            checked: selectedSet.has(module.id),
            disabled: introductory || !module.available,
            onchange: (e) => {
              const next = new Set(selected);
              if (e.target.checked) next.add(module.id);
              else next.delete(module.id);
              onChange([...next]);
            },
          }),
          el(
            "span",
            {},
            module.name,
            !module.available && el("small", {}, "尚未开放"),
          ),
        ),
      ),
    ),
    button("只玩基础版", () => onChange([]), "text small"),
    moduleProblem(modules, selected, capacity, introductory) &&
      el(
        "p",
        { class: "error-text", role: "status" },
        moduleProblem(modules, selected, capacity, introductory),
      ),
  );
}
