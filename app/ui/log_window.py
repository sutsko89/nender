"""Окно журнала событий приложения."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from app.db import get_logs


LEVEL_COLORS = {
    "ERROR":   "#e0ced7",
    "WARNING": "#e9e0c6",
    "INFO":    "#ffffff",
    "DEBUG":   "#f9f8f5",
}


class LogWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Журнал событий")
        self.setMinimumSize(860, 480)
        self.resize(960, 560)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Заголовок
        header = QHBoxLayout()
        title = QLabel("Журнал событий")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        self.level_filter = QComboBox()
        self.level_filter.addItems(["Все", "INFO", "WARNING", "ERROR"])
        self.level_filter.currentTextChanged.connect(self._filter)
        header.addWidget(QLabel("Уровень:"))
        header.addWidget(self.level_filter)

        btn_refresh = QPushButton("↻ Обновить")
        btn_refresh.setStyleSheet("background:#cedcd8;color:#0f3638;border-radius:4px;padding:6px 12px;")
        btn_refresh.clicked.connect(self._load)
        header.addWidget(btn_refresh)
        layout.addLayout(header)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Дата/время", "Уровень", "Модуль", "Сообщение"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        btn_close = QPushButton("Закрыть")
        btn_close.setStyleSheet("background:transparent;color:#7a7974;border:1px solid #d4d1ca;border-radius:4px;padding:6px 18px;")
        btn_close.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn_close)
        layout.addLayout(row)

    def _load(self):
        self._all = get_logs(limit=500)
        self._filter(self.level_filter.currentText())

    def _filter(self, level: str):
        rows = self._all if level == "Все" else [r for r in self._all if r["level"] == level]
        self.table.setRowCount(len(rows))
        for i, entry in enumerate(rows):
            self.table.setRowHeight(i, 32)
            self.table.setItem(i, 0, QTableWidgetItem(entry.get("created_at", "")))
            lvl_item = QTableWidgetItem(entry.get("level", "INFO"))
            lvl_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            bg = LEVEL_COLORS.get(entry.get("level", "INFO"), "#ffffff")
            lvl_item.setBackground(QColor(bg))
            self.table.setItem(i, 1, lvl_item)
            self.table.setItem(i, 2, QTableWidgetItem(entry.get("module", "")))
            msg = entry.get("message", "")
            if entry.get("details"):
                msg += f"  [{entry['details'][:80]}]"
            self.table.setItem(i, 3, QTableWidgetItem(msg))
