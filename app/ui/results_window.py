"""Окно просмотра результатов поискового профиля."""

import webbrowser
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from app.db import get_recent_results


class ResultsWindow(QDialog):
    def __init__(self, profile_id: int, profile_name: str, parent=None):
        super().__init__(parent)
        self.profile_id = profile_id
        self.profile_name = profile_name
        self.setWindowTitle(f"Результаты: {profile_name}")
        self.setMinimumSize(1000, 560)
        self.resize(1100, 640)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Заголовок
        header = QHBoxLayout()
        title = QLabel(f"Найденные закупки: {self.profile_name}")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("color:#7a7974;")
        header.addWidget(self.lbl_count)
        layout.addLayout(header)

        # Поиск по таблице
        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Фильтр по названию, номеру, заказчику...")
        self.search_edit.textChanged.connect(self._filter)
        search_row.addWidget(self.search_edit)
        layout.addLayout(search_row)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Номер закупки", "Наименование", "Заказчик",
            "Регион", "Дата публ.", "Статус", "Ссылка"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 100)
        layout.addWidget(self.table)

        # Закрыть
        btn_close = QPushButton("Закрыть")
        btn_close.setStyleSheet("background:transparent;color:#7a7974;border:1px solid #d4d1ca;border-radius:4px;padding:6px 18px;")
        btn_close.clicked.connect(self.reject)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(btn_close)
        layout.addLayout(close_row)

    def _load(self):
        self._all_rows = get_recent_results(self.profile_id, limit=500)
        self._render(self._all_rows)

    def _render(self, rows):
        self.table.setRowCount(len(rows))
        for r, t in enumerate(rows):
            self.table.setRowHeight(r, 38)
            self.table.setItem(r, 0, QTableWidgetItem(t.get("purchase_number") or "—"))
            self.table.setItem(r, 1, QTableWidgetItem(t.get("title") or "—"))
            self.table.setItem(r, 2, QTableWidgetItem(t.get("customer_name") or "—"))
            self.table.setItem(r, 3, QTableWidgetItem(t.get("region") or "—"))
            self.table.setItem(r, 4, QTableWidgetItem((t.get("publish_date") or "")[:10]))
            self.table.setItem(r, 5, QTableWidgetItem(t.get("status") or "—"))

            url = t.get("source_url") or ""
            btn_open = QPushButton("Открыть")
            btn_open.setFixedHeight(28)
            btn_open.setStyleSheet("background:#cedcd8;color:#0f3638;border-radius:4px;padding:0 8px;font-size:12px;")
            if url:
                btn_open.clicked.connect(lambda _, u=url: webbrowser.open(u))
            else:
                btn_open.setEnabled(False)
            self.table.setCellWidget(r, 6, btn_open)

            # Новые — подсветить
            if t.get("is_new") and not t.get("email_sent"):
                for col in range(6):
                    item = self.table.item(r, col)
                    if item:
                        item.setBackground(QColor("#cedcd8"))

        self.lbl_count.setText(f"Всего: {len(rows)} закупок")

    def _filter(self, text: str):
        text = text.lower()
        filtered = [
            t for t in self._all_rows
            if text in (t.get("title") or "").lower()
            or text in (t.get("purchase_number") or "").lower()
            or text in (t.get("customer_name") or "").lower()
            or text in (t.get("region") or "").lower()
        ]
        self._render(filtered)
