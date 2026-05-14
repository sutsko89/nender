"""Точка входа в приложение Nender."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from app.db import init_db, log
from app.ui.main_window import MainWindow


def main():
    init_db()
    log("main", "Приложение запущено")

    app = QApplication(sys.argv)
    app.setApplicationName("Nender")
    app.setApplicationDisplayName("Nender — Мониторинг закупок ЕИС")
    app.setStyle("Fusion")

    # Базовый стиль
    app.setStyleSheet("""
        QMainWindow, QDialog, QWidget {
            background-color: #f7f6f2;
            color: #28251d;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
        }
        QTableWidget {
            border: 1px solid #d4d1ca;
            border-radius: 4px;
            gridline-color: #dcd9d5;
            background-color: #ffffff;
            alternate-background-color: #f9f8f5;
        }
        QTableWidget::item:selected {
            background-color: #cedcd8;
            color: #28251d;
        }
        QHeaderView::section {
            background-color: #01696f;
            color: #ffffff;
            padding: 6px 10px;
            border: none;
            font-weight: bold;
        }
        QPushButton {
            background-color: #01696f;
            color: #ffffff;
            border: none;
            border-radius: 4px;
            padding: 7px 18px;
            font-size: 13px;
        }
        QPushButton:hover { background-color: #0c4e54; }
        QPushButton:pressed { background-color: #0f3638; }
        QPushButton.secondary {
            background-color: transparent;
            color: #01696f;
            border: 1px solid #01696f;
        }
        QPushButton.secondary:hover { background-color: #cedcd8; }
        QPushButton.danger {
            background-color: #a12c7b;
            color: #ffffff;
        }
        QPushButton.danger:hover { background-color: #7d1e5e; }
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QTimeEdit {
            border: 1px solid #d4d1ca;
            border-radius: 4px;
            padding: 5px 8px;
            background-color: #ffffff;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
            border-color: #01696f;
        }
        QLabel { color: #28251d; }
        QLabel.muted { color: #7a7974; }
        QGroupBox {
            border: 1px solid #d4d1ca;
            border-radius: 6px;
            margin-top: 10px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: #01696f;
        }
        QTabWidget::pane { border: 1px solid #d4d1ca; border-radius: 4px; }
        QTabBar::tab {
            padding: 7px 18px;
            border: 1px solid #d4d1ca;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            background: #f3f0ec;
        }
        QTabBar::tab:selected { background: #ffffff; color: #01696f; font-weight: bold; }
        QStatusBar { background: #f3f0ec; color: #7a7974; }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
