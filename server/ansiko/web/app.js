import { AnsiTerminal } from "./ansi.js";
import { BoardEditor } from "./editor.js";
import { getLanguage, initLanguage, setLanguage, t } from "./i18n.js";

const $ = (id) => document.getElementById(id);

class ApiError extends Error {
  constructor(message, status = 0, line = null, column = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.line = line;
    this.column = column;
  }
}

const state = {
  booted: false,
  status: null,
  boards: [],
  widgets: [],
  widgetErrors: [],
  selectedFolder: null,
  editorDirty: false,
  view: "boards",
  poll: null,
  boardFilter: "all",
  boardQuery: "",
  widgetQuery: "",
};

async function request(path, options = {}) {
  const response = await fetch(path, options);
  if (response.status === 401) {
    showLogin();
    throw new ApiError("unauthorized", 401);
  }
  const type = response.headers.get("content-type") || "";
  let body = null;
  if (type.includes("application/json")) {
    body = await response.json().catch(() => null);
  } else {
    body = await response.text().catch(() => "");
  }
  if (!response.ok) {
    const message = body && typeof body === "object" && body.error
      ? body.error
      : (typeof body === "string" && body.trim()) || response.statusText;
    throw new ApiError(message, response.status, body?.line ?? null, body?.column ?? null);
  }
  return body;
}

const api = {
  get: (path) => request(path),
  post: (path, data = {}) => request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }),
  putText: (path, text) => request(path, {
    method: "PUT",
    headers: { "Content-Type": "text/plain" },
    body: text,
  }),
  del: (path) => request(path, { method: "DELETE" }),
};

function node(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = text;
  return item;
}

function svgIcon(name) {
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("class", "icon");
  icon.setAttribute("viewBox", "0 0 24 24");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#${name}`);
  icon.append(use);
  return icon;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function formatAge(epoch) {
  if (!epoch) return t("boards.notSaved");
  const seconds = Math.max(0, Math.round(Date.now() / 1000 - epoch));
  const locale = getLanguage() === "ru" ? "ru" : "en";
  const relative = new Intl.RelativeTimeFormat(locale, { numeric: "always" });
  if (seconds < 60) return t("boards.justNow");
  if (seconds < 3600) return relative.format(-Math.round(seconds / 60), "minute");
  if (seconds < 86400) return relative.format(-Math.round(seconds / 3600), "hour");
  return relative.format(-Math.round(seconds / 86400), "day");
}

/* --- toasts and dialogs -------------------------------------------------- */

function toast(message, kind = "success", timeout = 4200) {
  const item = node("div", `toast ${kind}`);
  const icon = svgIcon(kind === "error" ? "i-warn" : kind === "success" ? "i-check" : "i-help");
  item.append(icon, node("span", "", message));
  $("toasts").append(item);
  setTimeout(() => {
    item.style.opacity = "0";
    item.style.transform = "translateY(6px)";
    setTimeout(() => item.remove(), 220);
  }, timeout);
}

let activeDialog = null;

function showDialog({ title, description = "", content = null, actions = [], wide = false, onClose = null }) {
  if (activeDialog) activeDialog.close();
  const previousFocus = document.activeElement;
  const backdrop = node("div", "modal-backdrop");
  const modal = node("div", `modal${wide ? " wide" : ""}`);
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  const head = node("div", "modal-head");
  const copy = node("div");
  copy.append(node("h2", "", title));
  if (description) copy.append(node("p", "", description));
  const closeButton = node("button", "icon-btn");
  closeButton.type = "button";
  closeButton.setAttribute("aria-label", t("common.close"));
  closeButton.append(svgIcon("i-x"));
  head.append(copy, closeButton);
  const body = node("div", "modal-body");
  if (content) body.append(content);
  const footer = node("div", "modal-actions");
  modal.append(head, body);
  if (actions.length) {
    for (const action of actions) {
      const button = node("button", `btn ${action.kind || ""}`.trim());
      button.type = "button";
      button.textContent = action.label;
      if (action.disabled) button.disabled = true;
      button.addEventListener("click", async () => {
        if (!action.onClick) {
          close();
          return;
        }
        button.disabled = true;
        try {
          await action.onClick(close, modal);
        } finally {
          button.disabled = false;
        }
      });
      footer.append(button);
    }
    modal.append(footer);
  }
  backdrop.append(modal);
  document.body.append(backdrop);
  document.body.style.overflow = "hidden";
  const onKey = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    }
    if (event.key !== "Tab") return;
    const focusables = [...modal.querySelectorAll("button, input, textarea, select, a[href]")]
      .filter((item) => !item.disabled && item.offsetParent !== null);
    if (!focusables.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };
  document.addEventListener("keydown", onKey);
  const close = () => {
    if (!backdrop.isConnected) return;
    backdrop.remove();
    document.removeEventListener("keydown", onKey);
    document.body.style.overflow = "";
    activeDialog = null;
    if (onClose) onClose();
    if (previousFocus && previousFocus.focus) previousFocus.focus();
  };
  closeButton.addEventListener("click", close);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) close();
  });
  activeDialog = { close, modal };
  setTimeout(() => {
    const first = modal.querySelector("input, button, select, textarea");
    if (first) first.focus();
  }, 20);
  return activeDialog;
}

