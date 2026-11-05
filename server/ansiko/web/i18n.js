const dictionaries = {
  en: {
    "common.cancel": "Cancel",
    "common.close": "Close",
    "common.delete": "Delete",
    "common.continue": "Continue",
    "common.open": "Open",
    "common.preview": "Preview",
    "common.test": "Test",
    "common.all": "All",
    "common.ready": "Ready",
    "common.issues": "Issues",
    "common.copied": "Copied.",
    "common.nameRequired": "Enter a name.",

    "login.eyebrow": "Read-only glass terminal",
    "login.headline": "Compose a screen.<br>Put it on the glass.",
    "login.lede": "A local control surface for boards, widgets and the phone that only displays.",
    "login.spec.ansi": "ANSI BYTES",
    "login.spec.local": "LOCAL NETWORK",
    "login.spec.noInput": "NO PHONE INPUT",
    "login.operator": "Operator access",
    "login.title": "Unlock",
    "login.tokenHint": "Enter the daemon token from <code>ansiko.local.toml</code>.",
    "login.tokenLabel": "Daemon token",
    "login.tokenPlaceholder": "token from ansiko.local.toml",
    "login.show": "Show",
    "login.hide": "Hide",
    "login.submit": "Unlock",
    "login.hint": "The token is stored in an HttpOnly cookie on this device.",
    "login.wrong": "Wrong token.",
    "login.lang": "Switch language",

    "nav.boards": "Boards",
    "nav.widgets": "Widgets",
    "nav.pair": "Pair phone",
    "nav.help": "Help",
    "nav.active": "On the phone",
    "nav.nothing": "Nothing running",
    "nav.stop": "Stop display",
    "nav.lock": "Lock dashboard",
    "nav.menu": "Open navigation",
    "nav.main": "Main navigation",

    "view.workspace": "Workspace",
    "view.boards": "Boards",
    "view.widgets": "Widgets",
    "view.pair": "Pair phone",
    "view.help": "Help",
    "view.editor": "Board editor",

    "status.checking": "Checking phone",
    "status.phone": "Phone {cols}×{rows}",
    "status.offline": "Phone offline",
    "status.idle": "Idle",
    "status.terminal": "Terminal",
    "status.board": "Board · {title}",
    "status.unknown": "Unknown",
    "status.activeBoard": "board “{title}”",
    "status.activeTerminal": "terminal {argv}",
    "status.activeNothing": "nothing running",
    "status.widgetIssues": "{n} widget issue(s)",
    "statusbar.save": "CTRL+S SAVE",
    "statusbar.undo": "CTRL+Z UNDO",
    "statusbar.label": "System status",

    "boards.eyebrow": "Library",
    "boards.title": "Board index",
    "boards.lede": "Compose on a grid, then push the frame to the glass.",
    "boards.new": "New board",
    "boards.search": "Search boards",
    "boards.all": "All",
    "boards.ready": "Ready",
    "boards.issues": "Issues",
    "boards.empty.title": "No boards yet",
    "boards.empty.text": "Start with a template and place your first widget.",
    "boards.empty.action": "Create a board",
    "boards.noMatches": "No boards match this view.",
    "boards.refresh": "Refresh boards",
    "boards.auto": "Auto layout",
    "boards.free": "Free layout",
    "boards.widgets": "Widgets: {n}",
    "boards.framed": "Framed",
    "boards.invalid": "Invalid",
    "boards.custom": "CUSTOM",
    "boards.bundled": "BUNDLED",
    "boards.onPhone": "ON PHONE",
    "boards.open": "Open",
    "boards.duplicate": "Duplicate board",
    "boards.delete": "Delete board",
    "boards.deleteTitle": "Delete “{name}”?",
    "boards.deleteText": "The board folder and its board.toml will be removed. Widget directories are not touched.",
    "boards.duplicateTitle": "Duplicate board",
    "boards.duplicateDesc": "A new folder with a copy of board.toml.",
    "boards.duplicateLabel": "New folder name",
    "boards.renameTitle": "Rename board folder",
    "boards.renameDesc": "This changes the directory name, not the board title.",
    "boards.renameLabel": "Folder name",
    "boards.newTitle": "New board",
    "boards.newDesc": "A folder under custom-boards/ with a board.toml file.",
    "boards.folder": "Folder name",
    "boards.start": "Starting point",
    "boards.template.auto": "Auto pack",
    "boards.template.autoHint": "Widgets flow in order and wrap.",
    "boards.template.columns": "Equal columns",
    "boards.template.columnsHint": "One column per widget.",
    "boards.template.grid": "Grid",
    "boards.template.gridHint": "A compact grid.",
    "boards.template.single": "Single widget",
    "boards.template.singleHint": "One widget, all the space.",
    "boards.frameCheckbox": "Draw a titled frame around each cell",
    "boards.widgetsLabel": "Widgets",
    "boards.create": "Create board",
    "boards.nameError": "Use letters, numbers, dots, dashes or underscores; start with a letter or number.",
    "boards.selectWidget": "Select at least one widget.",
    "boards.created": "Created {name}.",
    "boards.renamed": "Renamed to {name}.",
    "boards.duplicated": "Duplicated as {name}.",
    "boards.deleted": "Deleted {name}.",
    "boards.saveFirst": "Save the board before renaming the folder.",
    "boards.discardTitle": "Discard unsaved changes?",
    "boards.discardText": "You have unsaved edits in this board.",
    "boards.discard": "Discard",
    "boards.lockTitle": "Lock the dashboard?",
    "boards.lockText": "Unsaved edits will be lost.",
    "boards.lock": "Lock",
    "boards.notSaved": "not saved",
    "boards.justNow": "just now",
    "boards.minutesAgo": "{n}m ago",
    "boards.hoursAgo": "{n}h ago",
    "boards.daysAgo": "{n}d ago",

    "widgets.eyebrow": "Catalog",
    "widgets.title": "Widget directory",
    "widgets.lede": "Every executable that prints text is a candidate.",
    "widgets.guide": "Widget guide",
    "widgets.search": "Search widgets",
    "widgets.reload": "Reload widgets",
    "widgets.path": "Custom widgets live in <code>custom-widgets/</code>; bundled examples stay in <code>widgets/</code>.",
    "widgets.custom": "CUSTOM",
    "widgets.bundled": "BUNDLED",
    "widgets.use": "Use in board",
    "widgets.test": "Test",
    "widgets.copyPath": "Copy widget directory",
    "widgets.pathCopied": "Widget path copied.",
    "widgets.empty.title": "No widgets found",
    "widgets.empty.text": "Add a directory with a <code>widget.toml</code> and an executable.",
    "widgets.empty.action": "Read the widget guide",
    "widgets.manifestErrors": "{n} manifest(s) could not be loaded.",
    "widgets.testTitle": "Test {name}",
    "widgets.running": "Running…",
    "widgets.noOutput": "(no output)",
    "widgets.error": "Error: {message}",
    "widgets.copyPathAria": "Copy path of {name}",

    "pair.eyebrow": "Device",
    "pair.title": "Pair the phone",
    "pair.lede": "Scan once in the Ansiko Android app. The code contains host, port and token.",
    "pair.onPhone": "On the phone",
    "pair.step1": "Open Ansiko and long-press the terminal.",
    "pair.step2": "Tap <strong>Scan pairing QR</strong>.",
    "pair.step3": "Scan the code, then save.",
    "pair.lan": "Open this page through the computer's LAN address, not localhost, so the phone can reach it.",
    "pair.tokenNote": "The token is stored in the phone settings. Keep the dashboard on your own network.",
    "pair.copy": "Copy pairing URL",
    "pair.copied": "Pairing URL copied.",
    "pair.warning": "Open this page through the computer's LAN address, not localhost, or the QR will point the phone at itself.",
    "pair.qrAlt": "Pairing QR code",

    "help.eyebrow": "Documentation",
    "help.title": "Field guide",
    "help.lede": "The short version of the board and widget formats.",
    "help.build.title": "Build a board",
    "help.build.text": "Choose a template, add widgets from the palette, then drag and resize cells. Save and push sends the same ANSI frame the phone receives.",
    "help.build.link": "Board format →",
    "help.widget.title": "Create a widget",
    "help.widget.text": "A widget is a directory with <code>widget.toml</code> and any executable. It prints text to stdout and exits.",
    "help.widget.link": "Widget guide →",
    "help.keyboard.title": "Keyboard",
    "help.keyboard.text": "Work without the mouse.",
    "help.shortcuts.save": "Save board",
    "help.shortcuts.undo": "Undo",
    "help.shortcuts.delete": "Delete selected cell",
    "help.shortcuts.preview": "Full-screen monitor",
    "help.shortcuts.escape": "Close dialog / deselect",
    "help.security.title": "Security",
    "help.security.text": "The daemon is a remote shell. Use a long token, keep it on a trusted network, and do not expose port 8765 to the internet.",

    "editor.layout": "Layout",
    "editor.source": "Source",
    "editor.boardTitle": "Board title",
    "editor.sourceAria": "Board TOML source",
    "editor.previewAria": "Live ANSI preview",
    "editor.onPhone": "{folder} · on phone",
    "editor.preview": "Preview",
    "editor.save": "Save",
    "editor.push": "Save & push",
    "editor.unsaved": "Unsaved",
    "editor.undo": "Undo (Ctrl+Z)",
    "editor.redo": "Redo (Ctrl+Shift+Z)",
    "editor.saveTitle": "Save board",
    "editor.pushTitle": "Save and push to phone",
    "editor.previewTitle": "Full preview (P)",
    "editor.more": "More board actions",
    "editor.rename": "Rename folder",
    "editor.duplicate": "Duplicate board",
    "editor.delete": "Delete board",
    "editor.palette.title": "Widgets",
    "editor.palette.search": "Find a widget",
    "editor.palette.hint": "Click to add. On desktop, drag a widget onto the canvas to place it.",
    "editor.palette.noMatch": "No widgets match. Check the Widgets page.",
    "editor.palette.add": "Add {name}",
    "editor.palette.meta": "{w}×{h} · {interval}s · {source}",
    "editor.mode.auto": "Auto",
    "editor.mode.free": "Free",
    "editor.frame": "Frame",
    "editor.grid": "Grid",
    "editor.quick": "Quick layout",
    "editor.equalColumns": "Equal columns",
    "editor.grid2": "2 × 2 grid",
    "editor.stack": "Vertical stack",
    "editor.canvasEmpty": "Add a widget from the palette",
    "editor.inspector": "Inspector",
    "editor.clearSelection": "Clear selection",
    "editor.monitor": "Monitor",
    "editor.monitorHint": "Temporary board, same renderer as the phone.",
    "editor.inspectorEmpty": "Select a cell to change its position, size or frame. Drag from the palette to add a widget.",
    "editor.distribute": "Distribute cells in a grid",
    "editor.x": "X %",
    "editor.y": "Y %",
    "editor.width": "Width %",
    "editor.height": "Height %",
    "editor.frameInherit": "Use board setting",
    "editor.frameOn": "Frame this cell",
    "editor.frameOff": "No frame",
    "editor.align": "Horizontal align",
    "editor.alignLeft": "Left",
    "editor.alignCenter": "Center",
    "editor.alignRight": "Right",
    "editor.valign": "Vertical align",
    "editor.valignTop": "Top",
    "editor.valignCenter": "Center",
    "editor.valignBottom": "Bottom",
    "editor.duplicateCell": "Duplicate",
    "editor.deleteCell": "Delete",
    "editor.nudgeUp": "Nudge up",
    "editor.nudgeDown": "Nudge down",
    "editor.nudgeLeft": "Nudge left",
    "editor.nudgeRight": "Nudge right",
    "editor.autoHint": "Auto layout packs widgets in the order below. Drag-and-drop is available in free layout.",
    "editor.convertFree": "Convert to free layout",
    "editor.moveUp": "Move up",
    "editor.moveDown": "Move down",
    "editor.remove": "Remove",
    "editor.status.auto": "Widgets: {n} · auto layout is read-only{extra}",
    "editor.status.free": "Cells: {n} · free layout{extra}",
    "editor.status.offscreen": " · some widgets are off-screen",
    "editor.toast.widgetMissing": "Widget “{name}” is not available.",
    "editor.toast.autoNoFit": "Not enough room for the auto layout. Remove a widget first.",
    "editor.toast.overlap": "Overlaps another cell — release to cancel",
    "editor.toast.release": "Release to place",
    "editor.toast.added": "Added {name}.",
    "editor.toast.occupied": "That spot is occupied. Try another position.",
    "editor.toast.noSpace": "No free space. Resize a cell or remove a widget.",
    "editor.toast.noFit": "Those widgets do not fit the current display. Remove one or use a larger grid.",
    "editor.toast.moveCancelled": "Move cancelled: cells cannot overlap.",
    "editor.toast.collision": "That change would overlap another cell.",
    "editor.toast.nudgeCollision": "The cell would overlap another one.",
    "editor.toast.duplicateNoSpace": "No free space for a duplicate.",
    "editor.toast.fixSource": "Fix the source first, then switch to layout.",
    "editor.toast.fixBeforeSave": "Fix the source before saving.",
    "editor.toast.sourceLoaded": "Source loaded into the layout.",
    "editor.toast.sourceValid": "TOML is valid.",
    "editor.toast.saved": "Board saved.",
    "editor.toast.pushed": "Sent to the phone.",
    "editor.toast.addFirst": "Add at least one widget first.",
    "editor.toast.invalidPush": "Fix the source before pushing.",
    "editor.toast.saveFailed": "Could not save the board.",
    "editor.source.title": "Raw TOML",
    "editor.source.note": "Visual edits rewrite formatting. Comments can be edited here.",
    "editor.source.validate": "Validate",
    "editor.source.apply": "Use in layout",
    "editor.source.save": "Save source",
    "editor.alert": "{n} widget error(s): {summary}",
    "preview.off": "off",
    "preview.connecting": "connecting",
    "preview.live": "live",
    "preview.reconnecting": "reconnecting",
    "preview.error": "error",
    "preview.connectionError": "connection error",
    "editor.previewClose": "Close full preview",
    "editor.previewOpen": "Open full preview",
    "editor.sourceError": "Line {line}: {message}",
    "editor.sourceErrorColumn": "Line {line}, column {column}: {message}",

    "help.article.boards": `
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
      <p><code>x</code>, <code>y</code>, <code>width</code> and <code>height</code> are fractions from 0 to 1. A cell may set <code>frame = false</code> to override the board frame, and <code>align</code> (left/center/right) or <code>valign</code> (top/center/bottom) to put the output inside its area. The widget receives its inner size in <code>ANSIKO_COLS</code> and <code>ANSIKO_ROWS</code>.</p>
      <p>In the visual editor, Free layout is draggable. Auto layout is read-only but can be converted with one click.</p>
    `,
    "help.article.widgets": `
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
  },
  ru: {
    "common.cancel": "Отмена",
    "common.close": "Закрыть",
    "common.delete": "Удалить",
    "common.continue": "Продолжить",
    "common.open": "Открыть",
    "common.preview": "Превью",
    "common.test": "Тест",
    "common.all": "Все",
    "common.ready": "Готово",
    "common.issues": "Ошибки",
    "common.copied": "Скопировано.",
    "common.nameRequired": "Введите имя.",

    "login.eyebrow": "Терминал только для чтения",
    "login.headline": "Соберите экран.<br>Поставьте его на стекло.",
    "login.lede": "Локальная панель для досок, виджетов и телефона, который только показывает.",
    "login.spec.ansi": "ANSI-БАЙТЫ",
    "login.spec.local": "ЛОКАЛЬНАЯ СЕТЬ",
    "login.spec.noInput": "БЕЗ ВВОДА С ТЕЛЕФОНА",
    "login.operator": "Доступ оператора",
    "login.title": "Разблокировать",
    "login.tokenHint": "Введите токен демона из <code>ansiko.local.toml</code>.",
    "login.tokenLabel": "Токен демона",
    "login.tokenPlaceholder": "токен из ansiko.local.toml",
    "login.show": "Показать",
    "login.hide": "Скрыть",
    "login.submit": "Разблокировать",
    "login.hint": "Токен хранится в HttpOnly-cookie на этом устройстве.",
    "login.wrong": "Неверный токен.",
    "login.lang": "Сменить язык",

    "nav.boards": "Доски",
    "nav.widgets": "Виджеты",
    "nav.pair": "Телефон",
    "nav.help": "Справка",
    "nav.active": "На телефоне",
    "nav.nothing": "Ничего не запущено",
    "nav.stop": "Остановить",
    "nav.lock": "Заблокировать панель",
    "nav.menu": "Открыть навигацию",
    "nav.main": "Основная навигация",

    "view.workspace": "Рабочая область",
    "view.boards": "Доски",
    "view.widgets": "Виджеты",
    "view.pair": "Сопряжение",
    "view.help": "Справка",
    "view.editor": "Редактор доски",

    "status.checking": "Проверяю телефон",
    "status.phone": "Телефон {cols}×{rows}",
    "status.offline": "Телефон офлайн",
    "status.idle": "Простой",
    "status.terminal": "Терминал",
    "status.board": "Доска · {title}",
    "status.unknown": "Неизвестно",
    "status.activeBoard": "доска «{title}»",
    "status.activeTerminal": "терминал {argv}",
    "status.activeNothing": "ничего не запущено",
    "status.widgetIssues": "{n} проблема(ы) виджетов",
    "statusbar.save": "CTRL+S СОХРАНИТЬ",
    "statusbar.undo": "CTRL+Z ОТМЕНА",
    "statusbar.label": "Состояние системы",

    "boards.eyebrow": "Библиотека",
    "boards.title": "Индекс досок",
    "boards.lede": "Соберите сетку и отправьте кадр на стекло.",
    "boards.new": "Новая доска",
    "boards.search": "Поиск досок",
    "boards.all": "Все",
    "boards.ready": "Готово",
    "boards.issues": "Ошибки",
    "boards.empty.title": "Досок пока нет",
    "boards.empty.text": "Начните с шаблона и добавьте первый виджет.",
    "boards.empty.action": "Создать доску",
    "boards.noMatches": "Нет досок по этому фильтру.",
    "boards.refresh": "Обновить доски",
    "boards.auto": "Авто-раскладка",
    "boards.free": "Свободная",
    "boards.widgets": "Виджетов: {n}",
    "boards.framed": "С рамками",
    "boards.invalid": "Ошибка",
    "boards.custom": "СВОЯ",
    "boards.bundled": "ВСТРОЕННАЯ",
    "boards.onPhone": "НА ТЕЛЕФОНЕ",
    "boards.open": "Открыть",
    "boards.duplicate": "Дублировать доску",
    "boards.delete": "Удалить доску",
    "boards.deleteTitle": "Удалить «{name}»?",
    "boards.deleteText": "Папка доски и её board.toml будут удалены. Папки виджетов не затрагиваются.",
    "boards.duplicateTitle": "Дублировать доску",
    "boards.duplicateDesc": "Новая папка с копией board.toml.",
    "boards.duplicateLabel": "Имя новой папки",
    "boards.renameTitle": "Переименовать папку доски",
    "boards.renameDesc": "Меняется имя папки, а не заголовок доски.",
    "boards.renameLabel": "Имя папки",
    "boards.newTitle": "Новая доска",
    "boards.newDesc": "Папка в custom-boards/ с файлом board.toml.",
    "boards.folder": "Имя папки",
    "boards.start": "Начальная раскладка",
    "boards.template.auto": "Авто-упаковка",
    "boards.template.autoHint": "Виджеты идут по порядку и переносятся.",
    "boards.template.columns": "Равные колонки",
    "boards.template.columnsHint": "По колонке на виджет.",
    "boards.template.grid": "Сетка",
    "boards.template.gridHint": "Компактная сетка.",
    "boards.template.single": "Один виджет",
    "boards.template.singleHint": "Один виджет на всё место.",
    "boards.frameCheckbox": "Рисовать рамку с заголовком вокруг ячейки",
    "boards.widgetsLabel": "Виджеты",
    "boards.create": "Создать доску",
    "boards.nameError": "Используйте буквы, цифры, точки, дефисы или подчёркивания; начинайте с буквы или цифры.",
    "boards.selectWidget": "Выберите хотя бы один виджет.",
    "boards.created": "Создана {name}.",
    "boards.renamed": "Переименована в {name}.",
    "boards.duplicated": "Дублирована как {name}.",
    "boards.deleted": "Удалена {name}.",
    "boards.saveFirst": "Сохраните доску перед переименованием папки.",
    "boards.discardTitle": "Отменить несохранённые изменения?",
    "boards.discardText": "В этой доске есть несохранённые правки.",
    "boards.discard": "Отменить",
    "boards.lockTitle": "Заблокировать панель?",
    "boards.lockText": "Несохранённые правки будут потеряны.",
    "boards.lock": "Заблокировать",
    "boards.notSaved": "не сохранено",
    "boards.justNow": "только что",
    "boards.minutesAgo": "{n} мин назад",
    "boards.hoursAgo": "{n} ч назад",
    "boards.daysAgo": "{n} дн назад",

    "widgets.eyebrow": "Каталог",
    "widgets.title": "Каталог виджетов",
    "widgets.lede": "Любой исполняемый файл, печатающий текст, может стать виджетом.",
    "widgets.guide": "Гид по виджетам",
    "widgets.search": "Поиск виджетов",
    "widgets.reload": "Перезагрузить виджеты",
    "widgets.path": "Свои виджеты — в <code>custom-widgets/</code>; встроенные примеры — в <code>widgets/</code>.",
    "widgets.custom": "СВОЙ",
    "widgets.bundled": "ВСТРОЕННЫЙ",
    "widgets.use": "В доску",
    "widgets.test": "Тест",
    "widgets.copyPath": "Скопировать папку виджета",
    "widgets.pathCopied": "Путь к виджету скопирован.",
    "widgets.empty.title": "Виджеты не найдены",
    "widgets.empty.text": "Добавьте папку с <code>widget.toml</code> и исполняемым файлом.",
    "widgets.empty.action": "Открыть гид по виджетам",
    "widgets.manifestErrors": "{n} манифест(ов) не удалось загрузить.",
    "widgets.testTitle": "Тест {name}",
    "widgets.running": "Запуск…",
    "widgets.noOutput": "(нет вывода)",
    "widgets.error": "Ошибка: {message}",
    "widgets.copyPathAria": "Скопировать путь к {name}",

    "pair.eyebrow": "Устройство",
    "pair.title": "Сопряжение телефона",
    "pair.lede": "Отсканируйте один раз в приложении Ansiko. В коде — хост, порт и токен.",
    "pair.onPhone": "На телефоне",
    "pair.step1": "Откройте Ansiko и удерживайте терминал.",
    "pair.step2": "Нажмите <strong>Сканировать QR-код</strong>.",
    "pair.step3": "Отсканируйте код и сохраните.",
    "pair.lan": "Открывайте эту страницу по LAN-адресу компьютера, а не через localhost, иначе телефон не сможет подключиться.",
    "pair.tokenNote": "Токен хранится в настройках телефона. Держите панель в своей сети.",
    "pair.copy": "Скопировать URL сопряжения",
    "pair.copied": "URL сопряжения скопирован.",
    "pair.warning": "Откройте страницу по LAN-адресу, а не через localhost, иначе QR укажет телефону на него самого.",
    "pair.qrAlt": "QR-код сопряжения",

    "help.eyebrow": "Документация",
    "help.title": "Полевой справочник",
    "help.lede": "Коротко о форматах досок и виджетов.",
    "help.build.title": "Собрать доску",
    "help.build.text": "Выберите шаблон, добавьте виджеты из палитры, перетаскивайте и меняйте размер ячеек. «Сохранить и отправить» отправляет на телефон тот же ANSI-кадр.",
    "help.build.link": "Формат досок →",
    "help.widget.title": "Создать виджет",
    "help.widget.text": "Виджет — это папка с <code>widget.toml</code> и исполняемым файлом. Он печатает текст в stdout и завершается.",
    "help.widget.link": "Гид по виджетам →",
    "help.keyboard.title": "Клавиатура",
    "help.keyboard.text": "Работа без мыши.",
    "help.shortcuts.save": "Сохранить доску",
    "help.shortcuts.undo": "Отменить",
    "help.shortcuts.delete": "Удалить выбранную ячейку",
    "help.shortcuts.preview": "Полноэкранный монитор",
    "help.shortcuts.escape": "Закрыть диалог / снять выбор",
    "help.security.title": "Безопасность",
    "help.security.text": "Демон — это удалённый shell. Используйте длинный токен, держите его в доверенной сети и не открывайте порт 8765 в интернет.",

    "editor.layout": "Раскладка",
    "editor.source": "TOML",
    "editor.boardTitle": "Название доски",
    "editor.sourceAria": "Исходник доски в TOML",
    "editor.previewAria": "Живое ANSI-превью",
    "editor.onPhone": "{folder} · на телефоне",
    "editor.preview": "Превью",
    "editor.save": "Сохранить",
    "editor.push": "Сохранить и отправить",
    "editor.unsaved": "Не сохранено",
    "editor.undo": "Отменить (Ctrl+Z)",
    "editor.redo": "Повторить (Ctrl+Shift+Z)",
    "editor.saveTitle": "Сохранить доску",
    "editor.pushTitle": "Сохранить и отправить на телефон",
    "editor.previewTitle": "Полноэкранное превью (P)",
    "editor.more": "Другие действия с доской",
    "editor.rename": "Переименовать папку",
    "editor.duplicate": "Дублировать доску",
    "editor.delete": "Удалить доску",
    "editor.palette.title": "Виджеты",
    "editor.palette.search": "Найти виджет",
    "editor.palette.hint": "Нажмите, чтобы добавить. На компьютере виджет можно перетащить на холст.",
    "editor.palette.noMatch": "Нет подходящих виджетов. Проверьте страницу «Виджеты».",
    "editor.palette.add": "Добавить {name}",
    "editor.palette.meta": "{w}×{h} · {interval}с · {source}",
    "editor.mode.auto": "Авто",
    "editor.mode.free": "Свободно",
    "editor.frame": "Рамка",
    "editor.grid": "Сетка",
    "editor.quick": "Быстрая раскладка",
    "editor.equalColumns": "Равные колонки",
    "editor.grid2": "Сетка 2 × 2",
    "editor.stack": "Вертикальный стек",
    "editor.canvasEmpty": "Добавьте виджет из палитры",
    "editor.inspector": "Инспектор",
    "editor.clearSelection": "Снять выбор",
    "editor.monitor": "Монитор",
    "editor.monitorHint": "Временная доска, тот же рендерер, что и на телефоне.",
    "editor.inspectorEmpty": "Выберите ячейку, чтобы изменить позицию, размер или рамку. Перетащите виджет из палитры, чтобы добавить.",
    "editor.distribute": "Распределить ячейки сеткой",
    "editor.x": "X %",
    "editor.y": "Y %",
    "editor.width": "Ширина %",
    "editor.height": "Высота %",
    "editor.frameInherit": "Как у доски",
    "editor.frameOn": "Рамка ячейки",
    "editor.frameOff": "Без рамки",
    "editor.align": "Выравнивание",
    "editor.alignLeft": "Влево",
    "editor.alignCenter": "По центру",
    "editor.alignRight": "Вправо",
    "editor.valign": "По вертикали",
    "editor.valignTop": "Вверх",
    "editor.valignCenter": "По центру",
    "editor.valignBottom": "Вниз",
    "editor.duplicateCell": "Дублировать",
    "editor.deleteCell": "Удалить",
    "editor.nudgeUp": "Сдвинуть вверх",
    "editor.nudgeDown": "Сдвинуть вниз",
    "editor.nudgeLeft": "Сдвинуть влево",
    "editor.nudgeRight": "Сдвинуть вправо",
    "editor.autoHint": "Авто-раскладка упаковывает виджеты по порядку. Перетаскивание доступно в свободной раскладке.",
    "editor.convertFree": "Перевести в свободную раскладку",
    "editor.moveUp": "Выше",
    "editor.moveDown": "Ниже",
    "editor.remove": "Удалить",
    "editor.status.auto": "Виджетов: {n} · авто-раскладка только для чтения{extra}",
    "editor.status.free": "Ячеек: {n} · свободная раскладка{extra}",
    "editor.status.offscreen": " · часть виджетов за экраном",
    "editor.toast.widgetMissing": "Виджет «{name}» недоступен.",
    "editor.toast.autoNoFit": "Для авто-раскладки не хватает места. Сначала удалите виджет.",
    "editor.toast.overlap": "Пересечение с другой ячейкой — отпустите, чтобы отменить",
    "editor.toast.release": "Отпустите, чтобы разместить",
    "editor.toast.added": "Добавлен {name}.",
    "editor.toast.occupied": "Место занято. Попробуйте другое.",
    "editor.toast.noSpace": "Нет свободного места. Уменьшите ячейку или удалите виджет.",
    "editor.toast.noFit": "Эти виджеты не помещаются в текущий экран. Удалите один или увеличьте сетку.",
    "editor.toast.moveCancelled": "Перемещение отменено: ячейки не могут пересекаться.",
    "editor.toast.collision": "Изменение пересечёт другую ячейку.",
    "editor.toast.nudgeCollision": "Ячейка пересечёт другую.",
    "editor.toast.duplicateNoSpace": "Нет места для дубликата.",
    "editor.toast.fixSource": "Сначала исправьте TOML, затем переключитесь в раскладку.",
    "editor.toast.fixBeforeSave": "Исправьте TOML перед сохранением.",
    "editor.toast.sourceLoaded": "TOML загружен в раскладку.",
    "editor.toast.sourceValid": "TOML корректен.",
    "editor.toast.saved": "Доска сохранена.",
    "editor.toast.pushed": "Отправлено на телефон.",
    "editor.toast.addFirst": "Сначала добавьте хотя бы один виджет.",
    "editor.toast.invalidPush": "Исправьте TOML перед отправкой.",
    "editor.toast.saveFailed": "Не удалось сохранить доску.",
    "editor.source.title": "Сырой TOML",
    "editor.source.note": "Визуальные правки переформатируют файл; комментарии можно править здесь.",
    "editor.source.validate": "Проверить",
    "editor.source.apply": "В раскладку",
    "editor.source.save": "Сохранить TOML",
    "editor.alert": "{n} ошибка(и) виджетов: {summary}",
    "preview.off": "выкл",
    "preview.connecting": "подключение",
    "preview.live": "онлайн",
    "preview.reconnecting": "переподключение",
    "preview.error": "ошибка",
    "preview.connectionError": "ошибка подключения",
    "editor.previewClose": "Закрыть полноэкранный монитор",
    "editor.previewOpen": "Открыть полноэкранный монитор",
    "editor.sourceError": "Строка {line}: {message}",
    "editor.sourceErrorColumn": "Строка {line}, колонка {column}: {message}",

    "help.article.boards": `
      <p class="eyebrow">Справка</p>
      <h2>Формат доски</h2>
      <p>Доска — это папка в <code>boards/</code> с файлом <code>board.toml</code>. Она может использовать автоматическую упаковку или явные дробные ячейки. Дроби сохраняются при повороте и разных размерах телефона.</p>
      <h3>Авто-раскладка</h3>
      <pre>name = "desk"
frame = true
widgets = ["clock", "calendar"]</pre>
      <h3>Свободная раскладка</h3>
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
      <p><code>x</code>, <code>y</code>, <code>width</code> и <code>height</code> — дроби от 0 до 1. Ячейка может задать <code>frame = false</code>, чтобы отменить рамку доски, а также <code>align</code> (left/center/right) или <code>valign</code> (top/center/bottom), чтобы разместить вывод внутри области. Виджет получает внутренний размер в <code>ANSIKO_COLS</code> и <code>ANSIKO_ROWS</code>.</p>
      <p>В визуальном редакторе свободная раскладка перетаскивается. Авто-раскладка только для чтения, но переводится в свободную одним нажатием.</p>
    `,
    "help.article.widgets": `
      <p class="eyebrow">Справка</p>
      <h2>Гид по виджетам</h2>
      <p>Виджет — это папка в <code>widgets/</code> с манифестом и исполняемым файлом. Подходит любой язык: Python, shell, Node, скомпилированный бинарник.</p>
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
      <p>Скрипт печатает UTF-8 (ANSI разрешён) в stdout и завершается. Он получает <code>ANSIKO_COLS</code> и <code>ANSIKO_ROWS</code> для своей области. Ненулевой код возврата или таймаут показывают ошибку только в этой ячейке.</p>
      <h3>Правила</h3>
      <ul>
        <li>Укладывайтесь в таймаут; ставьте реалистичный <code>interval</code>.</li>
        <li>Предпочитайте ASCII и псевдографику; широкие эмодзи ломают сетку.</li>
        <li>Не зацикливайтесь: планировщик запускает новый процесс каждый раз.</li>
        <li>Добавьте необязательное <code>description</code> в манифест — оно появится в каталоге.</li>
      </ul>
      <p>Скрипты — доверенный локальный код. Не храните секреты в виджете на общей машине.</p>
    `,
  },
};

let language = "en";

export function getLanguage() {
  return language;
}

export function t(key, variables = {}) {
  const value = dictionaries[language]?.[key] ?? dictionaries.en[key] ?? key;
  return String(value).replace(/\{(\w+)\}/g, (_, name) => (
    variables[name] === undefined ? `{${name}}` : String(variables[name])
  ));
}

export function applyStatic(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  root.querySelectorAll("[data-i18n-html]").forEach((element) => {
    element.innerHTML = t(element.dataset.i18nHtml);
  });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder));
  });
  root.querySelectorAll("[data-i18n-title]").forEach((element) => {
    element.setAttribute("title", t(element.dataset.i18nTitle));
  });
  root.querySelectorAll("[data-i18n-aria]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAria));
  });
  root.querySelectorAll("[data-i18n-alt]").forEach((element) => {
    element.setAttribute("alt", t(element.dataset.i18nAlt));
  });
  document.documentElement.lang = language;
  document.querySelectorAll("[data-lang-toggle]").forEach((button) => {
    button.textContent = language.toUpperCase();
    button.setAttribute("aria-label", t("login.lang"));
  });
}

export function setLanguage(next, { persist = true, notify = true } = {}) {
  language = next === "ru" ? "ru" : "en";
  if (persist) localStorage.setItem("ansiko-lang", language);
  applyStatic();
  if (notify) document.dispatchEvent(new CustomEvent("ansiko:lang", { detail: language }));
}

export function initLanguage() {
  const stored = localStorage.getItem("ansiko-lang");
  const browser = (navigator.language || "en").toLowerCase();
  const initial = stored === "ru" || stored === "en" ? stored : (browser.startsWith("ru") ? "ru" : "en");
  setLanguage(initial, { persist: false, notify: false });
  return initial;
}
