# Custom boards

Put your own board directories here. They are loaded together with the bundled
boards in `boards/`, and a custom board with the same folder name overrides the
bundled one.

```
custom-boards/
└── my-desk/
    └── board.toml
```

The web dashboard creates new boards here. Editing a bundled board also writes a
local copy here instead of touching `boards/`.

The contents of this directory are ignored by git. An installed tool uses
`$XDG_DATA_HOME/ansiko/custom-boards` (usually
`~/.local/share/ansiko/custom-boards`) unless configured otherwise. Use another
location with `custom_boards` in `ansiko.local.toml` or
`ansiko serve --custom-boards PATH`.

Read the [board guide](../docs/boards.md) for the format.