function confirmDialog(title, message, { confirmLabel = t("common.continue"), danger = false } = {}) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    const dialog = showDialog({
      title,
      description: message,
      actions: [
        { label: t("common.cancel"), onClick: () => { dialog.close(); finish(false); } },
        {
          label: confirmLabel,
          kind: danger ? "danger" : "primary",
          onClick: () => { finish(true); dialog.close(); },
        },
      ],
      onClose: () => finish(false),
    });
  });
}

function promptDialog(title, description, value = "", label = t("boards.folder")) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      resolve(result);
    };
    const content = node("div", "form-stack");
    const row = node("div", "form-row");
    const input = document.createElement("input");
    input.id = "prompt-name";
    const inputLabel = node("label", "", label);
    inputLabel.htmlFor = "prompt-name";
    row.append(inputLabel);
    input.value = value;
    input.autocomplete = "off";
    input.spellcheck = false;
    row.append(input);
    content.append(row);
    const error = node("p", "form-error");
    content.append(error);
    const dialog = showDialog({
      title,
      description,
      content,
      actions: [
        { label: t("common.cancel"), onClick: () => { dialog.close(); finish(null); } },
        {
          label: t("common.continue"),
          kind: "primary",
          onClick: (close) => {
            const next = input.value.trim();
            if (!next) {
              error.textContent = t("common.nameRequired");
              return;
            }
            if (!/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(next)) {
              error.textContent = t("boards.nameError");
              return;
            }
            finish(next);
            close();
          },
        },
      ],
      onClose: () => finish(null),
    });
    setTimeout(() => input.select(), 30);
  });
}

/* --- preview ------------------------------------------------------------- */

class PreviewController {
  constructor(container, onStatus) {
    this.terminal = new AnsiTerminal(container);
    this.onStatus = onStatus;
    this.socket = null;
    this.pending = null;
    this.timer = null;
    this.active = false;
    this.retry = null;
    this.attempt = 0;
  }

  start(source, size) {
    this.active = true;
    this.update(source, size, true);
    this.connect();
  }

  stop() {
    this.active = false;
    clearTimeout(this.timer);
    clearTimeout(this.retry);
    this.retry = null;
    this.pending = null;
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.onStatus("off", "off");
  }

  update(source, size, immediate = false) {
    if (!this.active) return;
    if (size) this.terminal.setSize(size.cols, size.rows);
    this.pending = { source, cols: size?.cols || 80, rows: size?.rows || 24 };
    clearTimeout(this.timer);
    if (immediate) this.flush();
    else this.timer = setTimeout(() => this.flush(), 260);
  }

