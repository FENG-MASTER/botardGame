export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on"))
      node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key === "style") Object.assign(node.style, value);
    else if (key in node && !key.startsWith("aria")) node[key] = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat(Infinity))
    if (child !== null && child !== undefined && child !== false)
      node.append(
        child instanceof Node ? child : document.createTextNode(String(child)),
      );
  return node;
}
export const button = (text, onClick, kind = "", props = {}) =>
  el(
    "button",
    { type: "button", class: `btn ${kind}`, onclick: onClick, ...props },
    text,
  );
export const field = (label, input, hint) =>
  el(
    "label",
    { class: "field" },
    el("span", { class: "field-label" }, label),
    input,
    hint && el("small", {}, hint),
  );
export const input = (value, onChange, props = {}) =>
  el("input", {
    value: value ?? "",
    oninput: (e) => onChange(e.target.value),
    ...props,
  });
export function select(options, value, onChange, props = {}) {
  const node = el(
    "select",
    { onchange: (e) => onChange(e.target.value), ...props },
    options.map((o) =>
      el("option", { value: o.value, disabled: o.disabled }, o.label),
    ),
  );
  node.value = String(value ?? "");
  return node;
}
export const badge = (text, kind = "") =>
  el("span", { class: `badge ${kind}` }, text);
export const empty = (title, subtitle) =>
  el(
    "div",
    { class: "empty-state" },
    el("span", { class: "empty-mark" }, "◇"),
    el("h3", {}, title),
    el("p", {}, subtitle),
  );
export function toast(text, error = false) {
  const node = document.getElementById("toast");
  node.textContent = text;
  node.className = `visible ${error ? "error" : ""}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (node.className = ""), 6500);
}
export const money = (n) => `$${Number(n || 0).toLocaleString()}`;
export const short = (id) =>
  String(id || "")
    .slice(0, 8)
    .toUpperCase();
export async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("已复制");
  } catch {
    toast("浏览器未允许复制，请选中文本手动复制。", true);
  }
}
