"""Планировщик ежедневных проверок по всем активным поисковым профилям."""

import threading
import time
from datetime import datetime
from typing import Callable, Optional
from app.db import (
    get_all_profiles, get_profile,
    update_profile_last_run, update_profile_last_email,
    get_unsent_results, mark_results_sent,
    add_search_result, upsert_tender, log
)
from app.eis_client import EISClient
from app.filter_engine import apply_filters
from app.mailer import send_tender_digest


class TenderScheduler:
    """Планировщик ежедневных проверок закупок."""

    def __init__(self, on_new_results: Optional[Callable] = None):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.on_new_results = on_new_results
        self._last_checked: dict = {}

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log("scheduler", "Планировщик запущен")

    def stop(self):
        self._running = False
        log("scheduler", "Планировщик остановлен")

    def _loop(self):
        """Основной цикл: каждые 30 секунд проверяет расписание."""
        while self._running:
            now = datetime.now().strftime("%H:%M")
            try:
                profiles = get_all_profiles()
                for profile in profiles:
                    if not profile.get("is_active"):
                        continue
                    schedule_time = profile.get("schedule_time", "08:00")
                    last = self._last_checked.get(profile["id"])
                    if now == schedule_time and last != now:
                        self._last_checked[profile["id"]] = now
                        threading.Thread(
                            target=self.run_check,
                            args=(profile["id"],),
                            daemon=True
                        ).start()
            except Exception as e:
                log("scheduler", f"Ошибка в цикле планировщика: {e}", level="ERROR", details=str(e))
            time.sleep(30)

    def run_check(self, profile_id: int):
        """Запустить проверку для конкретного профиля."""
        profile = get_profile(profile_id)
        if not profile:
            return

        log("scheduler", f"Запуск проверки профиля: {profile['name']}")

        client = EISClient()
        client.reload_settings()

        try:
            raw_tenders = client.search_tenders(
                inn_list=profile.get("inn_list", []),
                region=profile.get("region"),
                city=profile.get("city"),
                keywords=profile.get("keywords", []),
            )
        except Exception as e:
            log("scheduler", f"Ошибка получения данных из ЕИС: {e}", level="ERROR", details=str(e))
            update_profile_last_run(profile_id)
            return

        filtered = apply_filters(raw_tenders, profile)
        log("scheduler",
            f"Профиль '{profile['name']}': получено {len(raw_tenders)}, "
            f"после фильтрации {len(filtered)}")

        new_count = 0
        for tender_data in filtered:
            tender_id = upsert_tender(tender_data)
            is_new = add_search_result(profile_id, tender_id)
            if is_new:
                new_count += 1

        update_profile_last_run(profile_id)

        unsent = get_unsent_results(profile_id)
        if unsent:
            ok, msg = send_tender_digest(
                to_email=profile["email"],
                profile_name=profile["name"],
                tenders=unsent
            )
            if ok:
                mark_results_sent(profile_id)
                update_profile_last_email(profile_id)
                log("scheduler",
                    f"Профиль '{profile['name']}': письмо отправлено, {len(unsent)} закупок")
            else:
                log("scheduler",
                    f"Профиль '{profile['name']}': ошибка отправки письма — {msg}",
                    level="ERROR")
        else:
            log("scheduler",
                f"Профиль '{profile['name']}': новых закупок нет, письмо не отправляется")

        if self.on_new_results:
            try:
                self.on_new_results(profile_id, new_count)
            except Exception:
                pass