  connect() {
    if (this.socket || !this.active) return;
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${location.host}/ws/preview`);
    socket.binaryType = "arraybuffer";
    this.socket = socket;
    this.onStatus("", "connecting");
    socket.addEventListener("open", () => {
      this.attempt = 0;
      this.flush();
    });
    socket.addEventListener("message", (event) => {
      if (event.data instanceof ArrayBuffer) {
        this.terminal.write(new Uint8Array(event.data));
        return;
      }
      const data = JSON.parse(event.data);
      if (data.type === "preview_ready") this.onStatus("live", "live");
      if (data.type === "preview_error") {
        this.onStatus("error", "error");
        if (data.error) this.onStatus("error", data.error.slice(0, 42));
      }
    });
    socket.addEventListener("close", () => {
      if (this.socket !== socket) return;
      this.socket = null;
      if (!this.active) return;
      this.onStatus("", "reconnecting");
      const delay = Math.min(8000, 800 * 2 ** this.attempt);
      this.attempt += 1;
      this.retry = setTimeout(() => this.connect(), delay);
    });
    socket.addEventListener("error", () => {
      this.onStatus("error", "connection error");
    });
  }

  flush() {
    if (!this.pending || !this.socket || this.socket.readyState !== WebSocket.OPEN) return;
    this.socket.send(JSON.stringify({
      type: "preview",
      source: this.pending.source,
      cols: this.pending.cols,
      rows: this.pending.rows,
    }));
  }
}

const preview = new PreviewController($("previewTerminal"), (kind, text) => {
  editor.setPreviewStatus(kind, text);
});

/* --- editor -------------------------------------------------------------- */

const editor = new BoardEditor({
  getWidgets: () => state.widgets,
  getSize: () => state.status?.display || { cols: 80, rows: 24 },
  validate: async (source, name) => {
    const result = await api.post("/api/boards/validate", { source, name: name || "preview" });
    return result.model;
  },
  save: async (folder, source) => {
    await api.putText(`/api/boards/${encodeURIComponent(folder)}`, source);
  },
  push: async (folder) => {
    await api.post("/api/push", { board: folder });
  },
  refreshStatus: () => refreshStatus(),
  onDirty: (dirty) => {
    state.editorDirty = dirty;
  },
  onPreview: (source, size) => {
    if (state.view === "editor") preview.update(source, size);
  },
  onBack: () => leaveEditor(),
  onRename: (folder) => renameBoard(folder),
  onDuplicate: (folder) => duplicateBoard(folder),
  onDelete: (folder) => deleteBoard(folder),
  toast,
});

/* --- boot and auth ------------------------------------------------------- */

function showLogin() {
  stopPolling();
  closeFullPreview();
  preview.stop();
  $("appView").classList.add("hidden");
  $("loginView").classList.remove("hidden");
  $("loginError").textContent = "";
  setTimeout(() => $("token").focus(), 40);
}

function showApp() {
  $("loginView").classList.add("hidden");
  $("appView").classList.remove("hidden");
}

async function boot() {
  const sessionResponse = await fetch("/api/session");
  if (!sessionResponse.ok) throw new Error(await sessionResponse.text());
  const session = await sessionResponse.json();
  if (!session.authenticated) {
    showLogin();
    return;
  }
  state.status = await api.get("/api/status");
  showApp();
  await Promise.all([loadBoards(), loadWidgets(), loadPair()]);
  state.booted = true;
  renderStatus();
  await route();
  startPolling();
}

function startPolling() {
  stopPolling();
  state.poll = setInterval(() => {
    if (!document.hidden) refreshStatus({ quiet: true });
  }, 3000);
}

function stopPolling() {
  if (state.poll) clearInterval(state.poll);
  state.poll = null;
}

async function refreshStatus({ quiet = false } = {}) {
  try {
    const status = await api.get("/api/status");
    state.status = status;
    renderStatus();
    editor.setStatus(status);
  } catch (error) {
    if (error.status === 401) return;
    if (!quiet) toast(`${t("view.workspace")}: ${error.message}`, "error");
    $("phonePill").className = "status-pill offline";
    $("phonePill").replaceChildren(node("span", "status-dot"), node("span", "", t("status.offline")));
    $("modePill").textContent = t("status.unknown");
  }
}

function renderStatus() {
  const status = state.status;
  if (!status) return;
  $("versionLabel").textContent = `v${status.version || "0.2.0"}`;
  $("statusVersion").textContent = `v${status.version || "0.2.0"}`;
  $("statusSize").textContent = `${status.display.cols} × ${status.display.rows}`;
  $("previewSize").textContent = `${status.display.cols} × ${status.display.rows}`;
  const phone = $("phonePill");
  if (status.display.connected) {
    phone.className = "status-pill online";
    phone.replaceChildren(
      node("span", "status-dot"),
      node("span", "", t("status.phone", { cols: status.display.cols, rows: status.display.rows })),
    );
  } else {
    phone.className = "status-pill offline";
    phone.replaceChildren(node("span", "status-dot"), node("span", "", t("status.offline")));
  }
  const mode = $("modePill");
  if (status.board.active) {
    mode.textContent = t("status.board", { title: status.board.title || status.board.name });
    $("statusMode").textContent = t("status.board", { title: status.board.title || status.board.name }).toUpperCase();
    const errors = status.board.errors || [];
    mode.title = errors.length ? t("status.widgetIssues", { n: errors.length }) : "";
  } else if (status.session.running) {
    mode.textContent = t("status.terminal");
    $("statusMode").textContent = t("status.terminal").toUpperCase();
  } else {
    mode.textContent = t("status.idle");
    $("statusMode").textContent = t("status.idle").toUpperCase();
    mode.title = "";
  }
  const activeParts = [];
  if (status.display.connected) activeParts.push(t("status.phone", { cols: status.display.cols, rows: status.display.rows }));
  if (status.board.active) activeParts.push(t("status.activeBoard", { title: status.board.title || status.board.name }));
  else if (status.session.running) activeParts.push(t("status.activeTerminal", { argv: status.session.argv.join(" ") }));
  else activeParts.push(t("status.activeNothing"));
  const errorCount = status.board.errors?.length || 0;
  if (errorCount) activeParts.push(t("status.widgetIssues", { n: errorCount }));
  $("activeSummary").textContent = activeParts.join(" · ");
  $("stopActive").disabled = !status.board.active && !status.session.running;
  editor.setStatus(status);
  for (const card of $("boardGrid").querySelectorAll(".board-card")) {
    card.classList.toggle("is-active", card.dataset.folder === status.board.name);
  }
}

/* --- board library ------------------------------------------------------- */

async function loadBoards({ quiet = false } = {}) {
  try {
    state.boards = await api.get("/api/boards?details=1");
    renderBoards();
  } catch (error) {
    if (error.status === 401) return;
    $("boardsError").textContent = error.message;
    if (!quiet) toast(`${t("view.boards")}: ${error.message}`, "error");
  }
}

function renderBoards() {
  const grid = $("boardGrid");
  grid.replaceChildren();
  const query = state.boardQuery.toLowerCase();
  const filtered = state.boards.filter((board) => {
    if (state.boardFilter === "valid" && !board.valid) return false;
    if (state.boardFilter === "invalid" && board.valid) return false;
    if (!query) return true;
    return `${board.name} ${board.title}`.toLowerCase().includes(query);
  });
  $("boardsEmpty").classList.toggle("hidden", state.boards.length > 0);
  $("boardsError").textContent = state.boards.length && !filtered.length
    ? t("boards.noMatches")
    : "";
  const activeName = state.status?.board?.name;
  for (const board of filtered) {
    const card = node("article", "board-card");
    card.dataset.folder = board.name;
    if (board.name === activeName) card.classList.add("is-active");
    if (!board.valid) card.classList.add("has-issue");

    const head = node("div", "board-card-head");
    const titleWrap = node("div");
    titleWrap.append(node("h3", "board-card-title", board.title || board.name));
    titleWrap.append(node("p", "board-card-folder", board.name));
    head.append(titleWrap);
    card.append(head);

    const meta = node("div", "board-card-meta");
    meta.append(
      node("span", `chip source-${board.source || "bundled"}`, t(board.source === "custom" ? "boards.custom" : "boards.bundled")),
      node("span", "chip", board.valid ? (board.mode === "auto" ? t("boards.auto") : t("boards.free")) : t("boards.invalid")),
      node("span", "chip", t("boards.widgets", { n: board.widget_count || 0 })),
    );
    if (board.frame) meta.append(node("span", "chip", t("boards.framed")));
    meta.append(node("span", "chip", formatAge(board.updated)));
    if (!board.valid) meta.firstElementChild.classList.add("danger");
    card.append(meta);
    if (!board.valid && board.error) {
      card.append(node("p", "board-card-issues", board.error));
    }

    const actions = node("div", "board-card-actions");
    const open = node("button", "btn", t("boards.open"));
    open.type = "button";
    open.addEventListener("click", () => navigate(`#/board/${encodeURIComponent(board.name)}`));
    const duplicate = node("button", "icon-btn");
    duplicate.type = "button";
    duplicate.title = t("boards.duplicate");
    duplicate.setAttribute("aria-label", t("boards.duplicate"));
    duplicate.append(svgIcon("i-copy"));
    duplicate.addEventListener("click", () => duplicateBoard(board.name));
    const remove = node("button", "icon-btn");
    remove.type = "button";
    remove.title = t("boards.delete");
    remove.setAttribute("aria-label", t("boards.delete"));
    remove.append(svgIcon("i-trash"));
    remove.addEventListener("click", () => deleteBoard(board.name));
    actions.append(open, duplicate, remove);
    card.append(actions);
    card.addEventListener("click", (event) => {
      if (event.target.closest("button")) return;
      navigate(`#/board/${encodeURIComponent(board.name)}`);
    });
    grid.append(card);
  }
}

