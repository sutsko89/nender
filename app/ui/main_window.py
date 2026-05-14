"""Главное окно приложения Nender."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel,
    QHeaderView, QMessageBox, QStatusBar
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from app.db import get_all_profiles, delete_profile, log
from app.scheduler import TenderScheduler
from app.ui.search_form import SearchFormDialog
from app.ui.results_window import ResultsWindow
from app.ui.settings_window import SettingsWindow
from app.ui.log_window import LogWindow

BTN_PRIMARY = (
    "QPushButton{background:#01696f;color:#fff;border:none;border-radius:4px;"
    "padding:5px 12px;font-size:12px;}"
    "QPushButton:hover{background:#0c4e54;}"
    "QPushButton:pressed{background:#0f3638;}"
)
BTN_SECONDARY = (
    "QPushButton{background:#cedcd8;color:#0f3638;border:none;border-radius:4px;"
    "padding:5px 12px;font-size:12px;}"
    "QPushButton:hover{background:#b5cac6;}"
)
BTN_ICON = (
    "QPushButton{background:#f3f0ec;color:#28251d;border:1px solid #d4d1ca;"
    "border-radius:4px;padding:5px 8px;font-size:12px;}"
    "QPushButton:hover{background:#edeae5;}"
)
BTN_DANGER = (
    "QPushButton{background:#e0ced7;color:#a12c7b;border:none;"
    "border-radius:4px;padding:5px 8px;font-size:12px;}"
    "QPushButton:hover{background:#d4b8c8;}"
)


class MainWindow(QMainWindow):
    new_results_signal = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nender — Мониторинг закупок ЕИС")
        self.setMinimumSize(960, 500)
        self.resize(1200, 680)

        self.scheduler = TenderScheduler(on_new_results=self._on_new_results)
        self.scheduler.start()
        self.new_results_signal.connect(self._show_new_results_badge)

        self._build_ui()
        self._load_profiles()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._load_profiles)
        self._timer.start(30_000)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Заголовок
        header = QHBoxLayout()
        title = QLabel("Поисковые профили")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        btn_settings = QPushButton("⚙️  Настройки")
        btn_settings.setStyleSheet(BTN_ICON)
        btn_settings.setFixedHeight(34)
        btn_settings.clicked.connect(self._open_settings)

        btn_log = QPushButton("📋  Журнал")
        btn_log.setStyleSheet(BTN_ICON)
        btn_log.setFixedHeight(34)
        btn_log.clicked.connect(self._open_log)

        btn_add = QPushButton("+  Добавить профиль")
        btn_add.setStyleSheet(BTN_PRIMARY)
        btn_add.setFixedHeight(34)
        btn_add.clicked.connect(self._add_profile)

        header.addWidget(btn_settings)
        header.addSpacing(6)
        header.addWidget(btn_log)
        header.addSpacing(6)
        header.addWidget(btn_add)
        layout.addLayout(header)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Название", "ИНН", "Регион",
            "Расписание", "Email", "Последняя проверка", "Действия"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 280)
        layout.addWidget(self.table)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Планировщик запущен")

    def _load_profiles(self):
        profiles = get_all_profiles()
        self.table.setRowCount(len(profiles))
        for row, p in enumerate(profiles):
            self.table.setRowHeight(row, 46)
            inn_str = ", ".join(p.get("inn_list", []))
            self.table.setItem(row, 0, QTableWidgetItem(p["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(inn_str or "—"))
            self.table.setItem(row, 2, QTableWidgetItem(p.get("region") or "—"))
            self.table.setItem(row, 3, QTableWidgetItem(p.get("schedule_time") or "08:00"))
            self.table.setItem(row, 4, QTableWidgetItem(p.get("email") or "—"))
            last_run = p.get("last_run_at") or "Не запускался"
            self.table.setItem(row, 5, QTableWidgetItem(last_run))

            if not p.get("is_active"):
                for col in range(6):
                    item = self.table.item(row, col)
                    if item:
                        item.setForeground(QColor("#bab9b4"))

            # --- Кнопки действий ---
            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(6, 4, 6, 4)
            al.setSpacing(5)

            btn_run = QPushButton("▶ Проверить")
            btn_run.setStyleSheet(BTN_PRIMARY)
            btn_run.setFixedHeight(32)
            btn_run.setMinimumWidth(90)
            btn_run.setToolTip("Запустить проверку сейчас")
            btn_run.clicked.connect(lambda _, pid=p["id"]: self._run_check(pid))

            btn_res = QPushButton("📄 Результаты")
            btn_res.setStyleSheet(BTN_SECONDARY)
            btn_res.setFixedHeight(32)
            btn_res.setMinimumWidth(100)
            btn_res.clicked.connect(lambda _, pid=p["id"], pn=p["name"]: self._show_results(pid, pn))

            btn_edit = QPushButton("✏️ Ред")
            btn_edit.setStyleSheet(BTN_ICON)
            btn_edit.setFixedHeight(32)
            btn_edit.setMinimumWidth(60)
            btn_edit.setToolTip("Редактировать")
            btn_edit.clicked.connect(lambda _, pid=p["id"]: self._edit_profile(pid))

            btn_del = QPushButton("🗑️")
            btn_del.setStyleSheet(BTN_DANGER)
            btn_del.setFixedHeight(32)
            btn_del.setFixedWidth(36)
            btn_del.setToolTip("Удалить профиль")
            btn_del.clicked.connect(lambda _, pid=p["id"], pn=p["name"]: self._delete_profile(pid, pn))

            al.addWidget(btn_run)
            al.addWidget(btn_res)
            al.addWidget(btn_edit)
            al.addWidget(btn_del)
            self.table.setCellWidget(row, 6, actions)

        if not profiles:
            self.status_bar.showMessage("Нет профилей. Нажмите «Добавить профиль».")

    def _add_profile(self):
        dlg = SearchFormDialog(self)
        if dlg.exec():
            self._load_profiles()

    def _edit_profile(self, profile_id):
        dlg = SearchFormDialog(self, profile_id=profile_id)
        if dlg.exec():
            self._load_profiles()

    def _delete_profile(self, profile_id, name):
        reply = QMessageBox.question(
            self, "Удалить профиль",
            f'Удалить «{name}»? Все результаты тоже будут удалены.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_profile(profile_id)
            self._load_profiles()

    def _run_check(self, profile_id):
        import threading
        self.status_bar.showMessage("Проверка запущена в фоне…")
        threading.Thread(target=self.scheduler.run_check, args=(profile_id,), daemon=True).start()
        QTimer.singleShot(8000, self._load_profiles)

    def _show_results(self, profile_id, profile_name):
        ResultsWindow(profile_id, profile_name, self).exec()

    def _open_settings(self):
        SettingsWindow(self).exec()

    def _open_log(self):
        LogWindow(self).exec()

    def _on_new_results(self, profile_id, count):
        self.new_results_signal.emit(profile_id, count)

    def _show_new_results_badge(self, profile_id, count):
        if count > 0:
            self.status_bar.showMessage(f"✅ Найдено {count} новых закупок по профилю #{profile_id}")
            self._load_profiles()

    def closeEvent(self, event):
        self.scheduler.stop()
        log("main", "Приложение закрыто")
        event.accept()
