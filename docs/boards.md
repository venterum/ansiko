# Boards

A board is a directory under `boards/` with a `board.toml`. It selects widgets
and places them on a grid. The phone only receives the composed ANSI frame; it
does not know which widget is which.

```
boards/desk/
└── board.toml
```

## Automatic packing

The simplest board lists widget directory names in order:

```toml
name = "Desk"
frame = true
widgets = ["clock", "calendar", "sysinfo"]
```

The server places them left to right, wraps to a new row, and leaves one blank
cell between widgets and rows. `frame = true` asks the server to draw a titled
box around each cell and subtract its two columns/rows from the widget's content
area.

## Explicit cells

For a fixed composition, use fractional coordinates. Fractions survive screen
rotation and different phone sizes:

```toml
name = "Desk"
frame = true

[[cells]]
widget = "clock"
x = 0.0
y = 0.0
width = 0.55
height = 0.3

[[cells]]
widget = "calendar"
x = 0.55
y = 0.0
width = 0.45
height = 0.62
```

`x` and `y` are the top-left corner. `width` and `height` are sizes. All values
are between `0` and `1`; `x + width` and `y + height` must not exceed `1`.

A cell can override the board frame:

```toml
[[cells]]
widget = "banner"
x = 0.0
y = 0.7
width = 1.0
height = 0.3
frame = false
```

The widget's text is placed in the top-left corner by default. `align` and
`valign` move the whole output block inside the cell's content area:

```toml
[[cells]]
widget = "clock"
x = 0.0
y = 0.0
width = 1.0
height = 0.4
align = "center"   # left (default), center, right
valign = "center"  # top (default), center, bottom
```

Centering uses the visible width, so ANSI colors and wide glyphs do not
shift the block.

## Visual editor

Open a board in **Boards** and use the **Layout** tab.

- **Palette** — existing widgets. Click one to add it, or drag it onto the
  canvas (desktop).
- **Auto** — read-only packing order. Reorder widgets with the arrows, remove
  them, or press **Convert to free layout**.
- **Free** — drag cells, resize from any of the eight handles, or use the
  inspector fields. Cells snap to a 5% grid and cannot overlap.
- **Quick layout** — equal columns, a grid, or a vertical stack.
- **Inspector** — exact percentages, frame override, horizontal and vertical
  alignment, duplicate, delete and arrow-key nudge.
- **Monitor** — a temporary board streams the same ANSI frames as the
  phone. Use **Preview** or the expand icon (or press `P`) for a full-screen
  terminal; `Esc` closes it. It is not a screenshot; colors and cursor
  addressing are rendered by a small terminal view.
- **Source** — the raw TOML. Visual edits normalize formatting; comments are
  best added in Source and kept there.

**Save & push** saves the board and activates it on the connected phone. A
board can be saved without being pushed.

## Keyboard

| Shortcut | Action |
| --- | --- |
| `Ctrl`/`Cmd` + `S` | Save |
| `Ctrl`/`Cmd` + `Z` | Undo |
| `Ctrl`/`Cmd` + `Shift` + `Z` | Redo |
| `Delete` | Delete selected cell |
| `Esc` | Deselect / close dialog |
| Arrow keys | Nudge the selected cell when the inspector is not focused |

## Validation

The server parses TOML and loads each referenced widget manifest before saving.
Syntax errors report the line and column. A missing widget fails the save, so a
broken board cannot replace a working one. Saves are atomic: a crash while
writing does not leave a half-written `board.toml`.

## Bundled examples

- `boards/desk` — four explicit cells with frames.
- `boards/focus` — a single clock cell with no frame.
- `boards/minimal` — automatic packing with a banner and system info.

Copy them under a new name, or create a board from the web dashboard.