function openCreateBoard(preferredId = null) {
  if (!state.widgets.length) {
    toast(t("widgets.empty.title"), "error");
    navigate("#/widgets");
    return;
  }
  const content = node("div", "form-stack");
  const nameRow = node("div", "form-row");
  const nameLabel = node("label", "", t("boards.folder"));
  nameLabel.htmlFor = "new-board-name";
  nameRow.append(nameLabel);
  const nameInput = document.createElement("input");
  nameInput.id = "new-board-name";
  let suffix = 1;
  let candidate = "board";
  const names = new Set(state.boards.map((board) => board.name));
  while (names.has(candidate)) {
    suffix += 1;
    candidate = `board-${suffix}`;
  }
  nameInput.value = candidate;
  nameInput.autocomplete = "off";
  nameInput.spellcheck = false;
  nameRow.append(nameInput);
  content.append(nameRow);

  const templateRow = node("div", "form-row");
  templateRow.append(node("label", "", t("boards.start")));
  const choices = node("div", "choice-grid");
  let template = "auto";
  const templates = [
    ["auto", t("boards.template.auto"), t("boards.template.autoHint")],
    ["columns", t("boards.template.columns"), t("boards.template.columnsHint")],
    ["grid", t("boards.template.grid"), t("boards.template.gridHint")],
    ["single", t("boards.template.single"), t("boards.template.singleHint")],
  ];
  const buttons = [];
  for (const [value, title, description] of templates) {
    const button = node("button", value === template ? "is-active" : "");
    button.type = "button";
    button.append(node("strong", "", title), node("span", "", description));
    button.addEventListener("click", () => {
      template = value;
      buttons.forEach((item) => item.classList.toggle("is-active", item === button));
      if (value === "single") {
        for (const input of list.querySelectorAll("input")) input.checked = false;
        const first = list.querySelector("input");
        if (first) first.checked = true;
      }
    });
    buttons.push(button);
    choices.append(button);
  }
  templateRow.append(choices);
  content.append(templateRow);

  const frameRow = node("div", "form-row");
  const frameLabel = node("label", "check-item");
  const frameInput = document.createElement("input");
  frameInput.type = "checkbox";
  frameInput.checked = true;
  frameLabel.append(frameInput, node("span", "", t("boards.frameCheckbox")));
  frameRow.append(frameLabel);
  content.append(frameRow);

  const widgetRow = node("div", "form-row");
  widgetRow.append(node("label", "", t("boards.widgetsLabel")));
  const list = node("div", "check-list");
  const selected = preferredId ? new Set([preferredId]) : new Set(state.widgets.slice(0, 3).map((widget) => widget.id));
  for (const widget of state.widgets) {
    const label = node("label", "check-item");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = widget.id;
    input.checked = selected.has(widget.id);
    const copy = node("span", "");
    copy.append(node("strong", "", widget.name), node("span", "widget-id", ` ${widget.id}`));
    label.append(input, copy);
    list.append(label);
  }
  widgetRow.append(list);
  content.append(widgetRow);
  const error = node("p", "form-error");
  content.append(error);

  const dialog = showDialog({
    title: t("boards.newTitle"),
    description: t("boards.newDesc"),
    content,
    wide: true,
    actions: [
      { label: t("common.cancel"), onClick: () => dialog.close() },
      {
        label: t("boards.create"),
        kind: "primary",
        onClick: async (close) => {
          const name = nameInput.value.trim();
          if (!/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(name)) {
            error.textContent = t("boards.nameError");
            return;
          }
          const chosen = [...list.querySelectorAll("input:checked")].map((input) => input.value);
          if (!chosen.length) {
            error.textContent = t("boards.selectWidget");
            return;
          }
          try {
            await api.post("/api/boards", { name, template, widgets: chosen, frame: frameInput.checked });
            close();
            await loadBoards();
            toast(t("boards.created", { name }), "success");
            navigate(`#/board/${encodeURIComponent(name)}`);
          } catch (e) {
            error.textContent = e.message;
          }
        },
      },
    ],
  });
}

