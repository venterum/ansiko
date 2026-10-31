import { AnsiTerminal } from "./ansi.js";
import { BoardEditor } from "./editor.js";

const $ = (id) => document.getElementById(id);
const html = document.documentElement;

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
  if (!epoch) return "not saved";
  const seconds = Math.max(0, Math.round(Date.now() / 1000 - epoch));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86400)}d ago`;
}

function setUseIcon(button, name) {
  const use = button.querySelector("use");
  if (use) use.setAttribute("href", `#${name}`);
}

/* --- theme --------------------------------------------------------------- */

function setTheme(theme) {
  html.dataset.theme = theme;
  localStorage.setItem("ansiko-theme", theme);
  setUseIcon($("themeToggle"), theme === "dark" ? "i-sun" : "i-moon");
}

function initTheme() {
  const stored = localStorage.getItem("ansiko-theme");
  setTheme(stored === "light" ? "light" : "dark");
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
  closeButton.setAttribute("aria-label", "Close dialog");
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

function confirmDialog(title, message, { confirmLabel = "Confirm", danger = false } = {}) {
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
        { label: "Cancel", onClick: () => { dialog.close(); finish(false); } },
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

function promptDialog(title, description, value = "", label = "Name") {
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
        { label: "Cancel", onClick: () => { dialog.close(); finish(null); } },
        {
          label: "Continue",
          kind: "primary",
          onClick: (close) => {
            const next = input.value.trim();
            if (!next) {
              error.textContent = "Enter a name.";
              return;
            }
            if (!/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(next)) {
              error.textContent = "Use letters, numbers, dots, dashes or underscores; start with a letter or number.";
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
    if (!quiet) toast(`Status: ${error.message}`, "error");
    $("phonePill").className = "status-pill offline";
    $("phonePill").replaceChildren(node("span", "status-dot"), node("span", "", "Phone offline"));
    $("modePill").textContent = "Unknown";
  }
}

function renderStatus() {
  const status = state.status;
  if (!status) return;
  $("versionLabel").textContent = `v${status.version || "0.2.0"}`;
  const phone = $("phonePill");
  if (status.display.connected) {
    phone.className = "status-pill online";
    phone.replaceChildren(
      node("span", "status-dot"),
      node("span", "", `Phone ${status.display.cols}×${status.display.rows}`),
    );
  } else {
    phone.className = "status-pill offline";
    phone.replaceChildren(node("span", "status-dot"), node("span", "", "Phone offline"));
  }
  const mode = $("modePill");
  if (status.board.active) {
    mode.textContent = `Board · ${status.board.title || status.board.name}`;
    const errors = status.board.errors || [];
    mode.title = errors.length ? `${errors.length} widget error(s)` : "";
  } else if (status.session.running) {
    mode.textContent = "Terminal";
  } else {
    mode.textContent = "Idle";
    mode.title = "";
  }
  const activeParts = [];
  if (status.display.connected) activeParts.push(`Phone ${status.display.cols}×${status.display.rows}`);
  if (status.board.active) activeParts.push(`board “${status.board.title || status.board.name}”`);
  else if (status.session.running) activeParts.push(`terminal ${status.session.argv.join(" ")}`);
  else activeParts.push("nothing running");
  const errorCount = status.board.errors?.length || 0;
  if (errorCount) activeParts.push(`${errorCount} widget issue${errorCount === 1 ? "" : "s"}`);
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
    if (!quiet) toast(`Boards: ${error.message}`, "error");
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
    ? "No boards match this view."
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
      node("span", "chip", board.valid ? (board.mode === "auto" ? "Auto layout" : "Free layout") : "Invalid"),
      node("span", "chip", `${board.widget_count || 0} widget${board.widget_count === 1 ? "" : "s"}`),
    );
    if (board.frame) meta.append(node("span", "chip", "Framed"));
    meta.append(node("span", "chip", formatAge(board.updated)));
    if (!board.valid) meta.firstElementChild.classList.add("danger");
    card.append(meta);
    if (!board.valid && board.error) {
      card.append(node("p", "board-card-issues", board.error));
    }

    const actions = node("div", "board-card-actions");
    const open = node("button", "btn", "Open");
    open.type = "button";
    open.addEventListener("click", () => navigate(`#/board/${encodeURIComponent(board.name)}`));
    const duplicate = node("button", "icon-btn");
    duplicate.type = "button";
    duplicate.title = "Duplicate board";
    duplicate.setAttribute("aria-label", `Duplicate ${board.name}`);
    duplicate.append(svgIcon("i-copy"));
    duplicate.addEventListener("click", () => duplicateBoard(board.name));
    const remove = node("button", "icon-btn");
    remove.type = "button";
    remove.title = "Delete board";
    remove.setAttribute("aria-label", `Delete ${board.name}`);
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
    toast("Add a widget directory first, then create a board.", "error");
    navigate("#/widgets");
    return;
  }
  const content = node("div", "form-stack");
  const nameRow = node("div", "form-row");
  const nameLabel = node("label", "", "Folder name");
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
  templateRow.append(node("label", "", "Starting point"));
  const choices = node("div", "choice-grid");
  let template = "auto";
  const templates = [
    ["auto", "Auto pack", "Widgets flow in order and wrap."],
    ["columns", "Equal columns", "One column is not always the answer."],
    ["grid", "Grid", "A compact two-by-two style grid."],
    ["single", "Single widget", "One widget, all the space."],
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
  frameLabel.append(frameInput, node("span", "", "Draw a titled frame around each cell"));
  frameRow.append(frameLabel);
  content.append(frameRow);

  const widgetRow = node("div", "form-row");
  widgetRow.append(node("label", "", "Widgets"));
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
    title: "New board",
    description: "A folder under boards/ with a board.toml file.",
    content,
    wide: true,
    actions: [
      { label: "Cancel", onClick: () => dialog.close() },
      {
        label: "Create board",
        kind: "primary",
        onClick: async (close) => {
          const name = nameInput.value.trim();
          if (!/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(name)) {
            error.textContent = "Use letters, numbers, dots, dashes or underscores; start with a letter or number.";
            return;
          }
          const chosen = [...list.querySelectorAll("input:checked")].map((input) => input.value);
          if (!chosen.length) {
            error.textContent = "Select at least one widget.";
            return;
          }
          try {
            await api.post("/api/boards", { name, template, widgets: chosen, frame: frameInput.checked });
            close();
            await loadBoards();
            toast(`Created ${name}.`, "success");
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
    const ok = await confirmDialog("Discard unsaved changes?", "This board has changes that were not saved.", {
      confirmLabel: "Discard",
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
  state.view = "editor";
  $("boardsView").classList.add("hidden");
  $("widgetsView").classList.add("hidden");
  $("pairView").classList.add("hidden");
  $("helpView").classList.add("hidden");
  $("editorView").classList.remove("hidden");
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("is-active", item.dataset.view === "boards");
  });
  $("viewEyebrow").textContent = "Board editor";
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
    if (error) toast("Board has a TOML issue. Fix it in Source.", "error");
  } catch (e) {
    toast(`Could not open ${folder}: ${e.message}`, "error");
    navigate("#/boards");
  }
}

async function renameBoard(folder) {
  if (state.editorDirty) {
    toast("Save the board before renaming the folder.", "error");
    return;
  }
  const next = await promptDialog("Rename board folder", "This changes the directory name, not the board title.", folder, "Folder name");
  if (!next || next === folder) return;
  try {
    await api.post(`/api/boards/${encodeURIComponent(folder)}/rename`, { name: next });
    await loadBoards();
    toast(`Renamed to ${next}.`, "success");
    navigate(`#/board/${encodeURIComponent(next)}`);
  } catch (error) {
    toast(error.message, "error");
  }
}

async function duplicateBoard(folder) {
  const next = await promptDialog("Duplicate board", "A new folder with a copy of this board file.", `${folder}-copy`, "New folder name");
  if (!next) return;
  try {
    await api.post(`/api/boards/${encodeURIComponent(folder)}/duplicate`, { name: next });
    await loadBoards();
    toast(`Duplicated as ${next}.`, "success");
    navigate(`#/board/${encodeURIComponent(next)}`);
  } catch (error) {
    toast(error.message, "error");
  }
}

async function deleteBoard(folder) {
  const ok = await confirmDialog(
    `Delete “${folder}”?`,
    "The board folder and its board.toml will be removed. Widget directories are not touched.",
    { confirmLabel: "Delete", danger: true },
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
    toast(`Deleted ${folder}.`, "success");
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
    toast(`Widgets: ${error.message}`, "error");
  }
}

function renderWidgets() {
  const grid = $("widgetGrid");
  grid.replaceChildren();
  $("widgetsEmpty").classList.toggle("hidden", state.widgets.length > 0);
  $("widgetsNotice").classList.toggle("hidden", !state.widgetErrors.length);
  if (state.widgetErrors.length) {
    $("widgetsNotice").textContent = `${state.widgetErrors.length} manifest${state.widgetErrors.length === 1 ? "" : "s"} could not be loaded.`;
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
    head.append(copy, node("span", "chip", widget.description ? "ready" : "no description"));
    card.append(head);
    card.append(node("p", "widget-desc", widget.description || `Prints from ${widget.command}.`));
    const specs = node("div", "widget-specs");
    specs.append(
      node("span", "chip", `${widget.width}×${widget.height}`),
      node("span", "chip", `${widget.interval}s`),
      node("span", "chip", `${widget.timeout}s timeout`),
    );
    card.append(specs);
    const actions = node("div", "widget-actions");
    const use = node("button", "btn", "Use in board");
    use.type = "button";
    use.addEventListener("click", () => openCreateBoard(widget.id));
    const test = node("button", "btn ghost", "Test");
    test.type = "button";
    test.addEventListener("click", () => testWidget(widget));
    const copyPath = node("button", "icon-btn");
    copyPath.type = "button";
    copyPath.title = "Copy widget directory";
    copyPath.setAttribute("aria-label", `Copy path of ${widget.name}`);
    copyPath.append(svgIcon("i-copy"));
    copyPath.addEventListener("click", () => copyToClipboard(widget.path, "Widget path copied."));
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
  const pre = node("pre", "modal-preview", "Running…");
  content.append(pre);
  const dialog = showDialog({
    title: `Test ${widget.name}`,
    description: `${widget.command} · ${widget.width}×${widget.height}`,
    content,
    wide: true,
    actions: [{ label: "Close", onClick: () => dialog.close() }],
  });
  try {
    const size = state.status?.display || { cols: widget.width, rows: widget.height };
    const result = await api.post("/api/widgets/run", {
      name: widget.id,
      cols: size.cols,
      rows: size.rows,
    });
    pre.textContent = result.error ? `Error: ${result.error}` : (result.output || "(no output)");
    if (result.error) pre.classList.add("danger-text");
  } catch (error) {
    pre.textContent = `Error: ${error.message}`;
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
    if (local) $("pairWarning").textContent = "Open this page through the computer's LAN address, not localhost, or the QR will point the phone at itself.";
  } catch (error) {
    if (error.status !== 401) toast(`Pairing: ${error.message}`, "error");
  }
}

async function copyToClipboard(text, message = "Copied.") {
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
  await copyToClipboard($("pairUrl").textContent, "Pairing URL copied.");
}

const HELP_ARTICLES = {
  boards: `
    <p class="eyebrow">Reference</p>
    <h2>Board format</h2>
    <p>A board is a directory under <code>boards/</code> with a <code>board.toml</code>. It can use automatic packing or explicit fractional cells. Fractions survive rotation and different phone sizes.</p>
    <h3>Auto layout</h3>
    <pre>name = "desk"
frame = true
widgets = ["clock", "calendar"]</pre>
    <h3>Free layout</h3>
    <pre>name = "desk"
frame = true

[[cells]]
widget = "clock"
x = 0.0
y = 0.0
width = 0.5
height = 0.4

[[cells]]
widget = "calendar"
x = 0.5
y = 0.0
width = 0.5
height = 1.0</pre>
    <p><code>x</code>, <code>y</code>, <code>width</code> and <code>height</code> are fractions from 0 to 1. A cell may set <code>frame = false</code> to override the board frame. The widget receives its inner size in <code>ANSIKO_COLS</code> and <code>ANSIKO_ROWS</code>.</p>
    <p>In the visual editor, Free layout is draggable. Auto layout is read-only but can be converted with one click.</p>
  `,
  widgets: `
    <p class="eyebrow">Reference</p>
    <h2>Widget guide</h2>
    <p>A widget is a directory under <code>widgets/</code> with a manifest and an executable. Any language works: Python, shell, Node, a compiled binary.</p>
    <pre>widgets/clock/
├── widget.toml
└── run.py</pre>
    <pre>name        = "clock"
description = "Local time and date"
command     = "./run.py"
interval    = 1
width       = 24
height      = 5
timeout     = 2</pre>
    <p>The script prints UTF-8 text (ANSI is allowed) to stdout and exits. It receives <code>ANSIKO_COLS</code> and <code>ANSIKO_ROWS</code> for its allotted content area. A non-zero exit or timeout shows an error inside that cell only.</p>
    <h3>Rules of thumb</h3>
    <ul>
      <li>Run in well under the timeout; keep <code>interval</code> realistic.</li>
      <li>Prefer ASCII and box-drawing characters; wide emoji break the grid.</li>
      <li>Do not loop forever; the scheduler starts a fresh process each time.</li>
      <li>Read the manifest for optional <code>description</code>; it appears in the catalog.</li>
    </ul>
    <p>Scripts are trusted local code. Do not put secrets in a widget that is served from a shared machine.</p>
  `,
};

function showHelpArticle(kind) {
  const article = $("helpArticle");
  article.innerHTML = HELP_ARTICLES[kind] || "";
  article.classList.toggle("hidden", !HELP_ARTICLES[kind]);
  if (HELP_ARTICLES[kind]) article.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* --- routing and sections ------------------------------------------------ */

const VIEW_META = {
  boards: ["Workspace", "Boards"],
  widgets: ["Catalog", "Widgets"],
  pair: ["Device", "Pair phone"],
  help: ["Documentation", "Help"],
};

function showSection(name) {
  state.view = name;
  preview.stop();
  for (const id of ["boardsView", "widgetsView", "pairView", "helpView", "editorView"]) {
    $(id).classList.add("hidden");
  }
  if (name === "editor") {
    $("editorView").classList.remove("hidden");
    $("viewEyebrow").textContent = "Board editor";
    if (editor.model) $("viewTitle").textContent = editor.model.name;
  } else {
    $(`${name}View`).classList.remove("hidden");
    const [eyebrow, title] = VIEW_META[name] || ["Workspace", "Ansiko"];
    $("viewEyebrow").textContent = eyebrow;
    $("viewTitle").textContent = title;
    if (name === "boards") loadBoards({ quiet: true });
    if (name === "widgets") loadWidgets();
    if (name === "pair") loadPair();
  }
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("is-active", name === "editor" ? item.dataset.view === "boards" : item.dataset.view === name);
  });
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
        const ok = await confirmDialog("Discard unsaved changes?", "You have unsaved edits in this board.", {
          confirmLabel: "Discard",
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
  $("themeToggle").addEventListener("click", () => {
    setTheme(html.dataset.theme === "dark" ? "light" : "dark");
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
        $("loginError").textContent = response.status === 401 ? "Wrong token." : await response.text();
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
    $("showToken").textContent = input.type === "password" ? "Show" : "Hide";
  });
  $("lock").addEventListener("click", async () => {
    if (state.editorDirty) {
      const ok = await confirmDialog("Lock the dashboard?", "Unsaved edits will be lost.", {
        confirmLabel: "Lock",
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
        const ok = await confirmDialog("Discard unsaved changes?", "You have unsaved edits in this board.", {
          confirmLabel: "Discard",
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
    const ok = await confirmDialog("Stop the display?", "The phone will show the idle screen.", {
      confirmLabel: "Stop",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.post("/api/stop");
      await refreshStatus();
      toast("Display stopped.", "success");
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
    if (event.key === "Escape") closeMobileNav();
  });
}

/* --- start --------------------------------------------------------------- */

async function main() {
  initTheme();
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
