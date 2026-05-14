"""Диалог создания и редактирования поискового профиля."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QPushButton, QLabel,
    QCheckBox, QTimeEdit, QDialogButtonBox, QMessageBox,
    QGroupBox, QComboBox, QHBoxLayout
)
from PySide6.QtCore import QTime
from app.db import get_profile, save_profile
from app.regions import REGION_NAMES, get_cities


class SearchFormDialog(QDialog):
    def __init__(self, parent=None, profile_id: int = None):
        super().__init__(parent)
        self.profile_id = profile_id
        self.setWindowTitle("Редактировать профиль" if profile_id else "Новый поисковый профиль")
        self.setMinimumWidth(540)
        self.setMinimumHeight(580)
        self._build_ui()
        if profile_id:
            self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # --- Основное ---
        grp_main = QGroupBox("Основное")
        form_main = QFormLayout(grp_main)
        form_main.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: Газпром — хабаровск")
        form_main.addRow("Название *:", self.name_edit)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("user@example.com")
        form_main.addRow("Email *:", self.email_edit)

        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime(8, 0))
        form_main.addRow("Время проверки:", self.time_edit)

        self.active_check = QCheckBox("Профиль активен")
        self.active_check.setChecked(True)
        form_main.addRow("", self.active_check)
        layout.addWidget(grp_main)

        # --- Фильтры ---
        grp_filters = QGroupBox("Фильтры поиска")
        form_f = QFormLayout(grp_filters)
        form_f.setSpacing(10)

        self.inn_edit = QTextEdit()
        self.inn_edit.setFixedHeight(70)
        self.inn_edit.setPlaceholderText("Каждый ИНН с новой строки:\n7736153559\n5035018415")
        form_f.addRow("ИНН заказчиков:", self.inn_edit)

        # Регион — выпадающий список
        self.region_combo = QComboBox()
        self.region_combo.setEditable(True)  # можно печатать для фильтрации
        self.region_combo.addItems(REGION_NAMES)
        self.region_combo.setCurrentIndex(0)
        self.region_combo.currentTextChanged.connect(self._on_region_changed)
        form_f.addRow("Регион:", self.region_combo)

        # Город — зависит от региона
        self.city_combo = QComboBox()
        self.city_combo.setEditable(True)
        self.city_combo.addItem("")
        self.city_combo.setEnabled(False)
        form_f.addRow("Город:", self.city_combo)

        self.keywords_edit = QTextEdit()
        self.keywords_edit.setFixedHeight(70)
        self.keywords_edit.setPlaceholderText("Каждое ключевое слово с новой строки:\nметаллоконструкции\nсварка")
        form_f.addRow("Ключевые слова:", self.keywords_edit)
        layout.addWidget(grp_filters)

        # --- Кнопки ---
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

    def _on_region_changed(self, region_name: str):
        """Обновить список городов при смене региона."""
        cities = get_cities(region_name)
        self.city_combo.clear()
        self.city_combo.addItems(cities)
        self.city_combo.setCurrentIndex(0)
        self.city_combo.setEnabled(len(cities) > 1)

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

        # Регион
        region = p.get("region") or ""
        idx = self.region_combo.findText(region)
        if idx >= 0:
            self.region_combo.setCurrentIndex(idx)
        else:
            self.region_combo.setCurrentText(region)

        # Город (после смены региона список уже обновился)
        city = p.get("city") or ""
        city_idx = self.city_combo.findText(city)
        if city_idx >= 0:
            self.city_combo.setCurrentIndex(city_idx)
        else:
            self.city_combo.setCurrentText(city)

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

        inn_list = [l.strip() for l in self.inn_edit.toPlainText().splitlines() if l.strip()]
        keywords = [l.strip() for l in self.keywords_edit.toPlainText().splitlines() if l.strip()]

        data = {
            "name": name,
            "email": email,
            "schedule_time": self.time_edit.time().toString("HH:mm"),
            "is_active": 1 if self.active_check.isChecked() else 0,
            "inn_list": inn_list,
            "region": self.region_combo.currentText().strip(),
            "city": self.city_combo.currentText().strip(),
            "keywords": keywords,
        }
        if self.profile_id:
            data["id"] = self.profile_id

        save_profile(data)
        self.accept()