async function leaveEditor() {
  if (state.editorDirty) {
    const ok = await confirmDialog(t("boards.discardTitle"), t("boards.discardText"), {
      confirmLabel: t("boards.discard"),
      danger: true,
    });
    if (!ok) return;
  }
  state.editorDirty = false;
  preview.stop();
  editor.unload();
  state.selectedFolder = null;
  if (location.hash === "#/boards") route();
  else navigate("#/boards");
}

function openBoardView(folder) {
  closeFullPreview();
  state.view = "editor";
  $("boardsView").classList.add("hidden");
  $("widgetsView").classList.add("hidden");
  $("pairView").classList.add("hidden");
  $("helpView").classList.add("hidden");
  $("editorView").classList.remove("hidden");
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("is-active", item.dataset.view === "boards");
  });
  $("viewEyebrow").textContent = t("view.editor");
  $("viewTitle").textContent = editor.model?.name || folder;
  document.title = `${editor.model?.name || folder} · Ansiko`;
  closeMobileNav();
}

async function openBoard(folder) {
  if (!folder) return;
  if (state.selectedFolder === folder && editor.model && !state.editorDirty) {
    openBoardView(folder);
    preview.start(editor.rawSource, editor.getSize());
    return;
  }
  try {
    const source = await api.get(`/api/boards/${encodeURIComponent(folder)}`);
    let model = null;
    let error = null;
    try {
      const result = await api.post("/api/boards/validate", { source, name: folder });
      model = result.model;
    } catch (e) {
      error = e;
    }
    state.selectedFolder = folder;
    editor.setWidgets(state.widgets);
    editor.setStatus(state.status);
    editor.load(folder, source, model, error);
    state.editorDirty = false;
    openBoardView(folder);
    $("viewTitle").textContent = editor.model?.name || folder;
    preview.start(editor.rawSource, editor.getSize());
    if (error) toast(t("editor.toast.fixSource"), "error");
  } catch (e) {
    toast(`${t("boards.open")} ${folder}: ${e.message}`, "error");
    navigate("#/boards");
  }
}

async function renameBoard(folder) {
  if (state.editorDirty) {
    toast(t("boards.saveFirst"), "error");
    return;
  }
  const next = await promptDialog(t("boards.renameTitle"), t("boards.renameDesc"), folder, t("boards.renameLabel"));
  if (!next || next === folder) return;
  try {
    await api.post(`/api/boards/${encodeURIComponent(folder)}/rename`, { name: next });
    await loadBoards();
    toast(t("boards.renamed", { name: next }), "success");
    navigate(`#/board/${encodeURIComponent(next)}`);
  } catch (error) {
    toast(error.message, "error");
  }
}

async function duplicateBoard(folder) {
  const next = await promptDialog(t("boards.duplicateTitle"), t("boards.duplicateDesc"), `${folder}-copy`, t("boards.duplicateLabel"));
  if (!next) return;
  try {
    await api.post(`/api/boards/${encodeURIComponent(folder)}/duplicate`, { name: next });
    await loadBoards();
    toast(t("boards.duplicated", { name: next }), "success");
    navigate(`#/board/${encodeURIComponent(next)}`);
  } catch (error) {
    toast(error.message, "error");
  }
}

async function deleteBoard(folder) {
  const ok = await confirmDialog(
    t("boards.deleteTitle", { name: folder }),
    t("boards.deleteText"),
    { confirmLabel: t("common.delete"), danger: true },
  );
  if (!ok) return;
  try {
    await api.del(`/api/boards/${encodeURIComponent(folder)}`);
    if (state.selectedFolder === folder) {
      state.editorDirty = false;
      preview.stop();
      editor.unload();
      state.selectedFolder = null;
      navigate("#/boards");
    }
    await loadBoards();
    toast(t("boards.deleted", { name: folder }), "success");
  } catch (error) {
    toast(error.message, "error");
  }
}

