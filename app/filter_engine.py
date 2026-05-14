"""Фильтрация закупок по параметрам поискового профиля.

Логика:
- ЕИС уже выполнил морфологический поиск по ключевым словам и/или ИНН.
- Мы фильтруем дополнительно только по региону/городу и ИНН —
  не по ключевым словам, чтобы не обрезать морфологические вариаты.
"""

from typing import List, Dict


def apply_filters(tenders: List[Dict], profile: Dict) -> List[Dict]:
    """
    Фильтрация после загрузки с ЕИС.

    Фильтры применяются ТОЛЬКО:
      - регион (если задан) — двусторонняя подстрока
      - город (если задан) — подстрока в тексте
      - ИНН (если задан) — строгое совпадение

    Ключевые слова НЕ применяются как постфильтр — ЕИС уже сделал
    морфологический поиск, и повторная фильтрация обрежет морфологические варианты.
    """
    inn_list = [i.strip() for i in (profile.get("inn_list") or []) if i.strip()]
    region = (profile.get("region") or "").strip().lower()
    city = (profile.get("city") or "").strip().lower()

    # Если нет ни одного фильтра — пропускаем всё
    if not inn_list and not region and not city:
        return tenders

    return [t for t in tenders if _passes(t, inn_list, region, city)]


def _passes(tender: Dict, inn_list: list, region: str, city: str) -> bool:
    # Фильтр по ИНН (строгое совпадение)
    if inn_list:
        if (tender.get("customer_inn") or "").strip() not in inn_list:
            return False

    # Фильтр по региону (двусторонная подстрока)
    # "хабаровский" совпадёт с "хабаровский край" и наоборот
    if region:
        tender_region = (tender.get("region") or "").lower()
        if tender_region:
            if region not in tender_region and tender_region not in region:
                return False
        # если регион в закупке пустой — даём пройти (еИС уже отфильтровал)

    # Фильтр по городу
    if city:
        haystack = " ".join([
            tender.get("region") or "",
            tender.get("customer_name") or "",
            tender.get("title") or "",
        ]).lower()
        if city not in haystack:
            return False

    return True
