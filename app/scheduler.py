"""Планировщик ежедневных проверок."""

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
from app.eis_client import EISClient, fetch_rss_tenders
from app.filter_engine import apply_filters
from app.mailer import send_tender_digest


class TenderScheduler:

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
        while self._running:
            now = datetime.now().strftime("%H:%M")
            try:
                for profile in get_all_profiles():
                    if not profile.get("is_active"):
                        continue
                    sched = profile.get("schedule_time", "08:00")
                    if now == sched and self._last_checked.get(profile["id"]) != now:
                        self._last_checked[profile["id"]] = now
                        threading.Thread(
                            target=self.run_check, args=(profile["id"],), daemon=True
                        ).start()
            except Exception as e:
                log("scheduler", f"Ошибка цикла: {e}", level="ERROR")
            time.sleep(30)

    def run_check(self, profile_id: int):
        profile = get_profile(profile_id)
        if not profile:
            return

        log("scheduler", f"Запуск проверки профиля: {profile['name']}")

        inn_list = profile.get("inn_list", [])
        keywords = profile.get("keywords", [])
        region = profile.get("region") or ""
        city = profile.get("city") or ""

        raw_tenders = []

        # Путь 1: HTML-поиск (по ИНН или по ключевым словам)
        if inn_list or keywords:
            try:
                client = EISClient()
                raw_tenders = client.search_tenders(
                    inn_list=inn_list,
                    region=region,
                    city=city,
                    keywords=keywords,
                )
            except Exception as e:
                log("scheduler", f"Ошибка HTML-поиска: {e}", level="ERROR")

        # Путь 2: RSS-резерв — если HTML дал ноль и есть ключевые слова
        if not raw_tenders and keywords:
            log("scheduler", "Переключаюсь на RSS-поиск")
            seen = set()
            for kw in keywords:
                for t in fetch_rss_tenders(kw, region=region or None):
                    if t["external_id"] not in seen:
                        seen.add(t["external_id"])
                        raw_tenders.append(t)
                time.sleep(1)

        # Применяем фильтры только по региону/городу/ИНН
        # Ключевые слова НЕ перефильтровываем — ЕИС уже выполнил морфологический поиск
        filtered = apply_filters(raw_tenders, profile)

        log(
            "scheduler",
            f"Профиль '{profile['name']}': "
            f"получено {len(raw_tenders)}, после фильтрации {len(filtered)}"
        )

        new_count = 0
        for tender_data in filtered:
            tender_id = upsert_tender(tender_data)
            if add_search_result(profile_id, tender_id):
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
                log("scheduler", f"Письмо отправлено, {len(unsent)} закупок")
            else:
                log("scheduler", f"Ошибка отправки: {msg}", level="ERROR")
        else:
            log("scheduler", f"Профиль '{profile['name']}': новых закупок нет, письмо не отправляется")

        if self.on_new_results:
            try:
                self.on_new_results(profile_id, new_count)
            except Exception:
                pass