/* --- widgets ------------------------------------------------------------- */

async function loadWidgets() {
  try {
    const data = await api.get("/api/widgets");
    state.widgets = data.widgets;
    state.widgetErrors = data.errors;
    renderWidgets();
    editor.setWidgets(state.widgets);
  } catch (error) {
    if (error.status === 401) return;
    toast(`${t("view.widgets")}: ${error.message}`, "error");
  }
}

function renderWidgets() {
  const grid = $("widgetGrid");
  grid.replaceChildren();
  $("widgetsEmpty").classList.toggle("hidden", state.widgets.length > 0);
  $("widgetsNotice").classList.toggle("hidden", !state.widgetErrors.length);
  if (state.widgetErrors.length) {
    $("widgetsNotice").textContent = t("widgets.manifestErrors", { n: state.widgetErrors.length });
  }
  const query = state.widgetQuery.toLowerCase();
  const filtered = state.widgets.filter((widget) => {
    if (!query) return true;
    return `${widget.id} ${widget.name} ${widget.description}`.toLowerCase().includes(query);
  });
  for (const widget of filtered) {
    const card = node("article", "widget-card");
    const head = node("div", "widget-card-head");
    const copy = node("div");
    copy.append(node("h3", "", widget.name), node("p", "widget-id", widget.id));
    head.append(
      copy,
      node("span", `chip source-${widget.source || "bundled"}`, t(widget.source === "custom" ? "widgets.custom" : "widgets.bundled")),
    );
    card.append(head);
    card.append(node("p", "widget-desc", widget.description || `${widget.command}`));
    const specs = node("div", "widget-specs");
    specs.append(
      node("span", "chip", `${widget.width}×${widget.height}`),
      node("span", "chip", `${widget.interval}s`),
      node("span", "chip", `${widget.timeout}s`),
    );
    card.append(specs);
    const actions = node("div", "widget-actions");
    const use = node("button", "btn", t("widgets.use"));
    use.type = "button";
    use.addEventListener("click", () => openCreateBoard(widget.id));
    const test = node("button", "btn ghost", t("widgets.test"));
    test.type = "button";
    test.addEventListener("click", () => testWidget(widget));
    const copyPath = node("button", "icon-btn");
    copyPath.type = "button";
    copyPath.title = t("widgets.copyPath");
    copyPath.setAttribute("aria-label", t("widgets.copyPathAria", { name: widget.name }));
    copyPath.append(svgIcon("i-copy"));
    copyPath.addEventListener("click", () => copyToClipboard(widget.path, t("widgets.pathCopied")));
    actions.append(use, test, copyPath);
    card.append(actions);
    grid.append(card);
  }
  const errors = $("widgetErrors");
  errors.replaceChildren();
  for (const error of state.widgetErrors) {
    errors.append(node("div", "error-item", `${error.id}: ${error.error}`));
  }
}

async function testWidget(widget) {
  const content = node("div");
  const pre = node("pre", "modal-preview", t("widgets.running"));
  content.append(pre);
  const dialog = showDialog({
    title: t("widgets.testTitle", { name: widget.name }),
    description: `${widget.command} · ${widget.width}×${widget.height}`,
    content,
    wide: true,
    actions: [{ label: t("common.close"), onClick: () => dialog.close() }],
  });
  try {
    const size = state.status?.display || { cols: widget.width, rows: widget.height };
    const result = await api.post("/api/widgets/run", {
      name: widget.id,
      cols: size.cols,
      rows: size.rows,
    });
    pre.textContent = result.error ? t("widgets.error", { message: result.error }) : (result.output || t("widgets.noOutput"));
    if (result.error) pre.classList.add("danger-text");
  } catch (error) {
    pre.textContent = t("widgets.error", { message: error.message });
    pre.classList.add("danger-text");
  }
}

/* --- pairing and help ---------------------------------------------------- */

async function loadPair() {
  try {
    const pair = await api.get("/api/pair");
    $("pairUrl").textContent = pair.url;
    $("pairQr").src = `/api/pair.svg?ts=${Date.now()}`;
    const local = ["localhost", "127.0.0.1", "::1"].includes(location.hostname);
    $("pairWarning").classList.toggle("hidden", !local);
    if (local) $("pairWarning").textContent = t("pair.warning");
  } catch (error) {
    if (error.status !== 401) toast(`${t("view.pair")}: ${error.message}`, "error");
  }
}

async function copyToClipboard(text, message = t("common.copied")) {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    toast(message, "success");
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    toast(message, "success");
  }
}

async function copyPairing() {
  await copyToClipboard($("pairUrl").textContent, t("pair.copied"));
}

