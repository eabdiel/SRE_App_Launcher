from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout


class ResponsiveBar(QWidget):
    """
    Packs widgets left-to-right and wraps to a 2nd row when needed.
    Keeps order stable.

    - Call set_items([...]) once
    - Call relayout(width) on resize
    """

    def __init__(self, parent=None, max_rows: int = 2):
        super().__init__(parent)
        self.max_rows = max_rows
        self._items = []

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(6)

        self._rows = []
        for _ in range(max_rows):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            self._rows.append(row)
            self._outer.addLayout(row)

        # filler at end of last row so the bar doesn't look cramped
        self._rows[-1].addStretch(1)

    def set_items(self, items: list[QWidget]) -> None:
        self._items = items[:]
        self.relayout(self.width())

    def relayout(self, available_width: int) -> None:
        # Remove all widgets from rows (except the final stretch in last row)
        for r, row in enumerate(self._rows):
            # Remove everything
            while row.count():
                item = row.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.setParent(None)
            # Re-add stretch only on last row
            if r == len(self._rows) - 1:
                row.addStretch(1)

        if not self._items:
            return

        # Estimate packing: sum of widget sizeHints + spacing
        spacing = 6
        row_index = 0
        used = 0

        for w in self._items:
            w_hint = w.sizeHint().width()
            # First item doesn't need leading spacing
            extra = w_hint if used == 0 else (spacing + w_hint)

            # If doesn't fit in current row, wrap to next row (if possible)
            if used > 0 and (used + extra) > max(200, available_width) and row_index < (self.max_rows - 1):
                row_index += 1
                used = 0
                extra = w_hint  # reset row spacing

            # Add widget to row (before stretch if last row)
            row = self._rows[row_index]
            # Insert before stretch if it's the last row
            if row_index == self.max_rows - 1:
                insert_pos = max(0, row.count() - 1)
                row.insertWidget(insert_pos, w)
            else:
                row.addWidget(w)

            used += extra

        self.updateGeometry()
