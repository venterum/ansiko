import { t } from "./i18n.js";

const GRID = 0.05;
const EPS = 1e-6;
let uidCounter = 0;

function uid() {
  uidCounter += 1;
  return `c${uidCounter}`;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function snap(value) {
  return Math.round(value / GRID) * GRID;
}

function round(value) {
  return Number(value.toFixed(4));
}

function tomlString(value) {
  return `"${String(value)
    .replaceAll("\\", "\\\\")
    .replaceAll('"', '\\"')
    .replaceAll("\n", "\\n")
    .replaceAll("\r", "\\r")
    .replaceAll("\t", "\\t")}"`;
}

function overlapping(a, b) {
  return (
    a.x < b.x + b.width - EPS &&
    a.x + a.width > b.x + EPS &&
    a.y < b.y + b.height - EPS &&
    a.y + a.height > b.y + EPS
  );
}

function widgetSize(widget, frame, cols, rows) {
  const extra = frame ? 2 : 0;
  return {
    width: clamp(((widget?.width || 20) + extra) / cols, GRID, 1),
    height: clamp(((widget?.height || 5) + extra) / rows, GRID, 1),
  };
}

export function serializeModel(model) {
  const lines = [
    `name = ${tomlString(model.name || "untitled")}`,
    `frame = ${model.frame ? "true" : "false"}`,
  ];
  if (model.mode === "auto") {
    const widgets = (model.widgets || []).filter(Boolean);
    lines.push(`widgets = [${widgets.map(tomlString).join(", ")}]`);
    return `${lines.join("\n")}\n`;
  }
  for (const cell of model.cells || []) {
    lines.push(
      "",
      "[[cells]]",
      `widget = ${tomlString(cell.widget)}`,
      `x = ${round(cell.x)}`,
      `y = ${round(cell.y)}`,
      `width = ${round(cell.width)}`,
      `height = ${round(cell.height)}`,
    );
    if (typeof cell.frame === "boolean" && cell.frame !== model.frame) {
      lines.push(`frame = ${cell.frame ? "true" : "false"}`);
    }
    if (cell.align && cell.align !== "left") {
      lines.push(`align = ${tomlString(cell.align)}`);
    }
    if (cell.valign && cell.valign !== "top") {
      lines.push(`valign = ${tomlString(cell.valign)}`);
    }
  }
  return `${lines.join("\n")}\n`;
}

function normalizeModel(model, folder, preserveFrames = false) {
  const cells = (model.cells || []).map((cell) => ({
    uid: uid(),
    widget: cell.widget,
    x: clamp(Number(cell.x) || 0, 0, 1),
    y: clamp(Number(cell.y) || 0, 0, 1),
    width: clamp(Number(cell.width) || GRID, GRID, 1),
    height: clamp(Number(cell.height) || GRID, GRID, 1),
    // New source loads inherit the board frame. Payload snapshots preserve a
    // per-cell override so undo/redo does not silently lose it.
    frame: preserveFrames && typeof cell.frame === "boolean"
      ? cell.frame
      : (typeof cell.frame_override === "boolean" ? cell.frame_override : null),
    align: cell.align === "center" || cell.align === "right" ? cell.align : "left",
    valign: cell.valign === "center" || cell.valign === "bottom" ? cell.valign : "top",
  }));
  return {
    folder,
    name: String(model.name || folder),
    frame: Boolean(model.frame),
    mode: model.mode === "auto" ? "auto" : "cells",
    widgets: [...(model.widgets || [])],
    cells,
  };
}

function payloadOf(model) {
  return {
    name: model.name,
    frame: model.frame,
    mode: model.mode,
    widgets: [...model.widgets],
    cells: model.cells.map((cell) => ({
      widget: cell.widget,
      x: round(cell.x),
      y: round(cell.y),
      width: round(cell.width),
      height: round(cell.height),
      frame: typeof cell.frame === "boolean" ? cell.frame : null,
      align: cell.align || "left",
      valign: cell.valign || "top",
    })),
  };
}

function packCells(model, widgets, cols, rows) {
  const byId = new Map(widgets.map((widget) => [widget.id, widget]));
  const cells = [];
  let x = 0;
  let y = 0;
  let rowHeight = 0;
  for (const [index, id] of (model.widgets || []).entries()) {
    const widget = byId.get(id);
    const extra = model.frame ? 2 : 0;
    const fw = (widget?.width || 20) + extra;
    const fh = (widget?.height || 5) + extra;
    if (x > 0 && x + fw > cols) {
      x = 0;
      y += rowHeight + 1;
      rowHeight = 0;
    }
    cells.push({
      uid: `auto-${index}`,
      widget: id,
      x: x / cols,
      y: y / rows,
      width: Math.min(fw / cols, Math.max(GRID, 1 - x / cols)),
      height: Math.min(fh / rows, Math.max(GRID, 1 - y / rows)),
      frame: null,
      align: "left",
      valign: "top",
      offscreen: y >= rows,
    });
    x += fw + 1;
    rowHeight = Math.max(rowHeight, fh);
  }
  return cells;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "icon");
  svg.setAttribute("viewBox", "0 0 24 24");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#${name}`);
  svg.append(use);
  return svg;
}

