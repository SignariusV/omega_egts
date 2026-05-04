# OMEGA_EGTS GUI
# Grid layout engine - constants and utilities for dashboard grid management


GRID_ROWS = 8
GRID_COLS = 8
GRID_GAP = 6


def cell_size(container_width: int, container_height: int) -> tuple[int, int]:
    """Calculate cell size accounting for gaps.
    
    Args:
        container_width: Total width of container
        container_height: Total height of container
        
    Returns:
        Tuple of (cell_width, cell_height)
    """
    cell_w = (container_width - (GRID_COLS - 1) * GRID_GAP) // GRID_COLS
    cell_h = (container_height - (GRID_ROWS - 1) * GRID_GAP) // GRID_ROWS
    return max(1, cell_w), max(1, cell_h)


def grid_position(pos_x: float, pos_y: float, container_width: int, container_height: int) -> tuple[int, int]:
    """Determine grid row and column from point coordinates.
    
    Args:
        pos_x: X coordinate in container
        pos_y: Y coordinate in container
        container_width: Total width of container
        container_height: Total height of container
        
    Returns:
        Tuple of (row, col) within grid bounds
    """
    cell_w, cell_h = cell_size(container_width, container_height)
    if cell_w <= 0 or cell_h <= 0:
        return 0, 0
    
    col = int(pos_x / cell_w)
    row = int(pos_y / cell_h)
    
    return max(0, min(GRID_ROWS - 1, row)), max(0, min(GRID_COLS - 1, col))