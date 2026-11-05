# Custom widgets

Put your own widget directories here. They are loaded together with the
bundled widgets in `widgets/`, and a custom widget with the same directory
name overrides the bundled one.

```
custom-widgets/
└── weather/
    ├── widget.toml
    └── run.py
```

The daemon looks here automatically when you run it from the repository root.
An installed tool uses `$XDG_DATA_HOME/ansiko/custom-widgets` (usually
`~/.local/share/ansiko/custom-widgets`) unless you configure another location.
Set `custom_widgets` in `ansiko.local.toml` or pass `--custom-widgets PATH` to
`ansiko serve`.

The contents of this directory are ignored by git. Keep tokens, API keys and
personal data in a local file, not in a tracked widget.

Read the [widget guide](../docs/widgets.md) for the manifest and output format.
