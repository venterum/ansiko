/**
 * A small ANSI screen for the board preview.
 *
 * It intentionally supports the subset the daemon emits (cursor addressing,
 * erase, SGR colors and the common text attributes) instead of pulling a full
 * terminal emulator into the dashboard. The Android terminal remains the final
 * authority; this renderer is for composition feedback.
 */

const ESC = "\x1b";
const ANSI_16 = [
  "#000000", "#cd3131", "#0dbc79", "#e5e510", "#2472c8", "#bc3fbc", "#11a8cd", "#e5e5e5",
  "#666666", "#f14c4c", "#23d18b", "#f5f543", "#3b8eea", "#d670d6", "#29b8db", "#ffffff",
];

function palette256(index) {
  index = Math.max(0, Math.min(255, Number(index) || 0));
  if (index < 16) return ANSI_16[index];
  if (index < 232) {
    const levels = [0, 95, 135, 175, 215, 255];
    const n = index - 16;
    return `rgb(${levels[Math.floor(n / 36)]},${levels[Math.floor((n % 36) / 6)]},${levels[n % 6]})`;
  }
  const value = 8 + (index - 232) * 10;
  return `rgb(${value},${value},${value})`;
}

function rgb(r, g, b) {
  return `rgb(${Math.max(0, Math.min(255, Number(r) || 0))},${Math.max(0, Math.min(255, Number(g) || 0))},${Math.max(0, Math.min(255, Number(b) || 0))})`;
}

