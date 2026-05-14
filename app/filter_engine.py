"""Модуль фильтрации закупок по параметрам поискового профиля."""

from typing import List, Dict


def apply_filters(tenders: List[Dict], profile: Dict) -> List[Dict]:
    """
    Применить фильтры профиля к списку закупок.

    Логика: закупка проходит, если она удовлетворяет ВСЕМ заполненным фильтрам.
    - ИНН: совпадение с одним из значений списка (ИЛИ)
    - Регион: совпадение подстроки
    - Город: совпадение подстроки в регионе, названии заказчика или теме
    - Ключевые слова: хотя бы одно слово найдено в тексте закупки (ИЛИ)
    """
    inn_list = [i.strip() for i in (profile.get("inn_list") or []) if i.strip()]
    region = (profile.get("region") or "").strip().lower()
    city = (profile.get("city") or "").strip().lower()
    keywords = [k.strip().lower() for k in (profile.get("keywords") or []) if k.strip()]

    result = []
    for tender in tenders:
        if _passes(tender, inn_list, region, city, keywords):
            result.append(tender)
    return result


def _passes(tender: Dict, inn_list: List[str], region: str, city: str, keywords: List[str]) -> bool:
    # Фильтр по ИНН
    if inn_list:
        customer_inn = (tender.get("customer_inn") or "").strip()
        if customer_inn not in inn_list:
            return False

    # Фильтр по региону
    if region:
        if region not in (tender.get("region") or "").lower():
            return False

    # Фильтр по городу (ищем в регионе, заказчике, названии)
    if city:
        searchable_city = " ".join([
            (tender.get("region") or ""),
            (tender.get("customer_name") or ""),
            (tender.get("title") or ""),
        ]).lower()
        if city not in searchable_city:
            return False

    # Фильтр по ключевым словам (подстрока, без учёта регистра)
    if keywords:
        searchable = " ".join([
            (tender.get("title") or ""),
            (tender.get("customer_name") or ""),
            (tender.get("region") or ""),
            (tender.get("status") or ""),
        ]).lower()
        if not any(kw in searchable for kw in keywords):
            return False

    return True