export class BoardEditor {
  constructor(options) {
    this.options = options;
    this.widgets = [];
    this.model = null;
    this.folder = null;
    this.savedSource = "";
    this.rawSource = "";
    this.history = [];
    this.redoStack = [];
    this.selectedId = null;
    this.activeTab = "layout";
    this.sourceTimer = null;
    this._drag = null;
    this._titleBefore = null;
    this._saving = false;
    this.active = false;

    this.el = {
      view: document.getElementById("editorView"),
      back: document.getElementById("editorBack"),
      title: document.getElementById("boardTitle"),
      folder: document.getElementById("boardFolder"),
      dirty: document.getElementById("dirtyBadge"),
      undo: document.getElementById("undoBtn"),
      redo: document.getElementById("redoBtn"),
      save: document.getElementById("saveBtn"),
      push: document.getElementById("pushBtn"),
      rename: document.getElementById("renameBoard"),
      duplicate: document.getElementById("duplicateBoard"),
      delete: document.getElementById("deleteBoard"),
      tabs: [...document.querySelectorAll(".editor-tabs .tab")],
      layout: document.getElementById("layoutPane"),
      source: document.getElementById("sourcePane"),
      palette: document.getElementById("paletteList"),
      paletteCount: document.getElementById("paletteCount"),
      paletteSearch: document.getElementById("paletteSearch"),
      canvas: document.getElementById("boardCanvas"),
      canvasStage: document.getElementById("canvasStage"),
      cellLayer: document.getElementById("cellLayer"),
      canvasEmpty: document.getElementById("canvasEmpty"),
      canvasStatus: document.getElementById("canvasStatus"),
      displaySize: document.getElementById("displaySize"),
      modeSwitch: document.getElementById("modeSwitch"),
      frame: document.getElementById("frameToggle"),
      grid: document.getElementById("gridToggle"),
      quick: document.getElementById("quickLayout"),
      inspector: document.getElementById("inspectorBody"),
      clearSelection: document.getElementById("clearSelection"),
      previewStatus: document.getElementById("previewStatus"),
      alert: document.getElementById("editorAlert"),
      sourceEditor: document.getElementById("sourceEditor"),
      lineNumbers: document.getElementById("lineNumbers"),
      sourceError: document.getElementById("sourceError"),
      validate: document.getElementById("validateBtn"),
      applySource: document.getElementById("applySourceBtn"),
      saveSource: document.getElementById("saveSourceBtn"),
      previewTerminal: document.getElementById("previewTerminal"),
    };

    this._bind();
    this.setPreviewStatus("", "off");
    this._resizeObserver = new ResizeObserver(() => this.fitCanvas());
    this._resizeObserver.observe(this.el.canvasStage);
  }

