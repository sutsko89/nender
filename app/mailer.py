"""Модуль отправки email-рассылки о новых закупках."""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
from datetime import datetime
from app.db import log, get_settings


def send_tender_digest(
    to_email: str,
    profile_name: str,
    tenders: List[Dict],
    settings: Optional[Dict] = None
) -> tuple:
    """
    Отправить письмо с перечнем новых закупок.
    Возвращает (успех, сообщение).
    """
    if not tenders:
        return True, "Нет новых закупок — письмо не отправляется"

    if settings is None:
        settings = get_settings() or {}

    smtp_host = settings.get("smtp_host", "")
    smtp_port = int(settings.get("smtp_port") or 465)
    smtp_use_ssl = bool(settings.get("smtp_use_ssl", 1))
    smtp_login = settings.get("smtp_login", "")
    smtp_password = settings.get("smtp_password", "")
    sender = settings.get("smtp_sender_email") or smtp_login

    if not smtp_host or not smtp_login or not smtp_password:
        msg = "SMTP не настроен. Укажите параметры в настройках приложения."
        log("mailer", msg, level="ERROR")
        return False, msg

    subject = (
        f"[Nender] {profile_name}: {len(tenders)} новых закупок — "
        f"{datetime.now().strftime('%d.%m.%Y')}"
    )

    mime_msg = MIMEMultipart("alternative")
    mime_msg["Subject"] = subject
    mime_msg["From"] = sender
    mime_msg["To"] = to_email
    mime_msg.attach(MIMEText(_build_text(profile_name, tenders), "plain", "utf-8"))
    mime_msg.attach(MIMEText(_build_html(profile_name, tenders), "html", "utf-8"))

    try:
        if smtp_use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=15) as server:
                server.login(smtp_login, smtp_password)
                server.sendmail(sender, to_email, mime_msg.as_bytes())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_login, smtp_password)
                server.sendmail(sender, to_email, mime_msg.as_bytes())

        log("mailer", f"Письмо отправлено на {to_email}: {len(tenders)} закупок по поиску '{profile_name}'")
        return True, "Письмо успешно отправлено"

    except smtplib.SMTPAuthenticationError:
        msg = "Ошибка авторизации SMTP. Проверьте логин и пароль."
        log("mailer", msg, level="ERROR")
        return False, msg
    except smtplib.SMTPException as e:
        msg = f"Ошибка SMTP: {e}"
        log("mailer", msg, level="ERROR", details=str(e))
        return False, msg
    except Exception as e:
        msg = f"Ошибка отправки письма: {e}"
        log("mailer", msg, level="ERROR", details=str(e))
        return False, msg


def _build_text(profile_name: str, tenders: List[Dict]) -> str:
    lines = [
        f"Поиск: {profile_name}",
        f"Дата проверки: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        f"Новых закупок: {len(tenders)}",
        "",
        "=" * 60,
    ]
    for i, t in enumerate(tenders, 1):
        lines += [
            f"{i}. {t.get('title', '—')}",
            f"   Номер: {t.get('purchase_number', '—')}",
            f"   Дата публикации: {t.get('publish_date', '—')}",
            f"   Заказчик: {t.get('customer_name', '—')}",
            f"   Регион: {t.get('region', '—')}",
            f"   Статус: {t.get('status', '—')}",
            f"   Ссылка: {t.get('source_url', '—')}",
            "",
        ]
    return "\n".join(lines)


def _build_html(profile_name: str, tenders: List[Dict]) -> str:
    rows = ""
    for i, t in enumerate(tenders, 1):
        url = t.get("source_url", "")
        link = f'<a href="{url}" style="color:#01696f;">Открыть</a>' if url else "—"
        bg = "#f9f9f9" if i % 2 == 0 else "#ffffff"
        rows += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:8px 12px;border:1px solid #e0e0e0;">{i}</td>'
            f'<td style="padding:8px 12px;border:1px solid #e0e0e0;">{t.get("title", "—")}</td>'
            f'<td style="padding:8px 12px;border:1px solid #e0e0e0;">{t.get("purchase_number", "—")}</td>'
            f'<td style="padding:8px 12px;border:1px solid #e0e0e0;">{t.get("publish_date", "—")}</td>'
            f'<td style="padding:8px 12px;border:1px solid #e0e0e0;">{t.get("customer_name", "—")}</td>'
            f'<td style="padding:8px 12px;border:1px solid #e0e0e0;">{t.get("region", "—")}</td>'
            f'<td style="padding:8px 12px;border:1px solid #e0e0e0;">{link}</td>'
            f'</tr>'
        )
    return (
        '<html><body style="font-family:Arial,sans-serif;color:#333;max-width:1000px;margin:0 auto;">'
        '<h2 style="color:#01696f;border-bottom:2px solid #01696f;padding-bottom:8px;">'
        'Nender — новые закупки</h2>'
        f'<p><b>Поиск:</b> {profile_name}</p>'
        f'<p><b>Дата проверки:</b> {datetime.now().strftime("%d.%m.%Y %H:%M")}</p>'
        f'<p><b>Новых закупок:</b> {len(tenders)}</p>'
        '<table style="border-collapse:collapse;width:100%;font-size:13px;margin-top:12px;">'
        '<thead><tr style="background:#01696f;color:#fff;">'
        '<th style="padding:10px 12px;">#</th>'
        '<th style="padding:10px 12px;">Наименование</th>'
        '<th style="padding:10px 12px;">Номер</th>'
        '<th style="padding:10px 12px;">Дата публ.</th>'
        '<th style="padding:10px 12px;">Заказчик</th>'
        '<th style="padding:10px 12px;">Регион</th>'
        '<th style="padding:10px 12px;">Ссылка</th>'
        '</tr></thead>'
        f'<tbody>{rows}</tbody></table>'
        '<p style="color:#999;font-size:11px;margin-top:20px;">'
        'Письмо сформировано автоматически приложением Nender.</p>'
        '</body></html>'
    )
