"""Окно настроек подключения: ЕИС и SMTP."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout,
    QLineEdit, QSpinBox, QCheckBox, QPushButton, QLabel,
    QDialogButtonBox, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt
from app.db import get_settings, save_settings
from app.eis_client import EISClient
from app.mailer import send_tender_digest


class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(480)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        tabs = QTabWidget()

        # --- Вкладка ЕИС ---
        eis_tab = QWidget()
        eis_form = QFormLayout(eis_tab)
        eis_form.setSpacing(10)
        eis_form.setContentsMargins(12, 16, 12, 12)

        self.eis_url = QLineEdit()
        self.eis_url.setPlaceholderText("https://zakupki.gov.ru")
        eis_form.addRow("Базовый URL ЕИС:", self.eis_url)

        self.eis_login = QLineEdit()
        self.eis_login.setPlaceholderText("Логин от ЛК ЕИС")
        eis_form.addRow("Логин:", self.eis_login)

        self.eis_token = QLineEdit()
        self.eis_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.eis_token.setPlaceholderText("Токен доступа")
        eis_form.addRow("Токен API:", self.eis_token)

        btn_test_eis = QPushButton("🔗 Проверить подключение к ЕИС")
        btn_test_eis.setStyleSheet("background:#cedcd8;color:#0f3638;border-radius:4px;padding:7px;")
        btn_test_eis.clicked.connect(self._test_eis)
        eis_form.addRow("", btn_test_eis)

        note = QLabel(
            "Для получения токена зарегистрируйтесь как получатель данных\n"
            "на сайте zakupki.gov.ru (раздел «Сервисы отдачи информации»)."
        )
        note.setStyleSheet("color:#7a7974;font-size:11px;")
        eis_form.addRow("", note)
        tabs.addTab(eis_tab, "ЕИС")

        # --- Вкладка SMTP ---
        smtp_tab = QWidget()
        smtp_form = QFormLayout(smtp_tab)
        smtp_form.setSpacing(10)
        smtp_form.setContentsMargins(12, 16, 12, 12)

        self.smtp_host = QLineEdit()
        self.smtp_host.setPlaceholderText("smtp.yandex.ru")
        smtp_form.addRow("SMTP-хост:", self.smtp_host)

        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(465)
        smtp_form.addRow("Порт:", self.smtp_port)

        self.smtp_ssl = QCheckBox("Использовать SSL")
        self.smtp_ssl.setChecked(True)
        smtp_form.addRow("", self.smtp_ssl)

        self.smtp_login = QLineEdit()
        self.smtp_login.setPlaceholderText("your@yandex.ru")
        smtp_form.addRow("Логин:", self.smtp_login)

        self.smtp_password = QLineEdit()
        self.smtp_password.setEchoMode(QLineEdit.EchoMode.Password)
        smtp_form.addRow("Пароль / токен:", self.smtp_password)

        self.smtp_sender = QLineEdit()
        self.smtp_sender.setPlaceholderText("Оставьте пустым — будет использован логин")
        smtp_form.addRow("Адрес отправителя:", self.smtp_sender)

        self.smtp_test_to = QLineEdit()
        self.smtp_test_to.setPlaceholderText("Email для тестового письма")
        smtp_form.addRow("Тест — отправить на:", self.smtp_test_to)

        btn_test_smtp = QPushButton("✉ Отправить тестовое письмо")
        btn_test_smtp.setStyleSheet("background:#cedcd8;color:#0f3638;border-radius:4px;padding:7px;")
        btn_test_smtp.clicked.connect(self._test_smtp)
        smtp_form.addRow("", btn_test_smtp)
        tabs.addTab(smtp_tab, "Email (SMTP)")

        layout.addWidget(tabs)

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

    def _load(self):
        s = get_settings() or {}
        self.eis_url.setText(s.get("eis_base_url") or "https://zakupki.gov.ru")
        self.eis_login.setText(s.get("eis_login") or "")
        self.eis_token.setText(s.get("eis_token") or "")
        self.smtp_host.setText(s.get("smtp_host") or "")
        self.smtp_port.setValue(int(s.get("smtp_port") or 465))
        self.smtp_ssl.setChecked(bool(s.get("smtp_use_ssl", 1)))
        self.smtp_login.setText(s.get("smtp_login") or "")
        self.smtp_password.setText(s.get("smtp_password") or "")
        self.smtp_sender.setText(s.get("smtp_sender_email") or "")

    def _save(self):
        save_settings({
            "eis_base_url": self.eis_url.text().strip() or "https://zakupki.gov.ru",
            "eis_login": self.eis_login.text().strip(),
            "eis_token": self.eis_token.text().strip(),
            "smtp_host": self.smtp_host.text().strip(),
            "smtp_port": self.smtp_port.value(),
            "smtp_use_ssl": 1 if self.smtp_ssl.isChecked() else 0,
            "smtp_login": self.smtp_login.text().strip(),
            "smtp_password": self.smtp_password.text().strip(),
            "smtp_sender_email": self.smtp_sender.text().strip(),
        })
        QMessageBox.information(self, "Готово", "Настройки сохранены.")
        self.accept()

    def _test_eis(self):
        self._save_silent()
        client = EISClient()
        ok, msg = client.check_connection()
        if ok:
            QMessageBox.information(self, "ЕИС", f"✅ {msg}")
        else:
            QMessageBox.warning(self, "ЕИС", f"❌ {msg}")

    def _test_smtp(self):
        to = self.smtp_test_to.text().strip()
        if not to:
            QMessageBox.warning(self, "Ошибка", "Укажите email для тестового письма.")
            return
        self._save_silent()
        ok, msg = send_tender_digest(
            to_email=to,
            profile_name="Тестовый профиль",
            tenders=[{
                "title": "Тестовая закупка — проверка SMTP",
                "purchase_number": "0000000000000000001",
                "publish_date": "2026-01-01",
                "customer_name": "Тестовый заказчик",
                "region": "Хабаровский край",
                "status": "Подача заявок",
                "source_url": "https://zakupki.gov.ru",
            }]
        )
        if ok:
            QMessageBox.information(self, "SMTP", f"✅ {msg}")
        else:
            QMessageBox.warning(self, "SMTP", f"❌ {msg}")

    def _save_silent(self):
        save_settings({
            "eis_base_url": self.eis_url.text().strip() or "https://zakupki.gov.ru",
            "eis_login": self.eis_login.text().strip(),
            "eis_token": self.eis_token.text().strip(),
            "smtp_host": self.smtp_host.text().strip(),
            "smtp_port": self.smtp_port.value(),
            "smtp_use_ssl": 1 if self.smtp_ssl.isChecked() else 0,
            "smtp_login": self.smtp_login.text().strip(),
            "smtp_password": self.smtp_password.text().strip(),
            "smtp_sender_email": self.smtp_sender.text().strip(),
        })