  _bind() {
    this.el.back.addEventListener("click", () => this.options.onBack());
    this.el.undo.addEventListener("click", () => this.undo());
    this.el.redo.addEventListener("click", () => this.redo());
    this.el.save.addEventListener("click", () => this.save({ push: false }));
    this.el.push.addEventListener("click", () => this.save({ push: true }));
    this.el.rename.addEventListener("click", () => this.options.onRename(this.folder));
    this.el.duplicate.addEventListener("click", () => this.options.onDuplicate(this.folder));
    this.el.delete.addEventListener("click", () => this.options.onDelete(this.folder));
    this.el.tabs.forEach((tab) => tab.addEventListener("click", () => this.switchTab(tab.dataset.tab)));
    this.el.modeSwitch.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-mode]");
      if (button) this.setMode(button.dataset.mode);
    });
    this.el.frame.addEventListener("change", () => this.setFrame(this.el.frame.checked));
    this.el.grid.addEventListener("change", () => this.el.canvas.classList.toggle("show-grid", this.el.grid.checked));
    this.el.quick.addEventListener("change", () => {
      const value = this.el.quick.value;
      this.el.quick.value = "";
      if (value) this.applyQuickLayout(value);
    });
    this.el.paletteSearch.addEventListener("input", () => this.renderPalette());
    this.el.clearSelection.addEventListener("click", () => this.select(null));
    this.el.validate.addEventListener("click", () => this.validateSource({ toastSuccess: true }));
    this.el.applySource.addEventListener("click", () => this.applySource());
    this.el.saveSource.addEventListener("click", () => this.saveSource());
    this.el.sourceEditor.addEventListener("input", () => {
      this.rawSource = this.el.sourceEditor.value;
      this.sourceDirty = true;
      this.updateLineNumbers();
      this.el.sourceError.textContent = "";
      this.updateDirty();
      this.options.onPreview(this.rawSource);
      clearTimeout(this.sourceTimer);
      this.sourceTimer = setTimeout(() => this.validateSource({ quiet: true }), 500);
    });
    this.el.sourceEditor.addEventListener("scroll", () => {
      this.el.lineNumbers.scrollTop = this.el.sourceEditor.scrollTop;
    });
    this.el.sourceEditor.addEventListener("keydown", (event) => {
      if (event.key === "Tab") {
        event.preventDefault();
        const start = this.el.sourceEditor.selectionStart;
        const end = this.el.sourceEditor.selectionEnd;
        this.el.sourceEditor.setRangeText("  ", start, end, "end");
        this.el.sourceEditor.dispatchEvent(new Event("input"));
      }
    });
    this.el.title.addEventListener("focus", () => {
      this._titleBefore = payloadOf(this.model);
    });
    this.el.title.addEventListener("input", () => {
      if (!this.model) return;
      this.model.name = this.el.title.value;
      this.afterVisualChange({ skipHeader: true, skipCanvas: true });
    });
    this.el.title.addEventListener("blur", () => {
      if (!this.model || !this._titleBefore) return;
      const before = this._titleBefore;
      this._titleBefore = null;
      if (JSON.stringify(before) !== JSON.stringify(payloadOf(this.model))) {
        this.history.push(before);
        if (this.history.length > 60) this.history.shift();
        this.redoStack = [];
      }
      this.afterVisualChange();
    });
    this.el.canvas.addEventListener("dragover", (event) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
    });
    this.el.canvas.addEventListener("drop", (event) => {
      event.preventDefault();
      const id = event.dataTransfer.getData("text/plain");
      if (!id) return;
      const rect = this.el.canvas.getBoundingClientRect();
      this.addWidget(id, {
        x: (event.clientX - rect.left) / rect.width,
        y: (event.clientY - rect.top) / rect.height,
      });
    });
    window.addEventListener("keydown", (event) => this.onKeyDown(event));
    window.addEventListener("resize", () => this.fitCanvas());
  }

  load(folder, source, model = null, error = null, sourceKind = null) {
    this.folder = folder;
    this.sourceKind = sourceKind;
    this.savedSource = source;
    this.rawSource = source;
    this.model = model ? normalizeModel(model, folder) : null;
    this.invalidError = error;
    this.history = [];
    this.redoStack = [];
    this.selectedId = null;
    this.activeTab = model ? "layout" : "source";
    this.sourceDirty = false;
    this.el.sourceEditor.value = source;
    this.el.sourceError.textContent = error ? this.sourceErrorText(error) : "";
    this.updateLineNumbers();
    const bundled = sourceKind === "bundled";
    this.el.rename.classList.toggle("hidden", bundled);
    this.el.delete.classList.toggle("hidden", bundled);
    if (model) this.renderAll();
    else {
      this.renderHeader();
      this.renderPalette();
      this.renderInspector();
      this.renderSourceTab();
    }
    this.updateDirty();
    this.notifyPreview();
  }

  unload() {
    this.folder = null;
    this.sourceKind = null;
    this.model = null;
    this.selectedId = null;
    this.invalidError = null;
  }

  setWidgets(widgets) {
    this.widgets = widgets || [];
    if (this.model) {
      this.renderPalette();
      this.renderCanvas();
      this.renderInspector();
    }
  }

  setStatus(status) {
    this.status = status;
    const display = status?.display;
    if (display) {
      const changed = this.size?.cols !== display.cols || this.size?.rows !== display.rows;
      this.size = { cols: display.cols, rows: display.rows };
      this.el.displaySize.textContent = `${display.cols} × ${display.rows}`;
      if (changed) {
        this.fitCanvas();
        if (this.model?.mode === "auto") this.renderCanvas();
        this.notifyPreview();
      }
    }
    this.active = Boolean(status?.board?.active && status?.board?.name === this.folder);
    this.renderFolder();
    this.renderAlert();
  }

  renderAlert() {
    if (!this.el.alert) return;
    const errors = this.active ? (this.status?.board?.errors || []) : [];
    if (!errors.length) {
      this.el.alert.classList.add("hidden");
      this.el.alert.textContent = "";
      return;
    }
    const summary = errors.slice(0, 3).map((item) => `${item.widget}: ${item.message}`).join(" · ");
    this.el.alert.textContent = t("editor.alert", { n: errors.length, summary });
    this.el.alert.classList.remove("hidden");
  }

  setPreviewStatus(kind, text) {
    this.previewKind = kind;
    this.previewText = text;
    const keys = {
      off: "preview.off",
      connecting: "preview.connecting",
      live: "preview.live",
      reconnecting: "preview.reconnecting",
      error: "preview.error",
      "connection error": "preview.connectionError",
    };
    this.el.previewStatus.className = `preview-status ${kind || ""}`;
    this.el.previewStatus.textContent = keys[text] ? t(keys[text]) : text;
  }

  refreshPreviewStatus() {
    this.setPreviewStatus(this.previewKind || "", this.previewText || "off");
  }

  sourceErrorText(error) {
    if (!error) return "";
    const key = error.column ? "editor.sourceErrorColumn" : "editor.sourceError";
    return t(key, {
      line: error.line || "?",
      column: error.column,
      message: error.message || "",
    });
  }

  getSize() {
    return this.size || { cols: 80, rows: 24 };
  }

  widget(id) {
    return this.widgets.find((item) => item.id === id);
  }

  displayWidgetName(id) {
    return this.widget(id)?.name || id;
  }

  payload() {
    return payloadOf(this.model);
  }

  applyPayload(payload) {
    this.model = normalizeModel(
      {
        name: payload.name,
        frame: payload.frame,
        mode: payload.mode,
        widgets: payload.widgets,
        cells: payload.cells.map((cell) => ({ ...cell })),
      },
      this.folder,
      true,
    );
    this.rawSource = serializeModel(this.model);
    if (this.activeTab === "source") {
      this.el.sourceEditor.value = this.rawSource;
      this.updateLineNumbers();
    }
  }

  afterVisualChange({ skipHeader = false, skipCanvas = false } = {}) {
    this.rawSource = serializeModel(this.model);
    this.updateDirty();
    if (!skipHeader) this.renderHeader();
    if (!skipCanvas) this.renderCanvas();
    this.renderInspector();
    this.notifyPreview();
    this.fitCanvas();
  }

  commit(before) {
    if (JSON.stringify(before) !== JSON.stringify(this.payload())) {
      this.history.push(before);
      if (this.history.length > 60) this.history.shift();
      this.redoStack = [];
    }
    this.afterVisualChange();
  }

  undo() {
    if (!this.history.length) return;
    const current = this.payload();
    const previous = this.history.pop();
    this.redoStack.push(current);
    this.applyPayload(previous);
    this.selectedId = null;
    this.afterVisualChange();
  }

  redo() {
    if (!this.redoStack.length) return;
    const current = this.payload();
    const next = this.redoStack.pop();
    this.history.push(current);
    this.applyPayload(next);
    this.selectedId = null;
    this.afterVisualChange();
  }

  updateDirty() {
    const dirty = Boolean(this.folder && this.rawSource !== this.savedSource);
    this.dirty = dirty;
    this.el.dirty.classList.toggle("hidden", !dirty);
    this.el.save.disabled = this._saving || !this.canSave();
    this.el.push.disabled = this._saving || !this.model || !this.canSave();
    this.options.onDirty(dirty);
  }

  canSave() {
    if (!this.model) return Boolean(this.rawSource.trim());
    if (this.model.mode === "auto") return this.model.widgets.length > 0;
    return this.model.cells.length > 0;
  }

  renderAll() {
    this.renderHeader();
    this.renderPalette();
    this.renderCanvas();
    this.renderInspector();
    this.renderSourceTab();
    this.fitCanvas();
  }

  renderHeader() {
    if (document.activeElement !== this.el.title) {
      this.el.title.value = this.model?.name || this.folder || "";
    }
    this.el.title.disabled = !this.model;
    this.renderFolder();
    this.el.undo.disabled = !this.history.length;
    this.el.redo.disabled = !this.redoStack.length;
    this.el.modeSwitch.querySelectorAll("button").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.mode === this.model?.mode);
    });
    this.el.frame.checked = Boolean(this.model?.frame);
    this.el.save.disabled = this._saving || !this.canSave();
    this.el.push.disabled = this._saving || !this.model || !this.canSave();
    this.updateDirty();
  }

  renderFolder() {
    if (!this.folder) return;
    this.el.folder.textContent = this.active ? t("editor.onPhone", { folder: this.folder }) : this.folder;
    this.el.folder.classList.toggle("accent", this.active);
    this.el.folder.title = this.folder;
  }

  hasActiveTab(tab) {
    this.el.tabs.forEach((button) => {
      const active = button.dataset.tab === tab;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    this.el.layout.classList.toggle("hidden", tab !== "layout");
    this.el.source.classList.toggle("hidden", tab !== "source");
  }

  renderSourceTab() {
    this.hasActiveTab(this.activeTab);
    if (this.activeTab === "source") {
      this.el.sourceEditor.value = this.rawSource;
      this.updateLineNumbers();
    }
  }

  switchTab(tab) {
    if (tab === this.activeTab) return;
    if (tab === "layout" && !this.model) {
      this.options.toast(t("editor.toast.fixSource"), "error");
      return;
    }
    if (tab === "layout" && this.sourceDirty) {
      this.applySource().then((ok) => {
        if (ok) {
          this.activeTab = "layout";
          this.renderSourceTab();
          this.fitCanvas();
        }
      });
      return;
    }
    this.activeTab = tab;
    if (tab === "source") {
      this.el.sourceEditor.value = this.rawSource;
      this.sourceDirty = false;
      this.updateLineNumbers();
    }
    this.renderSourceTab();
    if (tab === "layout") this.fitCanvas();
  }

  renderPalette() {
    if (!this.el.palette) return;
    const query = (this.el.paletteSearch.value || "").trim().toLowerCase();
    const items = this.widgets.filter((widget) => {
      if (!query) return true;
      return `${widget.id} ${widget.name} ${widget.description}`.toLowerCase().includes(query);
    });
    this.el.palette.replaceChildren();
    this.el.paletteCount.textContent = String(this.widgets.length);
    if (!items.length) {
      this.el.palette.append(element("p", "hint", t("editor.palette.noMatch")));
      return;
    }
    for (const widget of items) {
      const item = element("button", "palette-item");
      item.type = "button";
      item.draggable = true;
      item.title = t("editor.palette.add", { name: widget.name });
      const glyph = element("span", "palette-glyph", widget.name.slice(0, 2).toUpperCase());
      const copy = element("span", "palette-item-copy");
      copy.append(
        element("span", "palette-item-name", widget.name),
        element("span", "palette-item-meta", t("editor.palette.meta", {
          w: widget.width,
          h: widget.height,
          interval: widget.interval,
          source: t(widget.source === "custom" ? "widgets.custom" : "widgets.bundled"),
        })),
      );
      item.append(glyph, copy, icon("i-plus"));
      item.addEventListener("click", () => this.addWidget(widget.id));
      item.addEventListener("dragstart", (event) => {
        event.dataTransfer.setData("text/plain", widget.id);
        event.dataTransfer.effectAllowed = "copy";
      });
      this.el.palette.append(item);
    }
  }

  autoCells() {
    return packCells(this.model, this.widgets, this.getSize().cols, this.getSize().rows);
  }

  currentCells() {
    return this.model.mode === "auto" ? this.autoCells() : this.model.cells;
  }

  selectedCell() {
    return this.model?.cells.find((cell) => cell.uid === this.selectedId) || null;
  }

  select(uidValue) {
    this.selectedId = uidValue;
    this.renderCanvas();
    this.renderInspector();
  }

  collision(cell) {
    if (
      cell.x < -EPS ||
      cell.y < -EPS ||
      cell.x + cell.width > 1 + EPS ||
      cell.y + cell.height > 1 + EPS
    ) return true;
    return this.model.cells.some((other) => other !== cell && overlapping(cell, other));
  }

  findFreeSpot(width, height) {
    for (let y = 0; y <= 1 - height + EPS; y += GRID) {
      for (let x = 0; x <= 1 - width + EPS; x += GRID) {
        const candidate = { x: snap(x), y: snap(y), width, height };
        if (!this.collision(candidate)) return { x: candidate.x, y: candidate.y };
      }
    }
    return null;
  }

  addWidget(id, at = null) {
    if (!this.model) return;
    if (!this.widget(id)) {
      this.options.toast(t("editor.toast.widgetMissing", { name: id }), "error");
      return;
    }
    if (this.model.mode === "auto") {
      const before = this.payload();
      this.model.widgets.push(id);
      this.commit(before);
      this.options.toast(t("editor.toast.added", { name: this.displayWidgetName(id) }), "success");
      return;
    }
    const before = this.payload();
    const widget = this.widget(id);
    const size = widgetSize(widget, this.model.frame, this.getSize().cols, this.getSize().rows);
    let spot;
    if (at) {
      spot = {
        x: snap(clamp(at.x - size.width / 2, 0, 1 - size.width)),
        y: snap(clamp(at.y - size.height / 2, 0, 1 - size.height)),
      };
      const candidate = { ...spot, ...size };
      if (this.collision(candidate)) {
        this.options.toast(t("editor.toast.occupied"), "error");
        return;
      }
    } else {
      spot = this.findFreeSpot(size.width, size.height);
      if (!spot) {
        this.options.toast(t("editor.toast.noSpace"), "error");
        return;
      }
    }
    const cell = {
      uid: uid(),
      widget: id,
      x: spot.x,
      y: spot.y,
      width: size.width,
      height: size.height,
      frame: null,
    };
    this.model.cells.push(cell);
    this.selectedId = cell.uid;
    this.commit(before);
    this.options.toast(t("editor.toast.added", { name: this.displayWidgetName(id) }), "success");
  }

  setMode(mode) {
    if (!this.model || mode === this.model.mode) return;
    if (mode === "cells") {
      const auto = this.autoCells();
      if (auto.some((cell) => cell.offscreen)) {
        this.options.toast(t("editor.toast.noFit"), "error");
        return;
      }
      const before = this.payload();
      this.model.cells = auto.map((cell) => ({
        uid: uid(),
        widget: cell.widget,
        x: cell.x,
        y: cell.y,
        width: cell.width,
        height: cell.height,
        frame: null,
      }));
      this.model.mode = "cells";
      this.model.widgets = [];
      this.selectedId = null;
      this.commit(before);
      return;
    }
    if (!this.model.cells.length) return;
    const before = this.payload();
    const ordered = [...this.model.cells].sort((a, b) => a.y - b.y || a.x - b.x);
    this.model.widgets = ordered.map((cell) => cell.widget);
    this.model.cells = [];
    this.model.mode = "auto";
    this.selectedId = null;
    this.commit(before);
  }

  setFrame(value) {
    if (!this.model || this.model.frame === value) return;
    const before = this.payload();
    this.model.frame = value;
    this.commit(before);
  }

  applyQuickLayout(kind) {
    if (!this.model) return;
    if (this.model.mode === "auto") {
      const before = this.payload();
      const auto = this.autoCells();
      if (auto.some((cell) => cell.offscreen)) {
        this.options.toast(t("editor.toast.autoNoFit"), "error");
        return;
      }
      this.model.cells = auto.map((cell) => ({
        uid: uid(),
        widget: cell.widget,
        x: cell.x,
        y: cell.y,
        width: cell.width,
        height: cell.height,
        frame: null,
      }));
      this.model.mode = "cells";
      this.model.widgets = [];
      this.selectedId = null;
      this.applyQuickLayout(kind);
      return;
    }
    const cells = this.model.cells;
    if (!cells.length) return;
    const before = this.payload();
    const count = cells.length;
    const next = cells.map((cell, index) => ({ ...cell }));
    if (kind === "columns") {
      const width = 1 / count;
      next.forEach((cell, index) => {
        cell.x = index * width;
        cell.y = 0;
        cell.width = width;
        cell.height = 1;
      });
    } else if (kind === "stack") {
      const height = 1 / count;
      next.forEach((cell, index) => {
        cell.x = 0;
        cell.y = index * height;
        cell.width = 1;
        cell.height = height;
      });
    } else {
      const columns = Math.ceil(Math.sqrt(count));
      const rows = Math.ceil(count / columns);
      const width = 1 / columns;
      const height = 1 / rows;
      next.forEach((cell, index) => {
        cell.x = (index % columns) * width;
        cell.y = Math.floor(index / columns) * height;
        cell.width = width;
        cell.height = height;
      });
    }
    this.model.cells = next;
    this.selectedId = null;
    this.commit(before);
  }

  renderCanvas() {
    if (!this.model) return;
    const cells = this.currentCells();
    this.el.cellLayer.replaceChildren();
    this.el.canvasEmpty.classList.toggle("hidden", cells.length > 0);
    this.el.canvas.classList.toggle("show-grid", this.el.grid.checked);
    const auto = this.model.mode === "auto";
    for (const cell of cells) {
      const node = element("div", "board-cell");
      node.dataset.uid = cell.uid;
      node.dataset.widget = cell.widget;
      node.style.left = `${cell.x * 100}%`;
      node.style.top = `${cell.y * 100}%`;
      node.style.width = `${cell.width * 100}%`;
      node.style.height = `${cell.height * 100}%`;
      if (auto) node.classList.add("auto-cell");
      if (cell.uid === this.selectedId) node.classList.add("selected");
      if (cell.offscreen) node.classList.add("offscreen");
      const label = element("span", "cell-label", this.displayWidgetName(cell.widget));
      const meta = element("span", "cell-meta", `${Math.round(cell.width * 100)}% × ${Math.round(cell.height * 100)}%`);
      node.append(label, meta);
      if (!auto) {
        node.addEventListener("pointerdown", (event) => this.startMove(event, cell));
        for (const handle of ["nw", "n", "ne", "e", "se", "s", "sw", "w"]) {
          const grip = element("span", "cell-resize");
          grip.dataset.handle = handle;
          grip.addEventListener("pointerdown", (event) => this.startResize(event, cell, handle));
          node.append(grip);
        }
      }
      this.el.cellLayer.append(node);
    }
    const warning = cells.some((cell) => cell.offscreen)
      ? t("editor.status.offscreen")
      : "";
    this.el.canvasStatus.textContent = auto
      ? t("editor.status.auto", { n: cells.length, extra: warning })
      : t("editor.status.free", { n: cells.length, extra: warning });
    this.fitCanvas();
  }

  updateCellVisual(cell, invalid = false) {
    const node = this.el.cellLayer.querySelector(`[data-uid="${cell.uid}"]`);
    if (!node) return;
    node.style.left = `${cell.x * 100}%`;
    node.style.top = `${cell.y * 100}%`;
    node.style.width = `${cell.width * 100}%`;
    node.style.height = `${cell.height * 100}%`;
    node.classList.toggle("invalid", invalid);
    const meta = node.querySelector(".cell-meta");
    if (meta) meta.textContent = `${Math.round(cell.width * 100)}% × ${Math.round(cell.height * 100)}%`;
  }

  startMove(event, cell) {
    if (event.button !== 0 || this.model.mode !== "cells") return;
    if (event.target.closest(".cell-resize")) return;
    event.preventDefault();
    this.select(cell.uid);
    this.beginDrag(event, cell, "move");
  }

  startResize(event, cell, handle) {
    if (event.button !== 0) return;
    event.stopPropagation();
    event.preventDefault();
    this.select(cell.uid);
    this.beginDrag(event, cell, "resize", handle);
  }

  beginDrag(event, cell, kind, handle = "") {
    const rect = this.el.canvas.getBoundingClientRect();
    this._drag = {
      kind,
      handle,
      cell,
      before: this.payload(),
      startX: event.clientX,
      startY: event.clientY,
      rect,
      orig: { x: cell.x, y: cell.y, width: cell.width, height: cell.height },
      invalid: false,
      moved: false,
    };
    this.el.cellLayer.querySelector(`[data-uid="${cell.uid}"]`)?.classList.add("dragging");
    document.body.style.cursor = kind === "move" ? "grabbing" : "nwse-resize";
    window.addEventListener("pointermove", this._onPointerMove, { passive: false });
    window.addEventListener("pointerup", this._onPointerUp, { once: true });
    window.addEventListener("pointercancel", this._onPointerUp, { once: true });
  }

  _onPointerMove = (event) => {
    const drag = this._drag;
    if (!drag) return;
    event.preventDefault();
    const dx = (event.clientX - drag.startX) / drag.rect.width;
    const dy = (event.clientY - drag.startY) / drag.rect.height;
    const cell = drag.cell;
    if (Math.abs(dx) > 0.002 || Math.abs(dy) > 0.002) drag.moved = true;
    if (drag.kind === "move") {
      cell.x = snap(clamp(drag.orig.x + dx, 0, 1 - drag.orig.width));
      cell.y = snap(clamp(drag.orig.y + dy, 0, 1 - drag.orig.height));
    } else {
      const handle = drag.handle;
      let x = drag.orig.x;
      let y = drag.orig.y;
      let width = drag.orig.width;
      let height = drag.orig.height;
      if (handle.includes("e")) width = snap(drag.orig.width + dx);
      if (handle.includes("s")) height = snap(drag.orig.height + dy);
      if (handle.includes("w")) {
        x = snap(drag.orig.x + dx);
        width = snap(drag.orig.width - dx);
        if (x < 0) { width += x; x = 0; }
      }
      if (handle.includes("n")) {
        y = snap(drag.orig.y + dy);
        height = snap(drag.orig.height - dy);
        if (y < 0) { height += y; y = 0; }
      }
      width = clamp(width, GRID, 1 - x);
      height = clamp(height, GRID, 1 - y);
      cell.x = clamp(x, 0, 1 - GRID);
      cell.y = clamp(y, 0, 1 - GRID);
      cell.width = width;
      cell.height = height;
    }
    drag.invalid = this.collision(cell);
    this.updateCellVisual(cell, drag.invalid);
    this.el.canvasStatus.textContent = drag.invalid
      ? t("editor.toast.overlap")
      : t("editor.toast.release");
  };

  _onPointerUp = () => {
    const drag = this._drag;
    if (!drag) return;
    window.removeEventListener("pointermove", this._onPointerMove);
    window.removeEventListener("pointercancel", this._onPointerUp);
    this._drag = null;
    document.body.style.cursor = "";
    this.el.cellLayer.querySelector(`[data-uid="${drag.cell.uid}"]`)?.classList.remove("dragging");
    if (drag.invalid) {
      Object.assign(drag.cell, drag.orig);
      this.options.toast(t("editor.toast.moveCancelled"), "error");
      this.renderCanvas();
      this.renderInspector();
      return;
    }
    if (!drag.moved) {
      this.renderCanvas();
      this.renderInspector();
      return;
    }
    this.commit(drag.before);
  };

  applyProp(cell, key, raw) {
    const before = this.payload();
    let value = clamp((Number(raw) || 0) / 100, 0, 1);
    if (key === "width" || key === "height") value = Math.max(GRID, value);
    if (key === "x") value = clamp(value, 0, 1 - cell.width);
    if (key === "y") value = clamp(value, 0, 1 - cell.height);
    if (key === "width") value = clamp(value, GRID, 1 - cell.x);
    if (key === "height") value = clamp(value, GRID, 1 - cell.y);
    const previous = cell[key];
    cell[key] = snap(value);
    if (this.collision(cell)) {
      cell[key] = previous;
      this.options.toast(t("editor.toast.collision"), "error");
      this.renderInspector();
      return;
    }
    this.commit(before);
  }

  nudge(cell, dx, dy) {
    const before = this.payload();
    const previous = { x: cell.x, y: cell.y };
    cell.x = snap(clamp(cell.x + dx, 0, 1 - cell.width));
    cell.y = snap(clamp(cell.y + dy, 0, 1 - cell.height));
    if (this.collision(cell)) {
      cell.x = previous.x;
      cell.y = previous.y;
      this.options.toast(t("editor.toast.nudgeCollision"), "error");
      this.renderInspector();
      return;
    }
    this.commit(before);
  }

  duplicateCell(cell) {
    const before = this.payload();
    const copy = {
      ...cell,
      uid: uid(),
      x: snap(clamp(cell.x + GRID, 0, 1 - cell.width)),
      y: snap(clamp(cell.y + GRID, 0, 1 - cell.height)),
    };
    if (this.collision(copy)) {
      const spot = this.findFreeSpot(copy.width, copy.height);
      if (!spot) {
        this.options.toast(t("editor.toast.duplicateNoSpace"), "error");
        return;
      }
      copy.x = spot.x;
      copy.y = spot.y;
    }
    this.model.cells.push(copy);
    this.selectedId = copy.uid;
    this.commit(before);
  }

  deleteSelected() {
    const cell = this.selectedCell();
    if (!cell) return;
    const before = this.payload();
    this.model.cells = this.model.cells.filter((item) => item !== cell);
    this.selectedId = null;
    this.commit(before);
  }

  renderInspector() {
    if (!this.model) {
      this.el.inspector.replaceChildren(
        element("p", "inspector-empty", this.invalidError?.message || t("editor.toast.fixSource")),
      );
      this.el.clearSelection.classList.add("hidden");
      return;
    }
    const body = this.el.inspector;
    body.replaceChildren();
    this.el.clearSelection.classList.toggle("hidden", !this.selectedId);
    if (this.model.mode === "auto") {
      body.append(
        element("p", "inspector-empty", t("editor.autoHint")),
      );
      const list = element("div", "auto-list");
      this.model.widgets.forEach((id, index) => {
        const row = element("div", "auto-item");
        const label = element("span", "", this.displayWidgetName(id));
        const up = element("button", "icon-btn", "↑");
        up.type = "button";
        up.title = t("editor.moveUp");
        up.disabled = index === 0;
        up.addEventListener("click", () => this.reorder(index, -1));
        const down = element("button", "icon-btn", "↓");
        down.type = "button";
        down.title = t("editor.moveDown");
        down.disabled = index === this.model.widgets.length - 1;
        down.addEventListener("click", () => this.reorder(index, 1));
        const remove = element("button", "icon-btn", "×");
        remove.type = "button";
        remove.title = t("editor.remove");
        remove.addEventListener("click", () => this.removeAuto(index));
        row.append(label, up, down, remove);
        list.append(row);
      });
      body.append(list);
      const convert = element("button", "btn block", t("editor.convertFree"));
      convert.type = "button";
      convert.addEventListener("click", () => this.setMode("cells"));
      body.append(convert);
      return;
    }

    const cell = this.selectedCell();
    if (!cell) {
      body.append(
        element("p", "inspector-empty", t("editor.inspectorEmpty")),
      );
      const fill = element("button", "btn block", t("editor.distribute"));
      fill.type = "button";
      fill.addEventListener("click", () => this.applyQuickLayout("grid"));
      body.append(fill);
      return;
    }

    const widget = this.widget(cell.widget);
    const identity = element("div", "inspector-widget");
    identity.append(
      element("strong", "", widget?.name || cell.widget),
      element("span", "", cell.widget),
    );
    body.append(identity);

    const grid = element("div", "prop-grid");
    for (const key of ["x", "y", "width", "height"]) {
      const field = element("label", "prop-field");
      const labelText = t(`editor.${key}`);
      field.append(element("span", "", labelText));
      const input = document.createElement("input");
      input.type = "number";
      input.min = "0";
      input.max = "100";
      input.step = "1";
      input.value = String(Math.round(cell[key] * 100));
      input.addEventListener("change", () => this.applyProp(cell, key, input.value));
      field.append(input);
      grid.append(field);
    }

    const frameField = element("label", "prop-field prop-wide");
    frameField.append(element("span", "", t("editor.frame")));
    const frameSelect = document.createElement("select");
    for (const [value, label] of [
      ["inherit", t("editor.frameInherit")],
      ["true", t("editor.frameOn")],
      ["false", t("editor.frameOff")],
    ]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      frameSelect.append(option);
    }
    frameSelect.value = typeof cell.frame === "boolean" ? String(cell.frame) : "inherit";
    frameSelect.addEventListener("change", () => {
      const before = this.payload();
      cell.frame = frameSelect.value === "inherit" ? null : frameSelect.value === "true";
      this.commit(before);
    });
    frameField.append(frameSelect);
    grid.append(frameField);

    for (const [key, title, values] of [
      ["align", "editor.align", [["left", "editor.alignLeft"], ["center", "editor.alignCenter"], ["right", "editor.alignRight"]]],
      ["valign", "editor.valign", [["top", "editor.valignTop"], ["center", "editor.valignCenter"], ["bottom", "editor.valignBottom"]]],
    ]) {
      const field = element("label", "prop-field");
      field.append(element("span", "", t(title)));
      const select = document.createElement("select");
      for (const [value, label] of values) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = t(label);
        select.append(option);
      }
      select.value = cell[key] || values[0][0];
      select.addEventListener("change", () => {
        const before = this.payload();
        cell[key] = select.value;
        this.commit(before);
      });
      field.append(select);
      grid.append(field);
    }
    body.append(grid);

    const nudge = element("div", "nudge");
    for (const [direction, label, dx, dy] of [
      ["up", "↑", 0, -GRID],
      ["left", "←", -GRID, 0],
      ["down", "↓", 0, GRID],
      ["right", "→", GRID, 0],
    ]) {
      const button = element("button", `icon-btn nudge-${direction}`, label);
      button.type = "button";
      button.title = t({ up: "editor.nudgeUp", down: "editor.nudgeDown", left: "editor.nudgeLeft", right: "editor.nudgeRight" }[direction]);
      button.addEventListener("click", () => this.nudge(cell, dx, dy));
      nudge.append(button);
    }
    body.append(nudge);

    const actions = element("div", "inspector-actions");
    const duplicate = element("button", "btn ghost", t("editor.duplicateCell"));
    duplicate.type = "button";
    duplicate.addEventListener("click", () => this.duplicateCell(cell));
    const remove = element("button", "btn danger-text", t("editor.deleteCell"));
    remove.type = "button";
    remove.addEventListener("click", () => this.deleteSelected());
    actions.append(duplicate, remove);
    body.append(actions);
  }

  reorder(index, delta) {
    const target = index + delta;
    if (target < 0 || target >= this.model.widgets.length) return;
    const before = this.payload();
    const [item] = this.model.widgets.splice(index, 1);
    this.model.widgets.splice(target, 0, item);
    this.commit(before);
  }

  removeAuto(index) {
    const before = this.payload();
    this.model.widgets.splice(index, 1);
    this.commit(before);
  }

  validateSource({ toastSuccess = false, quiet = false } = {}) {
    const source = this.el.sourceEditor.value;
    this.rawSource = source;
    return this.options.validate(source, this.folder)
      .then((model) => {
        if (!quiet) this.el.sourceError.textContent = "";
        if (toastSuccess) this.options.toast(t("editor.toast.sourceValid"), "success");
        return model;
      })
      .catch((error) => {
        this.el.sourceError.textContent = this.sourceErrorText(error);
        return null;
      });
  }

  async applySource() {
    const source = this.el.sourceEditor.value;
    this.el.sourceError.textContent = "";
    try {
      const model = await this.options.validate(source, this.folder);
      this.rawSource = source;
      this.model = normalizeModel(model, this.folder);
      this.selectedId = null;
      this.activeTab = "layout";
      this.sourceDirty = false;
      this.renderAll();
      this.updateDirty();
      this.notifyPreview();
      this.options.toast(t("editor.toast.sourceLoaded"), "success");
      return true;
    } catch (error) {
      this.el.sourceError.textContent = this.sourceErrorText(error);
      return false;
    }
  }

  async saveSource() {
    const source = this.el.sourceEditor.value;
    try {
      await this.options.validate(source, this.folder);
    } catch (error) {
      this.el.sourceError.textContent = this.sourceErrorText(error);
      this.options.toast(t("editor.toast.fixBeforeSave"), "error");
      return;
    }
    await this.save({ push: false, source });
  }

  async save({ push = false, source = null } = {}) {
    if (this._saving) return;
    if (!this.canSave()) {
      this.options.toast(t("editor.toast.addFirst"), "error");
      return;
    }
    if (push && !this.model) {
      this.options.toast(t("editor.toast.invalidPush"), "error");
      return;
    }
    let text = source ?? this.rawSource;
    if (this.activeTab === "source" && !source) text = this.el.sourceEditor.value;
    this._saving = true;
    this.updateDirty();
    try {
      await this.options.save(this.folder, text);
      this.savedSource = text;
      this.rawSource = text;
      // Source mode may have changed structure that the visual model does not
      // know about yet; force a parse before switching back to the layout.
      this.sourceDirty = this.activeTab === "source";
      this.el.sourceEditor.value = text;
      this.updateLineNumbers();
      this.el.sourceError.textContent = "";
      this.options.toast(t("editor.toast.saved"), "success");
      if (push) {
        await this.options.push(this.folder);
        this.options.toast(t("editor.toast.pushed"), "success");
        this.active = true;
        this.renderFolder();
        this.options.refreshStatus();
      }
    } catch (error) {
      this.el.sourceError.textContent = this.sourceErrorText(error);
      this.options.toast(error.message || t("editor.toast.saveFailed"), "error");
    } finally {
      this._saving = false;
      this.updateDirty();
    }
  }

  updateLineNumbers() {
    const count = this.el.sourceEditor.value.split("\n").length;
    const width = String(count).length;
    this.el.lineNumbers.style.width = `${Math.max(36, width * 9 + 18)}px`;
    this.el.lineNumbers.textContent = Array.from({ length: count }, (_, index) => String(index + 1)).join("\n");
  }

  notifyPreview() {
    if (this.model) this.options.onPreview(this.rawSource, this.getSize());
  }

  fitCanvas() {
    if (!this.el.canvas || !this.el.canvasStage) return;
    const stageWidth = this.el.canvasStage.clientWidth - 52;
    const stageHeight = Math.max(260, this.el.canvasStage.clientHeight - 52);
    if (stageWidth <= 0) return;
    const { cols, rows } = this.getSize();
    const aspect = clamp((cols * 0.62) / rows, 0.34, 2.7);
    let height = stageHeight;
    let width = height * aspect;
    if (width > stageWidth) {
      width = stageWidth;
      height = width / aspect;
    }
    this.el.canvas.style.width = `${Math.max(110, Math.round(width))}px`;
    this.el.canvas.style.height = `${Math.max(110, Math.round(height))}px`;
  }

  onKeyDown(event) {
    const tag = event.target?.tagName?.toLowerCase();
    const editing = tag === "input" || tag === "textarea" || tag === "select";
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      if (this.el.view.classList.contains("hidden")) return;
      this.save({ push: false });
      return;
    }
    if (this.activeTab === "source" && editing) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
      if (editing) return;
      event.preventDefault();
      if (event.shiftKey) this.redo();
      else this.undo();
      return;
    }
    if (event.key === "Delete" || event.key === "Backspace") {
      if (!editing && this.selectedCell()) {
        event.preventDefault();
        this.deleteSelected();
      }
    }
    if (!editing && this.selectedCell() && event.key.startsWith("Arrow")) {
      event.preventDefault();
      const step = event.shiftKey ? GRID * 5 : GRID;
      const deltas = {
        ArrowUp: [0, -step],
        ArrowDown: [0, step],
        ArrowLeft: [-step, 0],
        ArrowRight: [step, 0],
      };
      const [dx, dy] = deltas[event.key] || [0, 0];
      if (dx || dy) this.nudge(this.selectedCell(), dx, dy);
    }
    if (event.key === "Escape") {
      if (this.selectedCell()) {
        event.preventDefault();
        this.select(null);
      }
    }
  }
}