function showHelpArticle(kind) {
  const article = $("helpArticle");
  const content = kind ? t(`help.article.${kind}`) : "";
  article.innerHTML = content;
  article.classList.toggle("hidden", !content);
  state.helpArticle = content ? kind : null;
  if (content) article.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* --- full preview -------------------------------------------------------- */

let previewHome = null;

function openFullPreview() {
  if (state.view !== "editor" || !editor.model) return;
  const panel = document.getElementById("previewPanel");
  if (!panel || panel.classList.contains("is-fullscreen")) return;
  previewHome = { parent: panel.parentElement, next: panel.nextSibling };
  document.body.append(panel);
  document.body.classList.add("preview-open");
  $("previewScrim").classList.remove("hidden");
  panel.classList.add("is-fullscreen");
  $("expandPreview").classList.add("hidden");
  $("closePreview").classList.remove("hidden");
  setTimeout(() => preview.terminal.fit(), 40);
}

function closeFullPreview() {
  const panel = document.getElementById("previewPanel");
  document.body.classList.remove("preview-open");
  $("previewScrim").classList.add("hidden");
  if (panel) {
    panel.classList.remove("is-fullscreen");
    if (previewHome?.parent) {
      previewHome.parent.insertBefore(panel, previewHome.next);
      previewHome = null;
    }
  }
  $("expandPreview").classList.remove("hidden");
  $("closePreview").classList.add("hidden");
  setTimeout(() => preview.terminal.fit(), 40);
}

/* --- routing and sections ------------------------------------------------ */

const VIEW_META = {
  boards: ["view.workspace", "view.boards"],
  widgets: ["widgets.eyebrow", "view.widgets"],
  pair: ["pair.eyebrow", "view.pair"],
  help: ["help.eyebrow", "view.help"],
};

function showSection(name) {
  state.view = name;
  preview.stop();
  for (const id of ["boardsView", "widgetsView", "pairView", "helpView", "editorView"]) {
    $(id).classList.add("hidden");
  }
  if (name === "editor") {
    $("editorView").classList.remove("hidden");
    $("viewEyebrow").textContent = t("view.editor");
    if (editor.model) $("viewTitle").textContent = editor.model.name;
  } else {
    $(`${name}View`).classList.remove("hidden");
    const [eyebrow, title] = VIEW_META[name] || ["view.workspace", "nav.boards"];
    $("viewEyebrow").textContent = t(eyebrow);
    $("viewTitle").textContent = t(title);
    if (name === "boards") loadBoards({ quiet: true });
    if (name === "widgets") loadWidgets();
    if (name === "pair") loadPair();
  }
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("is-active", name === "editor" ? item.dataset.view === "boards" : item.dataset.view === name);
  });
  closeFullPreview();
  closeMobileNav();
  if (name === "editor" && editor.model) {
    $("viewTitle").textContent = editor.model.name;
    document.title = `${editor.model.name} · Ansiko`;
    preview.start(editor.rawSource, editor.getSize());
  } else if (name !== "editor") {
    document.title = "Ansiko";
  }
}

function navigate(hash) {
  if (location.hash === hash) {
    route();
    return;
  }
  location.hash = hash;
}

let routing = false;

async function route() {
  if (!state.booted || routing) return;
  routing = true;
  const hash = location.hash || "#/boards";
  try {
    if (state.editorDirty && state.selectedFolder) {
      const targetFolder = hash.startsWith("#/board/") ? decodeURIComponent(hash.slice(8)) : null;
      if (targetFolder !== state.selectedFolder) {
        const ok = await confirmDialog(t("boards.discardTitle"), t("boards.discardText"), {
          confirmLabel: t("boards.discard"),
          danger: true,
        });
        if (!ok) {
          history.replaceState(null, "", `#/board/${encodeURIComponent(state.selectedFolder)}`);
          return;
        }
        state.editorDirty = false;
      }
    }
    if (hash.startsWith("#/board/")) {
      const folder = decodeURIComponent(hash.slice(8));
      await openBoard(folder);
      return;
    }
    if (hash.startsWith("#/widgets")) {
      showSection("widgets");
      return;
    }
    if (hash.startsWith("#/pair")) {
      showSection("pair");
      return;
    }
    if (hash.startsWith("#/help")) {
      showSection("help");
      return;
    }
    showSection("boards");
  } finally {
    routing = false;
  }
}

function closeMobileNav() {
  document.body.classList.remove("nav-open");
  $("menuToggle").setAttribute("aria-expanded", "false");
}

/* --- events -------------------------------------------------------------- */

