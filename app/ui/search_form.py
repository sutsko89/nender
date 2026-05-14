"""Диалог создания и редактирования поискового профиля."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QPushButton, QLabel,
    QCheckBox, QTimeEdit, QDialogButtonBox, QMessageBox,
    QGroupBox, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, QTime
from app.db import get_profile, save_profile


class SearchFormDialog(QDialog):
    def __init__(self, parent=None, profile_id: int = None):
        super().__init__(parent)
        self.profile_id = profile_id
        self.setWindowTitle("Редактировать профиль" if profile_id else "Новый поисковый профиль")
        self.setMinimumWidth(520)
        self.setMinimumHeight(560)
        self._build_ui()
        if profile_id:
            self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Название
        grp_main = QGroupBox("Основное")
        form_main = QFormLayout(grp_main)
        form_main.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: Газпром — Хабаровск")
        form_main.addRow("Название профиля *:", self.name_edit)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("user@example.com")
        form_main.addRow("Email для отчётов *:", self.email_edit)

        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime(8, 0))
        form_main.addRow("Время проверки:", self.time_edit)

        self.active_check = QCheckBox("Профиль активен")
        self.active_check.setChecked(True)
        form_main.addRow("", self.active_check)
        layout.addWidget(grp_main)

        # Фильтры
        grp_filters = QGroupBox("Фильтры поиска")
        form_filters = QFormLayout(grp_filters)
        form_filters.setSpacing(10)

        self.inn_edit = QTextEdit()
        self.inn_edit.setFixedHeight(70)
        self.inn_edit.setPlaceholderText("Каждый ИНН с новой строки:\n7736153559\n5035018415")
        form_filters.addRow("ИНН заказчиков:", self.inn_edit)

        self.region_edit = QLineEdit()
        self.region_edit.setPlaceholderText("Например: Хабаровский")
        form_filters.addRow("Регион (подстрока):", self.region_edit)

        self.city_edit = QLineEdit()
        self.city_edit.setPlaceholderText("Например: Хабаровск")
        form_filters.addRow("Город:", self.city_edit)

        self.keywords_edit = QTextEdit()
        self.keywords_edit.setFixedHeight(70)
        self.keywords_edit.setPlaceholderText("Каждое ключевое слово с новой строки:\nметаллоконструкции\nсварка")
        form_filters.addRow("Ключевые слова:", self.keywords_edit)
        layout.addWidget(grp_filters)

        # Кнопки
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Save).setText("💾 Сохранить")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setStyleSheet(
            "background:transparent;color:#7a7974;border:1px solid #d4d1ca;"
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load_data(self):
        p = get_profile(self.profile_id)
        if not p:
            return
        self.name_edit.setText(p.get("name", ""))
        self.email_edit.setText(p.get("email", ""))
        t = p.get("schedule_time", "08:00").split(":")
        self.time_edit.setTime(QTime(int(t[0]), int(t[1])))
        self.active_check.setChecked(bool(p.get("is_active", 1)))
        self.inn_edit.setPlainText("\n".join(p.get("inn_list", [])))
        self.region_edit.setText(p.get("region") or "")
        self.city_edit.setText(p.get("city") or "")
        self.keywords_edit.setPlainText("\n".join(p.get("keywords", [])))

    def _save(self):
        name = self.name_edit.text().strip()
        email = self.email_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Укажите название профиля.")
            return
        if not email or "@" not in email:
            QMessageBox.warning(self, "Ошибка", "Укажите корректный email.")
            return

        inn_list = [
            line.strip() for line in self.inn_edit.toPlainText().splitlines()
            if line.strip()
        ]
        keywords = [
            line.strip() for line in self.keywords_edit.toPlainText().splitlines()
            if line.strip()
        ]

        data = {
            "name": name,
            "email": email,
            "schedule_time": self.time_edit.time().toString("HH:mm"),
            "is_active": 1 if self.active_check.isChecked() else 0,
            "inn_list": inn_list,
            "region": self.region_edit.text().strip(),
            "city": self.city_edit.text().strip(),
            "keywords": keywords,
        }
        if self.profile_id:
            data["id"] = self.profile_id

        save_profile(data)
        self.accept()