function charWidth(cp) {
  if (cp === 0) return 0;
  if (cp < 32) return 0;
  if (
    (cp >= 0x0300 && cp <= 0x036f) ||
    (cp >= 0x1ab0 && cp <= 0x1aff) ||
    (cp >= 0x1dc0 && cp <= 0x1dff) ||
    (cp >= 0x20d0 && cp <= 0x20ff) ||
    (cp >= 0xfe20 && cp <= 0xfe2f)
  ) return 0;
  if (
    (cp >= 0x1100 && cp <= 0x115f) ||
    (cp >= 0x2e80 && cp <= 0xa4cf) ||
    (cp >= 0xac00 && cp <= 0xd7a3) ||
    (cp >= 0xf900 && cp <= 0xfaff) ||
    (cp >= 0xfe10 && cp <= 0xfe19) ||
    (cp >= 0xfe30 && cp <= 0xfe6f) ||
    (cp >= 0xff00 && cp <= 0xff60) ||
    (cp >= 0xffe0 && cp <= 0xffe6) ||
    (cp >= 0x1f300 && cp <= 0x1faff) ||
    (cp >= 0x20000 && cp <= 0x3fffd)
  ) return 2;
  return 1;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export class AnsiTerminal {
  constructor(container) {
    this.el = container;
    this.cols = 80;
    this.rows = 24;
    this.decoder = new TextDecoder("utf-8");
    this.pending = "";
    this.raf = 0;
    this._saved = { row: 0, col: 0 };
    this.reset();
    this.fit();
    if (typeof ResizeObserver !== "undefined") {
      this._observer = new ResizeObserver(() => this.fit());
      this._observer.observe(this.el);
    }
  }

  reset() {
    this.grid = Array.from({ length: this.rows }, () =>
      Array.from({ length: this.cols }, () => this.blank()),
    );
    this.row = 0;
    this.col = 0;
    this.style = this.blankStyle();
    this.pending = "";
    this.schedule();
  }

  blankStyle() {
    return {
      fg: null,
      bg: null,
      bold: false,
      dim: false,
      italic: false,
      underline: false,
      inverse: false,
    };
  }

  blank() {
    return { ch: " ", ...this.blankStyle() };
  }

  setSize(cols, rows) {
    const nextCols = Math.max(1, Math.min(500, Number(cols) || 80));
    const nextRows = Math.max(1, Math.min(500, Number(rows) || 24));
    if (nextCols === this.cols && nextRows === this.rows) return;
    this.cols = nextCols;
    this.rows = nextRows;
    this.reset();
    this.fit();
  }

  fit() {
    if (!this.el || !this.el.clientWidth) return;
    const available = Math.max(120, this.el.clientWidth - 20);
    const size = clamp(available / this.cols / 0.62, 7, 13.5);
    this.el.style.fontSize = `${size.toFixed(2)}px`;
    this.el.style.lineHeight = "1.25";
  }

  write(data) {
    const text = typeof data === "string" ? data : this.decoder.decode(data, { stream: true });
    this.pending += text;
    let i = 0;
    const s = this.pending;
    while (i < s.length) {
      const code = s.charCodeAt(i);
      if (code === 0x1b) {
        if (i + 1 >= s.length) break;
        if (s[i + 1] === "[") {
          let j = i + 2;
          while (j < s.length && !(s[j] >= "@" && s[j] <= "~")) j += 1;
          if (j >= s.length) break;
          this.csi(s.slice(i + 2, j), s[j]);
          i = j + 1;
          continue;
        }
        if (s[i + 1] === "]") {
          let j = i + 2;
          while (j < s.length) {
            if (s[j] === "\x07") { j += 1; break; }
            if (s[j] === "\x1b" && s[j + 1] === "\\") { j += 2; break; }
            j += 1;
          }
          if (j >= s.length && !s.slice(i).endsWith("\x07") && !s.slice(i).endsWith("\x1b\\")) break;
          i = j;
          continue;
        }
        i += 2;
        continue;
      }
      if (code === 0x0a) { this.lineFeed(); i += 1; continue; }
      if (code === 0x0d) { this.col = 0; i += 1; continue; }
      if (code === 0x08) { this.col = Math.max(0, this.col - 1); i += 1; continue; }
      if (code === 0x09) {
        this.col = Math.min(this.cols - 1, (Math.floor(this.col / 8) + 1) * 8);
        i += 1;
        continue;
      }
      if (code < 0x20 || code === 0x7f) { i += 1; continue; }

      const cp = s.codePointAt(i);
      const ch = String.fromCodePoint(cp);
      const width = charWidth(cp);
      if (width === 0) {
        this.appendCombining(ch);
        i += ch.length;
        continue;
      }
      this.putChar(ch, width);
      i += ch.length;
    }
    this.pending = s.slice(i);
    this.schedule();
  }

  putChar(ch, width) {
    if (this.col >= this.cols) {
      this.col = 0;
      this.lineFeed();
    }
    const cell = this.grid[this.row][this.col];
    Object.assign(cell, this.style, { ch, continuation: false });
    if (width === 2 && this.col + 1 < this.cols) {
      const next = this.grid[this.row][this.col + 1];
      Object.assign(next, this.style, { ch: "", continuation: true });
    }
    this.col += width;
  }

  appendCombining(ch) {
    let col = this.col - 1;
    if (col < 0) return;
    if (this.grid[this.row][col]?.continuation) col -= 1;
    if (col < 0) return;
    const cell = this.grid[this.row][col];
    cell.ch += ch;
  }

  lineFeed() {
    this.row += 1;
    if (this.row < this.rows) return;
    this.grid.shift();
    this.grid.push(Array.from({ length: this.cols }, () => this.blank()));
    this.row = this.rows - 1;
  }

  scrollUp(lines = 1) {
    for (let i = 0; i < lines; i += 1) {
      this.grid.shift();
      this.grid.push(Array.from({ length: this.cols }, () => this.blank()));
    }
  }

  scrollDown(lines = 1) {
    for (let i = 0; i < lines; i += 1) {
      this.grid.pop();
      this.grid.unshift(Array.from({ length: this.cols }, () => this.blank()));
    }
  }

  csi(rawParams, final) {
    const privateMode = rawParams.startsWith("?");
    const body = privateMode ? rawParams.slice(1) : rawParams;
    const params = body === "" ? [] : body.split(";").map((part) => {
      const value = Number.parseInt(part, 10);
      return Number.isFinite(value) ? value : 0;
    });
    const first = params[0] ?? 0;
    switch (final) {
      case "H":
      case "f":
        this.row = clamp((params[0] || 1) - 1, 0, this.rows - 1);
        this.col = clamp((params[1] || 1) - 1, 0, this.cols - 1);
        break;
      case "A": this.row = clamp(this.row - (first || 1), 0, this.rows - 1); break;
      case "B": this.row = clamp(this.row + (first || 1), 0, this.rows - 1); break;
      case "C": this.col = clamp(this.col + (first || 1), 0, this.cols - 1); break;
      case "D": this.col = clamp(this.col - (first || 1), 0, this.cols - 1); break;
      case "E": this.row = clamp(this.row + (first || 1), 0, this.rows - 1); this.col = 0; break;
      case "F": this.row = clamp(this.row - (first || 1), 0, this.rows - 1); this.col = 0; break;
      case "G": this.col = clamp((first || 1) - 1, 0, this.cols - 1); break;
      case "d": this.row = clamp((first || 1) - 1, 0, this.rows - 1); break;
      case "J": this.eraseDisplay(first); break;
      case "K": this.eraseLine(first); break;
      case "m": this.sgr(params); break;
      case "s": this._saved = { row: this.row, col: this.col }; break;
      case "u": this.row = this._saved.row; this.col = this._saved.col; break;
      case "L": this.scrollDown(first || 1); break;
      case "M": this.scrollUp(first || 1); break;
      case "P": this.deleteChars(first || 1); break;
      case "@": this.insertChars(first || 1); break;
      case "S": this.scrollUp(first || 1); break;
      case "T": this.scrollDown(first || 1); break;
      default: break;
    }
  }

  eraseDisplay(mode) {
    if (mode === 2 || mode === 3) {
      for (let r = 0; r < this.rows; r += 1) {
        for (let c = 0; c < this.cols; c += 1) this.grid[r][c] = this.blank();
      }
      return;
    }
    if (mode === 1) {
      for (let r = 0; r < this.row; r += 1) {
        for (let c = 0; c < this.cols; c += 1) this.grid[r][c] = this.blank();
      }
      for (let c = 0; c <= this.col; c += 1) this.grid[this.row][c] = this.blank();
      return;
    }
    for (let c = this.col; c < this.cols; c += 1) this.grid[this.row][c] = this.blank();
    for (let r = this.row + 1; r < this.rows; r += 1) {
      for (let c = 0; c < this.cols; c += 1) this.grid[r][c] = this.blank();
    }
  }

  eraseLine(mode) {
    if (mode === 2) {
      for (let c = 0; c < this.cols; c += 1) this.grid[this.row][c] = this.blank();
      return;
    }
    if (mode === 1) {
      for (let c = 0; c <= this.col; c += 1) this.grid[this.row][c] = this.blank();
      return;
    }
    for (let c = this.col; c < this.cols; c += 1) this.grid[this.row][c] = this.blank();
  }

  deleteChars(count) {
    const row = this.grid[this.row];
    row.splice(this.col, count);
    while (row.length < this.cols) row.push(this.blank());
  }

  insertChars(count) {
    const row = this.grid[this.row];
    row.splice(this.col, 0, ...Array.from({ length: count }, () => this.blank()));
    row.length = this.cols;
  }

  sgr(params) {
    if (params.length === 0) params = [0];
    for (let i = 0; i < params.length; i += 1) {
      const code = params[i];
      if (code === 0) this.style = this.blankStyle();
      else if (code === 1) this.style.bold = true;
      else if (code === 2) this.style.dim = true;
      else if (code === 3) this.style.italic = true;
      else if (code === 4) this.style.underline = true;
      else if (code === 7) this.style.inverse = true;
      else if (code === 22) { this.style.bold = false; this.style.dim = false; }
      else if (code === 23) this.style.italic = false;
      else if (code === 24) this.style.underline = false;
      else if (code === 27) this.style.inverse = false;
      else if (code >= 30 && code <= 37) this.style.fg = ANSI_16[code - 30];
      else if (code === 39) this.style.fg = null;
      else if (code >= 40 && code <= 47) this.style.bg = ANSI_16[code - 40];
      else if (code === 49) this.style.bg = null;
      else if (code >= 90 && code <= 97) this.style.fg = ANSI_16[code - 90 + 8];
      else if (code >= 100 && code <= 107) this.style.bg = ANSI_16[code - 100 + 8];
      else if (code === 38 || code === 48) {
        const target = code === 38 ? "fg" : "bg";
        if (params[i + 1] === 5 && Number.isFinite(params[i + 2])) {
          this.style[target] = palette256(params[i + 2]);
          i += 2;
        } else if (params[i + 1] === 2 && Number.isFinite(params[i + 4])) {
          this.style[target] = rgb(params[i + 2], params[i + 3], params[i + 4]);
          i += 4;
        }
      }
    }
  }

  schedule() {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => {
      this.raf = 0;
      this.render();
    });
  }

  styleKey(cell) {
    return [
      cell.fg || "",
      cell.bg || "",
      cell.bold ? "b" : "",
      cell.dim ? "d" : "",
      cell.italic ? "i" : "",
      cell.underline ? "u" : "",
      cell.inverse ? "r" : "",
    ].join("|");
  }

  render() {
    if (!this.el) return;
    const screen = document.createElement("div");
    screen.className = "ansi-screen";
    for (let r = 0; r < this.rows; r += 1) {
      const rowEl = document.createElement("div");
      rowEl.className = "term-row";
      let run = null;
      let runKey = null;
      let text = "";
      const flush = () => {
        if (!run) return;
        run.textContent = text;
        rowEl.append(run);
        run = null;
        text = "";
      };
      for (let c = 0; c < this.cols; c += 1) {
        const cell = this.grid[r][c];
        const key = this.styleKey(cell);
        if (!run || key !== runKey) {
          flush();
          run = document.createElement("span");
          runKey = key;
          if (cell.fg) run.style.color = cell.fg;
          if (cell.bg) run.style.backgroundColor = cell.bg;
          if (cell.bold) run.style.fontWeight = "700";
          if (cell.dim) run.style.opacity = ".65";
          if (cell.italic) run.style.fontStyle = "italic";
          if (cell.underline) run.style.textDecoration = "underline";
          if (cell.inverse) {
            run.style.color = cell.bg || "#dbe7f2";
            run.style.backgroundColor = cell.fg || "#05080b";
          }
        }
        text += cell.ch;
      }
      flush();
      screen.append(rowEl);
    }
    this.el.replaceChildren(screen);
  }
}