function bindEvents() {
  document.querySelectorAll("[data-lang-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      setLanguage(getLanguage() === "ru" ? "en" : "ru");
    });
  });
  document.addEventListener("ansiko:lang", () => {
    if (state.booted) {
      renderStatus();
      renderBoards();
      renderWidgets();
      loadPair();
    }
    if (state.view === "editor" && editor.model && state.booted) {
      $("viewEyebrow").textContent = t("view.editor");
      $("viewTitle").textContent = editor.model.name;
      document.title = `${editor.model.name} · Ansiko`;
      editor.renderAll();
      editor.refreshPreviewStatus();
    } else if (state.booted) {
      const [eyebrow, title] = VIEW_META[state.view] || ["view.workspace", "nav.boards"];
      $("viewEyebrow").textContent = t(eyebrow);
      $("viewTitle").textContent = t(title);
      document.title = "Ansiko";
    }
    if (state.helpArticle) showHelpArticle(state.helpArticle);
    $("showToken").textContent = $("token").type === "password" ? t("login.show") : t("login.hide");
  });
  $("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    $("loginError").textContent = "";
    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: $("token").value }),
      });
      if (!response.ok) {
        $("loginError").textContent = response.status === 401 ? t("login.wrong") : await response.text();
        return;
      }
      $("token").value = "";
      await boot();
    } catch (error) {
      $("loginError").textContent = error.message;
    }
  });
  $("showToken").addEventListener("click", () => {
    const input = $("token");
    input.type = input.type === "password" ? "text" : "password";
    $("showToken").textContent = input.type === "password" ? t("login.show") : t("login.hide");
  });
  $("lock").addEventListener("click", async () => {
    if (state.editorDirty) {
      const ok = await confirmDialog(t("boards.lockTitle"), t("boards.lockText"), {
        confirmLabel: t("boards.lock"),
        danger: true,
      });
      if (!ok) return;
    }
    await fetch("/api/logout", { method: "POST" });
    state.booted = false;
    state.editorDirty = false;
    showLogin();
  });
  $("menuToggle").addEventListener("click", () => {
    const open = !document.body.classList.contains("nav-open");
    document.body.classList.toggle("nav-open", open);
    $("menuToggle").setAttribute("aria-expanded", open ? "true" : "false");
  });
  $("scrim").addEventListener("click", closeMobileNav);
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", async () => {
      const target = item.dataset.view;
      if (state.view === "editor" && target === "boards") {
        await leaveEditor();
        return;
      }
      if (state.view === "editor" && state.editorDirty) {
        const ok = await confirmDialog(t("boards.discardTitle"), t("boards.discardText"), {
          confirmLabel: t("boards.discard"),
          danger: true,
        });
        if (!ok) return;
        state.editorDirty = false;
        preview.stop();
      }
      navigate(`#/${target}`);
    });
  });
  $("newBoardBtn").addEventListener("click", () => openCreateBoard());
  $("emptyNewBoard").addEventListener("click", () => openCreateBoard());
  $("refreshBoards").addEventListener("click", () => loadBoards());
  $("boardSearch").addEventListener("input", () => {
    state.boardQuery = $("boardSearch").value.trim();
    renderBoards();
  });
  $("boardFilter").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-filter]");
    if (!button) return;
    state.boardFilter = button.dataset.filter;
    $("boardFilter").querySelectorAll("button").forEach((item) => item.classList.toggle("is-active", item === button));
    renderBoards();
  });
  $("refreshWidgets").addEventListener("click", () => loadWidgets());
  $("widgetSearch").addEventListener("input", () => {
    state.widgetQuery = $("widgetSearch").value.trim();
    renderWidgets();
  });
  $("widgetGuideBtn").addEventListener("click", () => {
    navigate("#/help");
    setTimeout(() => showHelpArticle("widgets"), 0);
  });
  document.querySelectorAll("[data-open-help]").forEach((button) => {
    button.addEventListener("click", () => {
      navigate("#/help");
      setTimeout(() => showHelpArticle("widgets"), 0);
    });
  });
  document.querySelectorAll("[data-doc]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      showHelpArticle(link.dataset.doc);
    });
  });
  $("copyPair").addEventListener("click", copyPairing);
  $("stopActive").addEventListener("click", async () => {
    const ok = await confirmDialog(t("nav.stop"), t("status.offline"), {
      confirmLabel: t("nav.stop"),
      danger: true,
    });
    if (!ok) return;
    try {
      await api.post("/api/stop");
      await refreshStatus();
      toast(t("nav.stop"), "success");
    } catch (error) {
      toast(error.message, "error");
    }
  });
  window.addEventListener("hashchange", route);
  window.addEventListener("beforeunload", (event) => {
    if (!state.editorDirty) return;
    event.preventDefault();
    event.returnValue = "";
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && state.booted) refreshStatus({ quiet: true });
  });
  document.addEventListener("click", (event) => {
    if (event.target.closest(".menu")) return;
    document.querySelectorAll(".menu[open]").forEach((menu) => { menu.open = false; });
  });
  document.addEventListener("keydown", (event) => {
    const editing = ["INPUT", "TEXTAREA", "SELECT"].includes(event.target?.tagName);
    if (event.key === "Escape") {
      closeFullPreview();
      closeMobileNav();
    }
    if (!editing && event.key.toLowerCase() === "p" && state.view === "editor" && editor.model) {
      event.preventDefault();
      const panel = document.getElementById("previewPanel");
      if (panel?.classList.contains("is-fullscreen")) closeFullPreview();
      else openFullPreview();
    }
  });
  $("fullPreviewBtn").addEventListener("click", openFullPreview);
  $("expandPreview").addEventListener("click", openFullPreview);
  $("closePreview").addEventListener("click", closeFullPreview);
  $("previewScrim").addEventListener("click", closeFullPreview);
}

/* --- start --------------------------------------------------------------- */

async function main() {
  initLanguage();
  bindEvents();
  try {
    await boot();
  } catch (error) {
    if (error.status !== 401) {
      showLogin();
      $("loginError").textContent = error.message;
    }
  }
}

main();
