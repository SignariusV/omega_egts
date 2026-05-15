# OMEGA_EGTS GUI
# Grid layout engine - constants and utilities for dashboard grid management


GRID_ROWS = 8
GRID_COLS = 8
GRID_GAP = 6


def cell_size(container_width: float, container_height: float) -> tuple[float, float]:
    """Calculate cell size accounting for gaps (returns float)."""
    cell_w = (container_width - (GRID_COLS - 1) * GRID_GAP) / GRID_COLS
    cell_h = (container_height - (GRID_ROWS - 1) * GRID_GAP) / GRID_ROWS
    return max(1.0, cell_w), max(1.0, cell_h)


def grid_position(pos_x: float, pos_y: float, container_width: float, container_height: float) -> tuple[int, int]:
    """Determine grid row and column from point coordinates (accounts for gaps)."""
    cell_w, cell_h = cell_size(container_width, container_height)
    col = int(pos_x / (cell_w + GRID_GAP))
    row = int(pos_y / (cell_h + GRID_GAP))
    return max(0, min(GRID_ROWS - 1, row)), max(0, min(GRID_COLS - 1, col))