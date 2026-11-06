(() => {
  const DISPLAY_TYPES = new Set(["info", "markdown", "image"]);
  const app = document.querySelector("#app");

  const ERROR_TEXT = {
    required: "필수 항목입니다.",
    "must be a number": "숫자를 입력하세요.",
  };

  let interaction = window.__INTERACT__ || null;
  let renderedKey = "";
  let dirty = new Set();
  let fieldNodes = new Map();

  if (!interaction) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "아직 열린 질문이 없습니다.";
    app.append(empty);
  } else {
    render(interaction, null);
  }

  setInterval(refreshInteraction, 1000);

  async function refreshInteraction() {
    const id = interaction && interaction.id ? interaction.id : location.pathname.split("/").pop();
    if (!id) return;
    try {
      const response = await fetch("/api/interactions/" + encodeURIComponent(id), { cache: "no-store" });
      if (!response.ok) return;
      const next = await response.json();
      if (!next) return;
      const nextKey = next.id + ":" + (next.updatedAt || next.createdAt || "");
      if (nextKey === renderedKey) return;
      const sameInteraction = interaction && interaction.id === next.id;
      const preserved = sameInteraction ? collectPreserved() : null;
      if (!sameInteraction) dirty = new Set();
      interaction = next;
      render(next, preserved);
    } catch {
      // Keep the current screen while the server is unavailable.
    }
  }

  function render(data, preserved) {
    renderedKey = data.id + ":" + (data.updatedAt || data.createdAt || "");
    document.title = (data.title ? data.title + " · " : "") + "Interact";
    app.innerHTML = "";

    const header = document.createElement("header");

    const meta = document.createElement("div");
    meta.className = "meta";
    const dot = document.createElement("span");
    dot.className = "dot";
    dot.setAttribute("title", "이 화면은 자동으로 갱신됩니다");
    const id = document.createElement("span");
    id.className = "meta-id";
    id.textContent = data.id || "interact";
    meta.append(dot, id);

    const title = document.createElement("h1");
    title.textContent = data.title || "Question";
    header.append(meta, title);
    if (data.description) {
      header.append(renderMarkdown(data.description, "description"));
    }

    const fields = data.fields || [];
    const answerFields = fields.filter((field) => !DISPLAY_TYPES.has(field.type));

    const form = document.createElement("form");
    form.noValidate = true;
    fieldNodes = new Map();
    let answerIndex = 0;
    for (const field of fields) {
      const numbered = !DISPLAY_TYPES.has(field.type) && answerFields.length > 1;
      if (!DISPLAY_TYPES.has(field.type)) answerIndex += 1;
      const node = renderRow(field, numbered ? answerIndex : 0);
      fieldNodes.set(field.id, node);
      form.append(node);
    }
    form.addEventListener("input", markDirty);
    form.addEventListener("change", markDirty);

    const actions = document.createElement("div");
    actions.className = "actions";
    const status = document.createElement("div");
    status.id = "status";
    status.setAttribute("role", "status");
    actions.append(status);

    if (answerFields.length > 0) {
      const submit = document.createElement("button");
      submit.type = "submit";
      submit.textContent = data.submitLabel || "Submit";
      actions.append(submit);
      form.addEventListener("submit", (event) => submitForm(event, data, status));
    } else {
      status.textContent = "응답이 필요하지 않습니다. 이 화면은 자동으로 갱신됩니다.";
      status.classList.add("muted");
    }

    form.append(actions);
    app.append(header, form);
    app.append(renderFooter(data));

    applyPreserved(data, preserved);
  }

  async function submitForm(event, data, status) {
    event.preventDefault();
    status.classList.remove("error");
    status.textContent = "Submitting...";
    try {
      const response = await fetch("/api/interactions/" + encodeURIComponent(data.id) + "/answer", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ values: collectValues(data.fields || []) }),
      });
      const result = await response.json();
      if (!response.ok) {
        const errors = result.errors || [];
        showFieldErrors(errors);
        status.classList.add("error");
        status.textContent = errors.length > 0
          ? "표시된 항목을 확인해주세요."
          : "제출할 수 없습니다.";
        return;
      }
      clearAllFieldErrors();
      dirty = new Set();
      status.textContent = "제출되었습니다. agent가 이어서 진행할 수 있습니다.";
    } catch {
      status.classList.add("error");
      status.textContent = "서버에 연결할 수 없습니다.";
    }
  }

  function renderFooter(data) {
    const footer = document.createElement("footer");
    const stamp = data.updatedAt || data.createdAt;
    if (stamp) {
      const time = new Date(stamp);
      if (!Number.isNaN(time.getTime())) {
        footer.textContent = "마지막 갱신 " + time.toLocaleTimeString();
      }
    }
    return footer;
  }

  function markDirty(event) {
    const name = event.target && event.target.name;
    if (!name) return;
    dirty.add(name);
    clearFieldError(name);
  }

  function showFieldErrors(errors) {
    clearAllFieldErrors();
    let first = null;
    for (const error of errors) {
      const node = fieldNodes.get(error.field);
      if (!node) continue;
      node.classList.add("invalid");
      const message = document.createElement("p");
      message.className = "field-error";
      message.textContent = ERROR_TEXT[error.message] || translateBound(error.message);
      (node.querySelector(".row-body") || node).append(message);
      if (!first) first = node;
    }
    if (first && typeof first.scrollIntoView === "function") {
      first.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  function translateBound(message) {
    const bound = String(message).match(/^select at (least|most) (\d+)$/);
    if (bound) return "최" + (bound[1] === "least" ? "소" : "대") + " " + bound[2] + "개를 선택하세요.";
    const range = String(message).match(/^must be at (least|most) (.+)$/);
    if (range) return range[2] + " " + (range[1] === "least" ? "이상" : "이하") + "이어야 합니다.";
    return String(message);
  }

  function clearFieldError(id) {
    const node = fieldNodes.get(id);
    if (!node) return;
    node.classList.remove("invalid");
    const message = node.querySelector(".field-error");
    if (message) message.remove();
  }

  function clearAllFieldErrors() {
    for (const id of fieldNodes.keys()) clearFieldError(id);
  }

  // ---------------------------------------------------------------- fields

  // Answer fields render as a two-column row: label rail on the left, control on
  // the right. Display fields span the full width.
  function renderRow(field, index) {
    const row = document.createElement("div");

    if (DISPLAY_TYPES.has(field.type)) {
      row.className = "row row-full";
      if (field.label && field.label !== field.id) {
        const title = document.createElement("p");
        title.className = "row-name";
        title.textContent = field.label;
        row.append(title);
      }
      row.append(renderDisplay(field));
      return row;
    }

    row.className = "row";
    const grouped = field.type === "single-select" || field.type === "multi-select";

    const labelCell = document.createElement("div");
    labelCell.className = "row-label";
    if (index) {
      const number = document.createElement("span");
      number.className = "row-index";
      number.textContent = index < 10 ? "0" + index : String(index);
      labelCell.append(number);
    }

    // Groups of inputs cannot use <label for>, so they are labelled by reference.
    const label = document.createElement(grouped ? "span" : "label");
    label.className = "row-name";
    if (grouped) {
      label.id = field.id + "-label";
      row.setAttribute("role", "group");
      row.setAttribute("aria-labelledby", label.id);
    } else {
      label.setAttribute("for", field.id);
    }
    applyLabel(label, field);
    labelCell.append(label);

    const body = document.createElement("div");
    body.className = "row-body";
    if (field.description) body.append(hint(field));
    body.append(renderControl(field));

    row.append(labelCell, body);
    return row;
  }

  function renderDisplay(field) {
    if (field.type === "markdown") {
      return renderMarkdown(field.content || field.description || "", "markdown");
    }
    if (field.type === "image") {
      const wrap = document.createElement("div");
      if (field.description) wrap.append(hint(field));
      wrap.append(renderGallery(imageList(field)));
      return wrap;
    }
    const text = document.createElement("p");
    text.className = "note";
    text.textContent = field.description || field.label || "";
    return text;
  }

  function renderControl(field) {
    if (field.type === "single-select" || field.type === "multi-select") {
      const options = document.createElement("div");
      options.className = field.options && field.options.some((option) => option.image)
        ? "options options-visual"
        : "options";

      for (const option of field.options || []) {
        const row = document.createElement("label");
        row.className = option.image ? "option option-visual" : "option";
        const input = document.createElement("input");
        input.type = field.type === "multi-select" ? "checkbox" : "radio";
        input.name = field.id;
        input.value = option.value;
        input.checked = isDefaultSelected(field, option.value);

        const body = document.createElement("span");
        body.className = "option-body";
        if (option.image) {
          const image = document.createElement("img");
          image.className = "option-image";
          image.src = assetUrl(option.image);
          image.alt = option.label || "";
          image.loading = "lazy";
          body.append(image);
        }
        const title = document.createElement("span");
        title.className = "option-title";
        title.textContent = option.label;
        body.append(title);
        if (option.description) {
          const desc = document.createElement("span");
          desc.className = "option-desc";
          desc.textContent = option.description;
          body.append(desc);
        }
        row.append(input, body);
        options.append(row);
      }
      return options;
    }

    if (field.type === "textarea") {
      const input = document.createElement("textarea");
      input.id = field.id;
      input.name = field.id;
      input.placeholder = field.placeholder || "";
      input.value = field.default === undefined || field.default === null ? "" : String(field.default);
      return input;
    }

    if (field.type === "select") {
      const input = document.createElement("select");
      input.id = field.id;
      input.name = field.id;
      for (const option of field.options || []) {
        const item = document.createElement("option");
        item.value = option.value;
        item.textContent = option.label;
        input.append(item);
      }
      if (field.default !== undefined && field.default !== null) input.value = String(field.default);
      return input;
    }

    if (field.type === "boolean") {
      const toggle = document.createElement("label");
      toggle.className = "toggle";
      const input = document.createElement("input");
      input.id = field.id;
      input.name = field.id;
      input.type = "checkbox";
      input.checked = Boolean(field.default);
      const text = document.createElement("span");
      text.textContent = field.placeholder || "Enabled";
      toggle.append(input, text);
      return toggle;
    }

    const input = document.createElement("input");
    input.id = field.id;
    input.name = field.id;
    input.type = field.type === "number" ? "number" : "text";
    input.placeholder = field.placeholder || "";
    if (field.type === "number" && field.min !== undefined) input.min = field.min;
    if (field.type === "number" && field.max !== undefined) input.max = field.max;
    if (field.default !== undefined && field.default !== null) input.value = String(field.default);
    return input;
  }

  function isDefaultSelected(field, value) {
    const fallback = field.default;
    if (fallback === undefined || fallback === null) return false;
    if (Array.isArray(fallback)) return fallback.map(String).includes(String(value));
    return String(fallback) === String(value);
  }

  function imageList(field) {
    if (Array.isArray(field.images) && field.images.length > 0) return field.images;
    if (field.src) return [{ src: field.src, alt: field.alt, caption: field.caption }];
    return [];
  }

  function renderGallery(items) {
    const gallery = document.createElement("div");
    gallery.className = items.length > 1 ? "gallery gallery-grid" : "gallery";
    for (const item of items) {
      const figure = document.createElement("figure");
      const image = document.createElement("img");
      image.src = assetUrl(item.src);
      image.alt = item.alt || item.caption || "";
      image.loading = "lazy";
      figure.append(image);
      if (item.caption) {
        const caption = document.createElement("figcaption");
        caption.textContent = item.caption;
        figure.append(caption);
      }
      gallery.append(figure);
    }
    return gallery;
  }

  function assetUrl(src) {
    const value = String(src || "");
    if (/^(https?:|data:|blob:)/i.test(value) || value.startsWith("/")) return value;
    return "/asset?p=" + encodeURIComponent(value);
  }

  function hint(field) {
    const value = document.createElement("p");
    value.className = "hint";
    value.textContent = field.description || "";
    return value;
  }

  // The required marker is its own styled element so it can be styled.
  function applyLabel(target, field) {
    target.textContent = field.label;
    if (!field.required) return;
    const mark = document.createElement("span");
    mark.className = "required-mark";
    mark.textContent = "*";
    mark.setAttribute("aria-label", "필수");
    target.append(mark);
  }

  // ------------------------------------------------------------ values

  function collectValues(fields) {
    const values = {};
    for (const field of fields) {
      if (DISPLAY_TYPES.has(field.type)) continue;
      values[field.id] = readFieldValue(field);
    }
    return values;
  }

  function readFieldValue(field) {
    if (field.type === "multi-select") {
      return Array.from(document.querySelectorAll(nameSelector(field.id) + ":checked")).map((item) => item.value);
    }
    if (field.type === "single-select") {
      const selected = document.querySelector(nameSelector(field.id) + ":checked");
      return selected ? selected.value : "";
    }
    if (field.type === "boolean") {
      const input = document.querySelector(nameSelector(field.id));
      return Boolean(input && input.checked);
    }
    const input = document.querySelector(nameSelector(field.id));
    return input ? input.value : "";
  }

  function writeFieldValue(field, value) {
    if (field.type === "multi-select") {
      const selected = (Array.isArray(value) ? value : [value]).map(String);
      for (const input of document.querySelectorAll(nameSelector(field.id))) {
        input.checked = selected.includes(input.value);
      }
      return;
    }
    if (field.type === "single-select") {
      for (const input of document.querySelectorAll(nameSelector(field.id))) {
        input.checked = String(value) === input.value;
      }
      return;
    }
    const input = document.querySelector(nameSelector(field.id));
    if (!input) return;
    if (field.type === "boolean") {
      input.checked = Boolean(value);
      return;
    }
    input.value = value === undefined || value === null ? "" : String(value);
  }

  function collectPreserved() {
    const values = {};
    for (const field of (interaction && interaction.fields) || []) {
      if (DISPLAY_TYPES.has(field.type)) continue;
      if (!dirty.has(field.id)) continue;
      values[field.id] = { type: field.type, value: readFieldValue(field) };
    }
    const active = document.activeElement;
    const focusId = active && active.name ? active.name : "";
    let caret = null;
    if (active && typeof active.selectionStart === "number") caret = active.selectionStart;
    return { values, focusId, caret };
  }

  function applyPreserved(data, preserved) {
    if (!preserved) return;
    for (const field of data.fields || []) {
      const saved = preserved.values[field.id];
      if (!saved || saved.type !== field.type) continue;
      writeFieldValue(field, saved.value);
    }
    if (!preserved.focusId) return;
    const target = document.querySelector(nameSelector(preserved.focusId));
    if (!target || typeof target.focus !== "function") return;
    target.focus();
    if (preserved.caret === null || typeof target.setSelectionRange !== "function") return;
    try {
      target.setSelectionRange(preserved.caret, preserved.caret);
    } catch {
      // Selection is not supported for this input type.
    }
  }

  function nameSelector(id) {
    return '[name="' + String(id).replace(/["\\]/g, "\\$&") + '"]';
  }

  // ---------------------------------------------------------- markdown

  function renderMarkdown(source, className) {
    const container = document.createElement("div");
    container.className = className || "markdown";
    container.innerHTML = markdownToHtml(source);
    return container;
  }

  function markdownToHtml(source) {
    const lines = String(source || "").replace(/\r\n/g, "\n").split("\n");
    const out = [];
    let paragraph = [];
    let list = null;
    let code = null;

    const flushParagraph = () => {
      if (paragraph.length === 0) return;
      out.push("<p>" + inlineMarkdown(paragraph.join(" ")) + "</p>");
      paragraph = [];
    };
    const flushList = () => {
      if (!list) return;
      const items = list.items.map((item) => "<li>" + inlineMarkdown(item) + "</li>").join("");
      out.push("<" + list.tag + ">" + items + "</" + list.tag + ">");
      list = null;
    };
    const flushCode = () => {
      if (!code) return;
      out.push("<pre><code>" + escapeHtml(code.join("\n")) + "</code></pre>");
      code = null;
    };

    for (const line of lines) {
      if (/^\s*```/.test(line)) {
        if (code) {
          flushCode();
        } else {
          flushParagraph();
          flushList();
          code = [];
        }
        continue;
      }
      if (code) {
        code.push(line);
        continue;
      }
      if (!line.trim()) {
        flushParagraph();
        flushList();
        continue;
      }

      const heading = line.match(/^(#{1,4})\s+(.*)$/);
      if (heading) {
        flushParagraph();
        flushList();
        const level = Math.min(heading[1].length + 1, 5);
        out.push("<h" + level + ">" + inlineMarkdown(heading[2]) + "</h" + level + ">");
        continue;
      }

      const bullet = line.match(/^\s*[-*]\s+(.*)$/);
      if (bullet) {
        flushParagraph();
        if (!list || list.tag !== "ul") {
          flushList();
          list = { tag: "ul", items: [] };
        }
        list.items.push(bullet[1]);
        continue;
      }

      const ordered = line.match(/^\s*\d+[.)]\s+(.*)$/);
      if (ordered) {
        flushParagraph();
        if (!list || list.tag !== "ol") {
          flushList();
          list = { tag: "ol", items: [] };
        }
        list.items.push(ordered[1]);
        continue;
      }

      flushList();
      paragraph.push(line.trim());
    }

    flushCode();
    flushParagraph();
    flushList();
    return out.join("");
  }

  function inlineMarkdown(text) {
    let value = escapeHtml(text);
    value = value.replace(/`([^`]+)`/g, "<code>$1</code>");
    value = value.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    value = value.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    value = value.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (match, label, href) => {
      // Unsupported scheme: keep the literal markdown rather than a mangled label.
      if (!/^(https?:|mailto:|\/)/i.test(href)) return match;
      return '<a href="' + href + '" target="_blank" rel="noreferrer noopener">' + label + "</a>";
    });
    return value;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => {
      if (character === "&") return "&amp;";
      if (character === "<") return "&lt;";
      if (character === ">") return "&gt;";
      if (character === '"') return "&quot;";
      return "&#39;";
    });
  }
})();
