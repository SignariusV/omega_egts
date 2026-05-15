# GUI Module Documentation — OMEGA_EGTS

## Table of Contents
1. [Overview](#overview)
2. [Architecture & Design Principles](#architecture--design-principles)
3. [Directory Structure](#directory-structure)
4. [Core Components](#core-components)
5. [Dashboard System](#dashboard-system)
6. [Bridge Layer](#bridge-layer)
7. [Widgets Library](#widgets-library)
8. [Utilities](#utilities)
9. [Overlays](#overlays)
10. [Resources](#resources)
11. [Testing](#testing)
12. [How It All Works Together](#how-it-all-works-together)

---

## Overview

The `gui/` module provides a modern, dashboard-style graphical interface for the OMEGA_EGTS system. Built with **PySide6** (Qt for Python) and **qasync** for async integration, it enables users to:

- Monitor EGTS server status and CMW-500 connections
- Run test scenarios with step-by-step progress tracking
- View live packet traffic (Rx/Tx) with filtering
- Monitor system logs with color-coded levels
- Configure all system settings via a persistent settings card

The GUI follows a **card-based dashboard** metaphor similar to IDEs like VS Code or PyCharm, where each functional area is a "card" that can be collapsed, expanded, moved, or hidden.

---

## Architecture & Design Principles

### 1. Card-Based Dashboard
The primary UI metaphor is a **grid-based dashboard** (`8x8`) where each functional unit is a `BaseCard` subclass. Cards can:
- Be **collapsed** (compact view) or **expanded** (full view)
- Be **dragged** to reposition on the grid
- Be **resized** via corner handles
- Be **hidden/shown** via the sidebar

### 2. Dual-View Pattern
Every card implements a **compact/expanded** dual-view pattern using `QStackedWidget`:
- **Compact view**: Minimal widget shown when card width < 320px or manually collapsed
- **Expanded view**: Full widget shown when card width >= 600px or manually expanded

### 3. Event-Driven Communication
The GUI uses an **EventBridge** pattern to decouple the Qt UI from the core engine:
- `core.event_bus.EventBus` — async event system in the core
- `gui.bridge.EventBridge` — Qt-based bridge that subscribes to core events and emits Qt signals
- Cards connect to `EventBridge` signals for updates

### 4. Async Integration
Uses **qasync** to integrate `asyncio` with Qt's event loop:
- `qasync.QEventLoop` replaces the standard Qt event loop
- Async slots decorated with `@qasync.asyncSlot` for async event handlers

### 5. Persistence
Layout and state are automatically saved/loaded:
- `layout.json` — card positions, sizes, visibility
- `state.json` — per-card state (filters, selections, etc.)
- Managed by `PersistenceManager`

### 6. VS Code Dark Theme
A custom dark theme inspired by VS Code:
- Defined in `gui/utils/theme.py` as `THEME_VSCODE_DARK`
- Applied via Qt Stylesheets (QSS)
- WCAG AA contrast-compliant

---

## Directory Structure

```
gui/
├── __init__.py                    # Module marker
├── main.py                        # Application entry point
├── main_window.py                 # Main window with grid dashboard
├── layout.json                    # Saved dashboard layout
├── state.json                     # Saved card states
│
├── dashboard/                     # Dashboard system
│   ├── __init__.py
│   ├── card_base.py              # BaseCard — base class for all cards
│   ├── container.py              # DashboardContainer — grid layout manager
│   ├── sidebar.py                # CardSidebar — icon-based card toggle
│   ├── layout_engine.py         # Grid constants and geometry utilities
│   ├── persistence.py           # Layout/state save/load manager
│   └── cards/                   # Individual dashboard cards
│       ├── __init__.py
│       ├── system_status.py      # SystemStatusCard — server/CMW status
│       ├── scenario_runner.py    # ScenarioRunnerCard — scenario execution
│       ├── live_packets.py       # LivePacketsCard — packet monitoring
│       ├── system_logs.py        # SystemLogsCard — log viewer
│       └── settings.py          # SettingsCard — application settings
│
├── bridge/                        # Core-GUI bridge layer
│   ├── __init__.py
│   ├── event_bridge.py           # EventBridge — translates core events to Qt signals
│   └── engine_wrapper.py        # EngineWrapper — async wrapper for CoreEngine
│
├── widgets/                       # Reusable UI widgets
│   ├── __init__.py
│   ├── collapsible_group.py     # CollapsibleGroupBox — expandable section
│   ├── packet_table.py          # PacketTableModel — table model for packets
│   ├── log_viewer.py            # LogViewer — color-coded log display
│   ├── status_indicator.py      # StatusIndicator — colored dot indicator
│   └── progress_bar.py         # ProgressBarWidget — segmented progress bar
│
├── utils/                         # Utility modules
│   ├── __init__.py
│   ├── theme.py                 # Theme definition and QSS generator
│   ├── qt_log_handler.py        # QLogHandler — routes Python logging to Qt
│   ├── scenario_scanner.py      # Scan scenario directories for JSON files
│   └── icon_loader.py          # (Placeholder for icon loading utilities)
│
├── overlays/                      # Dialog overlays
│   ├── __init__.py
│   └── scenario_editor.py      # ScenarioEditorOverlay — JSON editor with syntax highlighting
│
└── resources/                    # Static resources
    ├── defaults/                # Default layout and state JSON files
    │   ├── layout_default.json
    │   └── state_default.json
    ├── icons/                   # SVG icons for cards and UI
    │   ├── server.svg
    │   ├── cmw.svg
    │   ├── scenario.svg
    │   ├── packets.svg
    │   ├── logs.svg
    │   └── settings.svg
    └── styles/                  # Additional QSS style files
        └── base.qss
```

---

## Core Components

### `main.py` — Application Entry Point

**Location**: `gui/main.py`

**Purpose**: Initializes and runs the Qt application with asyncio integration.

```python
def main():
    app = QApplication(sys.argv)
    apply_theme(app)                      # Apply VS Code dark theme
    window = MainWindow()                 # Create main window
    window.show()
    loop = qasync.QEventLoop(app)         # Integrate asyncio
    asyncio.set_event_loop(loop)
    loop.run_forever()
```

**Key Points**:
- Sets up Python logging via `core.python_logger`
- Applies the dark theme before creating any widgets
- Uses `qasync.QEventLoop` to allow `async/await` in Qt slots

---

### `main_window.py` — Main Window

**Location**: `gui/main_window.py` (302 lines)

**Purpose**: The top-level window that hosts the dashboard, sidebar, and menu bar.

**Responsibilities**:
1. **Initialization**:
   - Loads `Config` from `config/settings.json`
   - Creates `EventBus`, `EngineWrapper`, `EventBridge`
   - Creates `DashboardContainer` and `CardSidebar`
   - Creates and positions all dashboard cards

2. **Card Management**:
   - Creates 4 default cards: `SystemStatusCard`, `ScenarioRunnerCard`, `LivePacketsCard`, `SystemLogsCard`, `SettingsCard`
   - Positions them on the 8x8 grid via `DashboardContainer.add_card()`
   - Hides `SettingsCard` by default (accessed via sidebar)

3. **Signal Connections**:
   - Connects `EventBridge` signals to card slots
   - Connects card signals (e.g., `run_requested`) to window handlers

4. **Keyboard Shortcuts**:
   - `Ctrl+Q` — Quit application
   - `Ctrl+R` — Toggle server start/stop
   - `F5` — Run selected scenario
   - `Ctrl+1-4` — Focus specific card
   - `Ctrl+B` — Toggle sidebar visibility
   - `Escape` — Close open overlays

5. **Persistence**:
   - Calls `_save_layout()` on `closeEvent`
   - Calls `_load_layout()` on initialization

6. **Graceful Shutdown**:
   - Stops the `EngineWrapper` async
   - Waits for async cleanup before quitting

---

## Dashboard System

### `card_base.py` — BaseCard

**Location**: `gui/dashboard/card_base.py` (337 lines)

**Purpose**: Abstract base class for all dashboard cards.

**Key Features**:
- **Dual Views**: `QStackedWidget` with compact (index 0) and expanded (index 1) widgets
- **Collapsible**: `collapse()` / `expand()` methods toggle `_collapsed` state
- **Grid Sizing**: Properties `grid_size` (row_span, col_span) and `grid_position` (row, col)
- **Draggable Title Bar**: `QFrame` with `OpenHandCursor`, initiates `QDrag`
- **Resize Handles**: 4 corner `QFrame` widgets with `SizeFDiagCursor` / `SizeBDiagCursor`
- **Context Menu**: Right-click for collapse/expand, reset, or close (hide)
- **Visibility Signals**: `card_visibility_changed(bool)` emitted on `show()`/`hide()`

**Grid Integration**:
- `set_grid_position(row, col)` — Set position in grid cells
- `set_grid_size(row_span, col_span)` — Set size in grid cells, emits `grid_size_changed`
- `grid_geometry_changed` — Emitted when both position and size change (from resize handles)

**Auto-Switch Display State**:
```python
def resizeEvent(self, event):
    w = event.size().width()
    if w < 320 and self._display_state != DisplayState.COMPACT:
        self._set_display_state(DisplayState.COMPACT)
    elif w >= 600 and self._display_state != DisplayState.EXPANDED:
        self._set_display_state(DisplayState.EXPANDED)
```

---

### `container.py` — DashboardContainer

**Location**: `gui/dashboard/container.py` (367 lines)

**Purpose**: Manages the grid layout of cards, handling positioning, collision detection, and drag-and-drop.

**Grid Specification**:
- **8 rows** x **8 columns** (`GRID_ROWS=8`, `GRID_COLS=8` from `layout_engine.py`)
- **6px gap** between cells (`GRID_GAP=6`)
- Cell size calculated dynamically: `cell_w = (width - 7*6) / 8`

**Key Methods**:
- `add_card(card, row, col, row_span, col_span)` — Add card to grid
- `move_card(card_id, new_row, new_col)` — Move card to new position
- `resize_card(card_id, row_span, col_span)` — Resize card
- `hide_card(card_id)` / `show_card(card_id)` — Toggle visibility
- `get_layout_snapshot()` — Returns list of `{card_id, row, col, row_span, col_span}` dicts
- `apply_layout_snapshot(snapshot)` — Restore layout from saved snapshot

**Collision Detection**:
```python
def _is_area_free(self, row, col, row_span, col_span, exclude_card_id=None):
    for cid, (r, c, rs, cs) in self._cards.items():
        if cid == exclude_card_id: continue
        if not (col + col_span <= c or col >= c + cs or row + row_span <= r or row >= r + rs):
            return False
    return True
```

**Drag-and-Drop Support**:
- Accepts `QMimeData` with `card_id` as text
- `dragEnterEvent`, `dragMoveEvent`, `dropEvent` for repositioning

---

### `sidebar.py` — CardSidebar

**Location**: `gui/dashboard/sidebar.py` (194 lines)

**Purpose**: Vertical icon sidebar for toggling card visibility, similar to VS Code's activity bar.

**Features**:
- **Icon Buttons**: Each card gets a `QToolButton` with icon or first letter of title
- **Checked State**: Button checked = card visible, unchecked = card hidden
- **Auto-Sync**: Listens to `container.cards_changed` and `container.card_visibility_changed`
- **Scrollable**: `QScrollArea` for many cards
- **Toggle Button**: `◀` button to hide/show the sidebar itself
- **Restore Button**: In status bar to restore hidden sidebar

**Button Creation**:
```python
def _add_button(self, card_id, card):
    btn = QToolButton()
    btn.setCheckable(True)
    btn.setChecked(not card.isHidden())
    btn.clicked.connect(lambda checked, cid=card_id: self._on_button_clicked(cid))
```

---

### `layout_engine.py` — Grid Utilities

**Location**: `gui/dashboard/layout_engine.py` (22 lines)

**Purpose**: Defines grid constants and geometry calculation functions.

**Constants**:
```python
GRID_ROWS = 8
GRID_COLS = 8
GRID_GAP = 6
```

**Functions**:
- `cell_size(container_w, container_h)` — Returns `(cell_w, cell_h)` float tuple
- `grid_position(pos_x, pos_y, container_w, container_h)` — Converts pixel coordinates to `(row, col)`

---

### `persistence.py` — PersistenceManager

**Location**: `gui/dashboard/persistence.py` (87 lines)

**Purpose**: Save and load dashboard layout and card states to JSON files.

**Files**:
- `layout.json` — Array of `{card_id, row, col, row_span, col_span}` objects
- `state.json` — Dict with per-card state (keys: `status_card`, `scenario_card`, etc.)

**Methods**:
- `save_layout(snapshot)` / `load_layout()` — Layout persistence
- `save_state(states)` / `load_state()` — State persistence
- `reset_to_defaults()` — Delete saved files to revert to defaults

**Validation**:
```python
def _validate_layout(self, data):
    if not isinstance(data, list): raise ValueError("Layout must be a list")
    for item in data:
        if 'card_id' not in item: raise ValueError("Missing required key: card_id")
        # ... validates row, col, row_span, col_span
```

---

### Cards

#### `system_status.py` — SystemStatusCard

**Location**: `gui/dashboard/cards/system_status.py` (170 lines)

**Purpose**: Displays server status (running/stopped) and CMW-500 connection status.

**Compact View**: `CompactStatusWidget` with two `StatusIndicator` dots (server + CMW)

**Expanded View**:
- **Server Group**: Status label, port label, toggle button (Start/Stop)
- **CMW-500 Group**: Status, IP, mode, IMEI, IMSI, RSSI

**Signals**:
- `toggle_server_requested` — Emitted when user clicks toggle button

**Slots**:
- `on_server_started(data)` / `on_server_stopped(data)` — Update server status
- `on_cmw_connected(data)` / `on_cmw_disconnected()` — Update CMW status
- `on_cmw_status(data)` — Update CMW data fields

**State**:
```python
def get_state(self):
    return {"server_running": self._server_running, "server_port": self._server_port, "cmw_connected": self._cmw_connected}
```

---

#### `scenario_runner.py` — ScenarioRunnerCard

**Location**: `gui/dashboard/cards/scenario_runner.py` (229 lines)

**Purpose**: Allows users to select and run test scenarios, with progress tracking.

**Compact View**: ComboBox + Run button

**Expanded View**:
- ComboBox for scenario selection
- `ProgressBarWidget` for execution progress
- `QTableView` with `StepTableModel` showing step-by-step status

**StepTableModel** (inner class):
- Columns: "Step Name", "Status", "Duration"
- Methods: `set_steps()`, `update_step()`

**Signals**:
- `run_requested(path)` — Emitted when user clicks Run
- `stop_requested()` — Emitted when user clicks Stop (while running)

**Slots**:
- `on_scenario_step(data)` — Updates step status, progress bar
- `on_command_error(data)` — Stops scenario on error

**Scenario Scanning**: Uses `gui.utils.scenario_scanner.scan_scenarios()` to populate ComboBox

---

#### `live_packets.py` — LivePacketsCard

**Location**: `gui/dashboard/cards/live_packets.py` (294 lines)

**Purpose**: Displays live EGTS packet traffic with filtering.

**Compact View**: `CompactProxyModel` showing last 5 packets

**Expanded View**:
- **Toolbar**: Filter text input, channel ComboBox (All/tcp/sms), Clear button
- **Table**: `QTableView` with `PacketFilterProxy` for filtering
- **Stats**: "Rx: N | Tx: N" label

**PacketFilterProxy** (inner class):
- Filters by text (regex supported) and channel
- `filterAcceptsRow()` checks both criteria

**Slots**:
- `on_packet_processed(data)` — Add received packet to model
- `on_packet_sent(data)` — Add sent packet to model

**Packet Format**:
```python
{
    "timestamp": "...",
    "pid": "...",
    "service": "...",
    "length": N,
    "channel": "tcp" | "sms",
    "crc": "OK" | "FAIL",
    "duplicate": "Yes" | "No",
    "hex": "...",
    "parsed": {...},
    "direction": "rx" | "tx"
}
```

**Double-Click**: Shows detailed packet info in `QMessageBox`

---

#### `system_logs.py` — SystemLogsCard

**Location**: `gui/dashboard/cards/system_logs.py` (277 lines)

**Purpose**: Displays system logs with color-coded levels and source filtering.

**Compact View**: `QPlainTextEdit` showing last 3 log messages

**Expanded View**:
- **Toolbar**: Source ComboBox, Level ComboBox, Clear button
- **Log Viewer**: `LogViewer` widget with HTML color formatting

**Log Sources** (filter options):
- `All`, `GUI`, `Core`, `Packets`, `Connections`, `Scenarios`, `Commands`
- Plus individual module names: `logger`, `tcp_server`, `dispatcher`, `session`, `engine`, `cmw500`, `scenario`

**Log Levels**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**Integration**:
- `QLogHandler` routes Python `logging` records to Qt signal
- `EventBridge` signals for packet/connection/scenario/command events

**Color Coding** (from `widgets/log_viewer.py`):
- `DEBUG`: gray, `INFO`: light gray, `WARNING`: orange, `ERROR`/`CRITICAL`: red
- Sources have distinct colors (e.g., `GUI`: cyan, `engine`: green)

---

#### `settings.py` — SettingsCard

**Location**: `gui/dashboard/cards/settings.py` (386 lines)

**Purpose**: Provides UI for viewing and editing application settings.

**Compact View**: Label showing port and GOST version

**Expanded View** (scrollable):
- **General Settings**: GOST version, TCP host/port
- **CMW-500 Settings**: IP, simulation mode, timeouts, MCC/MNC, RF level, SMS settings
- **Timeouts**: Various timeout configurations
- **Logging**: Level, directory, file size, retention

**Widgets Used**: `CollapsibleGroupBox` for each settings group

**Save Flow**:
1. User clicks "Сохранить настройки"
2. `_collect_data()` gathers all widget values into dict
3. Writes to `config/settings.json`
4. Emits `settings_changed` signal
5. Shows "restart required" message in status bar

**Note**: Settings take effect on next application restart (by design, since `EngineWrapper` is created once with initial config).

---

## Bridge Layer

### `event_bridge.py` — EventBridge

**Location**: `gui/bridge/event_bridge.py` (77 lines)

**Purpose**: Translates `core.event_bus.EventBus` events into Qt signals for the GUI.

**Signal Mapping**:
| Core Event | Qt Signal |
|------------|----------|
| `packet.processed` | `packet_processed(dict)` |
| `packet.sent` | `packet_sent(dict)` |
| `cmw.status` | `cmw_status(dict)` |
| `cmw.connected` | `cmw_connected(dict)` |
| `cmw.disconnected` | `cmw_disconnected(dict)` |
| `cmw.error` | `cmw_error(str)` |
| `server.started` | `server_started(dict)` |
| `server.stopped` | `server_stopped(dict)` |
| `connection.changed` | `connection_changed(dict)` |
| `scenario.step` | `scenario_step(dict)` |
| `command.sent` | `command_sent(dict)` |
| `command.error` | `command_error(dict)` |

**Usage**:
```python
bridge = EventBridge(event_bus)
bridge.packet_processed.connect(card.on_packet_processed)
```

---

### `engine_wrapper.py` — EngineWrapper

**Location**: `gui/bridge/engine_wrapper.py` (71 lines)

**Purpose**: Async wrapper around `core.engine.CoreEngine` for use with `qasync`.

**Methods** (all async):
- `start()` / `stop()` — Start/stop the core engine
- `get_status()` — Get engine status dict
- `cmw_status()` — Get CMW-500 status
- `run_scenario(path, connection_id)` — Execute a scenario
- `stop_scenario()` — Stop running scenario
- `replay(log_path, scenario_path)` — Replay from log
- `export(data_type, fmt, output_path)` — Export data
- `load_scenario_info(path)` — Load and validate scenario metadata

**Note**: This wrapper exists because `CoreEngine` methods are async and need to be called from Qt slots via `@qasync.asyncSlot`.

---

## Widgets Library

### `collapsible_group.py` — CollapsibleGroupBox

**Location**: `gui/widgets/collapsible_group.py` (102 lines)

**Purpose**: A widget with a clickable header that expands/collapses its content.

**Usage in SettingsCard**:
```python
group = CollapsibleGroupBox("Общие настройки")
form = QFormLayout()
# ... add widgets ...
group.set_content_layout(form)
```

**Signal**: `toggled(bool)` — Emitted when collapsed state changes

---

### `packet_table.py` — PacketTableModel

**Location**: `gui/widgets/packet_table.py` (84 lines)

**Purpose**: `QAbstractTableModel` for displaying packet data with buffering.

**Columns**: "Timestamp", "PID", "Service", "Length", "Channel", "CRC", "Duplicate"

**Buffering**:
- `_buffer`: `deque(maxlen=5000)` for packets
- `_pending`: List for new packets (flushed every 100ms via `QTimer`)
- `flush()` — Moves pending to buffer, emits `beginInsertRows`/`endInsertRows`

**Methods**:
- `add_packet(packet)` — Add to pending list
- `get_rx_count()` / `get_tx_count()` — Packet counters
- `get_packet(row)` — Get packet dict by row
- `clear()` — Clear all packets

---

### `log_viewer.py` — LogViewer

**Location**: `gui/widgets/log_viewer.py` (65 lines)

**Purpose**: Color-coded log display widget.

**Color Maps**:
- **Level Colors**: DEBUG: gray, INFO: light gray, WARNING: orange, ERROR: red
- **Source Colors**: GUI: cyan, engine: green, cmw500: orange, etc.

**Method**: `append_log(level, message, timestamp, source)` — Appends HTML-formatted log line

---

### `status_indicator.py` — StatusIndicator & CompactStatusWidget

**Location**: `gui/widgets/status_indicator.py` (83 lines)

**StatusIndicator**: A colored dot (10x10px, border-radius 5px)
- Colors: `GREEN`, `RED`, `YELLOW`, `GREY` (from `StatusColor` enum)
- Method: `set_color(color)`

**CompactStatusWidget**: Horizontal layout with two indicators + labels
- Used in `SystemStatusCard` compact view
- Methods: `set_server_status(running, port)`, `set_cmw_status(connected, text, mode)`

---

### `progress_bar.py` — ProgressBarWidget

**Location**: `gui/widgets/progress_bar.py` (49 lines)

**Purpose**: Segmented progress bar (10 segments) with percentage label.

**Usage in ScenarioRunnerCard**:
```python
bar = ProgressBarWidget()
bar.set_value(50)  # Shows 5/10 segments filled, "50%" label
```

---

## Utilities

### `theme.py` — Theme Engine

**Location**: `gui/utils/theme.py` (408 lines)

**Purpose**: Defines the VS Code-inspired dark theme and generates Qt Stylesheets (QSS).

**Theme Dict** (`THEME_VSCODE_DARK`):
```python
{
    "bg": "#1E1E1E",           # Window background
    "card_bg": "#252526",       # Card background
    "border": "#3E3E42",       # Borders
    "text": "#CCCCCC",          # Text color
    "accent": "#007ACC",        # Accent (buttons, links)
    "success": "#4EC9B0",      # Green
    "warning": "#CE9178",       # Orange
    "error": "#F44747",         # Red
    "font_main": "Segoe UI",   # Main font
    "font_mono": "Consolas",    # Monospace font
    # ... more keys
}
```

**Key Functions**:
- `generate_qss(theme)` — Generates complete QSS string from theme dict
- `apply_theme(app, theme_name)` — Applies theme to QApplication
- `contrast_ratio(bg, fg)` — Calculates WCAG contrast ratio
- `validate_contrast(theme)` — Validates WCAG AA compliance (>= 4.5:1)

---

### `qt_log_handler.py` — QLogHandler

**Location**: `gui/utils/qt_log_handler.py` (23 lines)

**Purpose**: Routes Python `logging` records to Qt signals.

**Usage**:
```python
handler = QLogHandler()
handler.log_message.connect(slot_function)
logging.getLogger().addHandler(handler)
```

**Emit Format**:
```python
{"level": record.levelname, "message": self.format(record), "timestamp": record.created, "logger": record.name}
```

---

### `scenario_scanner.py` — ScenarioScanner

**Location**: `gui/utils/scenario_scanner.py` (41 lines)

**Purpose**: Scans directories for valid scenario JSON files.

**ScenarioInfo** (dataclass):
```python
@dataclass
class ScenarioInfo:
    name: str        # From JSON "name" field
    path: Path       # Directory path
    json_file: Path  # Path to scenario.json
```

**Function**: `scan_scenarios(scenarios_dir)` — Scans subdirectories for `scenario.json` files

**Default Path**: `get_default_scenarios_path()` looks for `<root>/scenarios/` or `<root>/tests/scenarios/`

---

### `icon_loader.py` — (Placeholder)

**Location**: `gui/utils/icon_loader.py` (1 line)

**Note**: Currently empty, reserved for future icon loading utilities.

---

## Overlays

### `scenario_editor.py` — ScenarioEditorOverlay

**Location**: `gui/overlays/scenario_editor.py` (158 lines)

**Purpose**: A `QDialog` for editing scenario JSON files with syntax highlighting.

**Features**:
- **JSON Syntax Highlighter** (`JsonSyntaxHighlighter`):
  - Keys: cyan (`#9CDCFE`)
  - Strings: orange (`#CE9178`)
  - Numbers: green (`#B5CEA8`)
  - Brackets: gold (`#FFD700`)

- **Toolbar**: Validate button, Save button, Cancel button
- **Validation**: Checks JSON syntax and scenario structure (name, version, steps)
- **Save**: Writes to file, shows success/error status

---

## Resources

### `resources/` Directory

**Static assets** used by the GUI:

**Icons** (`resources/icons/`):
- `server.svg` — System Status card
- `cmw.svg` — (Reserved for CMW-500)
- `scenario.svg` — Scenario Runner card
- `packets.svg` — Live Packets card
- `logs.svg` — System Logs card
- `settings.svg` — Settings card

**Defaults** (`resources/defaults/`):
- `layout_default.json` — Default layout (currently empty `[]`)
- `state_default.json` — Default state (currently empty `{}`)

**Styles** (`resources/styles/`):
- `base.qss` — Additional QSS (currently unused in code)

---

## Testing

### Test Structure

Tests are located in `tests/gui/` and mirror the `gui/` module structure:

```
tests/gui/
├── __init__.py
├── test_main.py                # MainWindow tests
├── test_container.py           # DashboardContainer tests
├── test_card_base.py           # BaseCard tests
├── test_sidebar.py             # CardSidebar tests
├── test_persistence.py         # PersistenceManager tests
├── test_theme.py              # Theme/contrast tests
├── test_event_bridge.py        # EventBridge tests
├── test_engine_wrapper.py      # EngineWrapper tests
├── test_qt_log_handler.py      # QLogHandler tests
├── test_settings_flow.py       # Settings save/load flow
├── test_settings_persistence.py # Settings persistence
├── test_settings_integration.py # Settings integration
├── test_integration.py         # End-to-end integration tests
├── cards/
│   ├── __init__.py
│   ├── test_system_status.py   # SystemStatusCard tests
│   ├── test_scenario_runner.py # ScenarioRunnerCard tests
│   ├── test_live_packets.py    # LivePacketsCard tests
│   └── test_system_logs.py    # SystemLogsCard tests
├── widgets/
│   ├── __init__.py
│   └── test_collapsible_group.py # CollapsibleGroupBox tests
└── overlays/
    ├── __init__.py
    └── test_scenario_editor.py # ScenarioEditorOverlay tests
```

### Test Configuration

**Framework**: `pytest` with `pytest-qt` for Qt widget testing

**Fixtures** (from `tests/conftest.py`):
- `project_root()` — Returns project root Path
- `mock_event_bus()` — Creates mock `EventBus` with async methods
- `sample_config_dict()` — Returns sample configuration dict
- `mock_stream_pair()` — Mock TCP reader/writer pair

**Qt Fixtures** (from `pytest-qt`):
- `qtbot` — Manages Qt widgets in tests, provides `addWidget()`, `waitSignal()`, `wait()`

### Running Tests

```bash
# Run all GUI tests
pytest tests/gui/ -v

# Run specific test file
pytest tests/gui/test_container.py -v

# Run with asyncio support
pytest tests/gui/test_integration.py -v --asyncio-mode=auto
```

### Test Coverage Areas

| Component | Test File | Coverage |
|-----------|-----------|----------|
| `MainWindow` | `test_main.py` | Opening window, status bar messages |
| `DashboardContainer` | `test_container.py` | Add/remove/move/resize/hide/show cards, signals |
| `BaseCard` | `test_card_base.py` | Collapse/expand, grid size, visibility signals |
| `CardSidebar` | `test_sidebar.py` | Button creation, checked state, toggle behavior |
| `PersistenceManager` | `test_persistence.py` | Save/load, corrupted JSON fallback |
| `EventBridge` | `test_event_bridge.py` | All 12 signal translations |
| `Theme` | `test_theme.py` | Contrast ratio, QSS generation |
| `ScenarioRunnerCard` | `test_scenario_runner.py` | Step model, signals, state |
| `LivePacketsCard` | `test_live_packets.py` | Packet model, filtering, state |
| `SystemStatusCard` | `test_system_status.py` | Status updates, state save/load |
| `ScenarioEditorOverlay` | `test_scenario_editor.py` | JSON validation, save flow |

---

## How It All Works Together

### Startup Sequence

1. `main.py:main()` → Creates `QApplication`, applies theme
2. `MainWindow.__init__()`:
   - Loads `Config` from `config/settings.json`
   - Creates `EventBus()`, `EngineWrapper()`, `EventBridge()`
   - Creates `DashboardContainer()` and `CardSidebar()`
   - Creates 5 cards, adds to dashboard at grid positions
   - Connects `EventBridge` signals → card slots
   - Calls `_load_layout()` to restore saved positions
3. `window.show()` → Displays the main window
4. `loop.run_forever()` → Starts qasync event loop

### Runtime Event Flow

```
Core Engine (asyncio)
    ↓ emits event via EventBus
EventBus ("packet.processed", data)
    ↓ EventBridge subscribes via bus.on()
EventBridge (Qt object)
    ↓ emits Qt signal
packet_processed.emit(data)
    ↓ card connects to signal
LivePacketsCard.on_packet_processed(data)
    ↓ updates model
PacketTableModel.add_packet(packet)
    ↓ flush timer (100ms)
TableView displays new row
```

### User Interaction Flow (Run Scenario)

1. User selects scenario from ComboBox in `ScenarioRunnerCard`
2. User clicks "Run" button (or presses F5)
3. `ScenarioRunnerCard._on_toggle_clicked()` emits `run_requested(path)`
4. `MainWindow._on_run_scenario(path)`:
   - Checks if engine is running, starts if not
   - Calls `await engine_wrapper.run_scenario(path)`
5. Core engine executes scenario, emits "scenario.step" events
6. `EventBridge.scenario_step.emit(data)`
7. `ScenarioRunnerCard.on_scenario_step(data)`:
   - Updates `StepTableModel`
   - Updates `ProgressBarWidget`
   - If step status is "PASS" or "FAIL", stops the running state

### Shutdown Sequence

1. User clicks X or presses Ctrl+Q
2. `MainWindow.closeEvent()`:
   - Sets `_closing = True`
   - Calls `_save_layout()` (saves `layout.json` and `state.json`)
   - Creates async `shutdown()` coroutine:
     - Calls `await engine_wrapper.stop()`
     - Calls `QApplication.instance().quit()`
   - Schedules via `asyncio.ensure_future(shutdown())`
3. Event loop processes shutdown, then exits

---

## Summary

The `gui/` module is a well-structured, modern Qt application with:
- **Card-based dashboard** with grid layout and drag-and-drop
- **Dual-view pattern** (compact/expanded) for responsive UI
- **Event-driven architecture** bridging asyncio core with Qt signals
- **Comprehensive theming** with WCAG-compliant dark theme
- **Full persistence** of layout and state
- **Thorough test coverage** using pytest-qt

The modular design allows easy addition of new cards (subclass `BaseCard`) and new widgets (add to `widgets/`), making the GUI extensible for future OMEGA_EGTS features.
