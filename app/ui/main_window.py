"""Главное окно приложения Nender."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel,
    QHeaderView, QMessageBox, QStatusBar, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from app.db import get_all_profiles, delete_profile, log
from app.scheduler import TenderScheduler
from app.ui.search_form import SearchFormDialog
from app.ui.results_window import ResultsWindow
from app.ui.settings_window import SettingsWindow
from app.ui.log_window import LogWindow


class MainWindow(QMainWindow):
    new_results_signal = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nender — Мониторинг закупок ЕИС")
        self.setMinimumSize(900, 550)
        self.resize(1100, 650)

        self.scheduler = TenderScheduler(on_new_results=self._on_new_results)
        self.scheduler.start()
        self.new_results_signal.connect(self._show_new_results_badge)

        self._build_ui()
        self._load_profiles()

        # Обновлять список каждые 30 секунд
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._load_profiles)
        self._timer.start(30_000)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Заголовок
        header = QHBoxLayout()
        title = QLabel("Поисковые профили")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        btn_add = QPushButton("＋ Добавить профиль")
        btn_add.clicked.connect(self._add_profile)
        btn_settings = QPushButton("⚙ Настройки")
        btn_settings.setProperty("class", "secondary")
        btn_settings.setStyleSheet("background:transparent;color:#01696f;border:1px solid #01696f;border-radius:4px;padding:7px 14px;")
        btn_settings.clicked.connect(self._open_settings)
        btn_log = QPushButton("📋 Журнал")
        btn_log.setStyleSheet("background:transparent;color:#7a7974;border:1px solid #d4d1ca;border-radius:4px;padding:7px 14px;")
        btn_log.clicked.connect(self._open_log)
        header.addWidget(btn_settings)
        header.addWidget(btn_log)
        header.addWidget(btn_add)
        layout.addLayout(header)

        # Таблица профилей
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Название", "ИНН компаний", "Регион", "Расписание",
            "Email", "Последняя проверка", "Действия"
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
        self.table.setColumnWidth(6, 230)
        self.table.setRowHeight(0, 44)
        layout.addWidget(self.table)

        # Статус-бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Планировщик запущен")

    def _load_profiles(self):
        profiles = get_all_profiles()
        self.table.setRowCount(len(profiles))
        for row, p in enumerate(profiles):
            self.table.setRowHeight(row, 44)
            inn_str = ", ".join(p.get("inn_list", []))
            self.table.setItem(row, 0, QTableWidgetItem(p["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(inn_str or "—"))
            self.table.setItem(row, 2, QTableWidgetItem(p.get("region") or "—"))
            self.table.setItem(row, 3, QTableWidgetItem(p.get("schedule_time") or "08:00"))
            self.table.setItem(row, 4, QTableWidgetItem(p.get("email") or "—"))
            last_run = p.get("last_run_at") or "Ещё не запускался"
            self.table.setItem(row, 5, QTableWidgetItem(last_run))

            # Активность
            if not p.get("is_active"):
                for col in range(6):
                    item = self.table.item(row, col)
                    if item:
                        item.setForeground(QColor("#bab9b4"))

            # Кнопки действий
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            btn_check = QPushButton("▶ Проверить")
            btn_check.setFixedHeight(30)
            btn_check.setToolTip("Запустить проверку прямо сейчас")
            btn_check.clicked.connect(lambda _, pid=p["id"]: self._run_check(pid))

            btn_results = QPushButton("📄 Результаты")
            btn_results.setFixedHeight(30)
            btn_results.setStyleSheet("background:#cedcd8;color:#0f3638;border-radius:4px;padding:0 8px;")
            btn_results.clicked.connect(lambda _, pid=p["id"], pname=p["name"]: self._show_results(pid, pname))

            btn_edit = QPushButton("✏")
            btn_edit.setFixedSize(30, 30)
            btn_edit.setToolTip("Редактировать")
            btn_edit.setStyleSheet("background:#f3f0ec;color:#28251d;border:1px solid #d4d1ca;border-radius:4px;")
            btn_edit.clicked.connect(lambda _, pid=p["id"]: self._edit_profile(pid))

            btn_del = QPushButton("✕")
            btn_del.setFixedSize(30, 30)
            btn_del.setToolTip("Удалить")
            btn_del.setStyleSheet("background:#e0ced7;color:#a12c7b;border:none;border-radius:4px;")
            btn_del.clicked.connect(lambda _, pid=p["id"], pname=p["name"]: self._delete_profile(pid, pname))

            actions_layout.addWidget(btn_check)
            actions_layout.addWidget(btn_results)
            actions_layout.addWidget(btn_edit)
            actions_layout.addWidget(btn_del)
            self.table.setCellWidget(row, 6, actions)

        if not profiles:
            self.status_bar.showMessage("Нет сохранённых профилей. Нажмите «Добавить профиль».")

    def _add_profile(self):
        dlg = SearchFormDialog(self)
        if dlg.exec():
            self._load_profiles()

    def _edit_profile(self, profile_id: int):
        dlg = SearchFormDialog(self, profile_id=profile_id)
        if dlg.exec():
            self._load_profiles()

    def _delete_profile(self, profile_id: int, name: str):
        reply = QMessageBox.question(
            self, "Удалить профиль",
            f'Удалить поисковый профиль «{name}»?\nВсе связанные результаты также будут удалены.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_profile(profile_id)
            self._load_profiles()

    def _run_check(self, profile_id: int):
        self.status_bar.showMessage("Запуск проверки...")
        import threading
        threading.Thread(
            target=self.scheduler.run_check,
            args=(profile_id,),
            daemon=True
        ).start()
        QTimer.singleShot(3000, self._load_profiles)
        self.status_bar.showMessage("Проверка запущена в фоне")

    def _show_results(self, profile_id: int, profile_name: str):
        dlg = ResultsWindow(profile_id, profile_name, self)
        dlg.exec()

    def _open_settings(self):
        dlg = SettingsWindow(self)
        dlg.exec()

    def _open_log(self):
        dlg = LogWindow(self)
        dlg.exec()

    def _on_new_results(self, profile_id: int, count: int):
        self.new_results_signal.emit(profile_id, count)

    def _show_new_results_badge(self, profile_id: int, count: int):
        if count > 0:
            self.status_bar.showMessage(
                f"✅ Найдено {count} новых закупок по профилю #{profile_id}"
            )
            self._load_profiles()

    def closeEvent(self, event):
        self.scheduler.stop()
        log("main", "Приложение закрыто")
        event.accept()
