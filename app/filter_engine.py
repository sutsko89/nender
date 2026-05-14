"""Фильтрация закупок по параметрам поискового профиля."""

from typing import List, Dict


def apply_filters(tenders: List[Dict], profile: Dict) -> List[Dict]:
    """
    Применить фильтры профиля. Пропускает закупку если она удовлетворяет всем заполненным фильтрам.

    Логика фильтров:
    - Если ИНН задан — строгое совпадение (ИЛИ)
    - Если регион задан — подстрока без учёта регистра
    - Если город задан — подстрока в регионе/заказчике/названии
    - Если ключевые слова заданы — хотя бы одно (ИЛИ)
    - Если фильтров нет вовсе — пропускает всё
    """
    inn_list = [i.strip() for i in (profile.get("inn_list") or []) if i.strip()]
    region = (profile.get("region") or "").strip().lower()
    city = (profile.get("city") or "").strip().lower()
    keywords = [k.strip().lower() for k in (profile.get("keywords") or []) if k.strip()]

    # Если никаких фильтров — пропускаем всё
    if not inn_list and not region and not city and not keywords:
        return tenders

    return [t for t in tenders if _passes(t, inn_list, region, city, keywords)]


def _passes(tender: Dict, inn_list, region, city, keywords) -> bool:
    # Фильтр по ИНН (строгое совпадение)
    if inn_list:
        if (tender.get("customer_inn") or "").strip() not in inn_list:
            return False

    # Фильтр по региону (подстрока, без учёта регистра)
    # Важно: если регион пустой — не фильтруем по нему
    if region:
        tender_region = (tender.get("region") or "").lower()
        # Проверяем через подстроку или через начало названия
        # "хабаровский" совпадёт с "хабаровский край"
        if tender_region and region not in tender_region and tender_region not in region:
            return False
        # Если регион в закупке пустой — не отсеиваем (даём пройти)

    # Фильтр по городу
    if city:
        haystack = " ".join([
            tender.get("region") or "",
            tender.get("customer_name") or "",
            tender.get("title") or "",
        ]).lower()
        if city not in haystack:
            return False

    # Фильтр по ключевым словам
    if keywords:
        haystack = " ".join([
            tender.get("title") or "",
            tender.get("customer_name") or "",
            tender.get("region") or "",
            tender.get("status") or "",
        ]).lower()
        if not any(kw in haystack for kw in keywords):
            return False

    return True
