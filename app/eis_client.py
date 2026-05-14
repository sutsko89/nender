"""Модуль получения закупок с ЕИС без авторизации.

Публичный поиск (не требует логина и токена):
  https://zakupki.gov.ru/epz/order/extendedsearch/results.html

Параметры URL:
  searchString     — ключевые слова
  morphology       — on (морфология)
  pageNumber       — номер страницы
  recordsPerPage   — _10 / _20 / _50
  sortBy           — UPDATE_DATE
  sortDirection    — false (по убыванию)
  fz44             — on (включить 44-ФЗ)
  fz223            — on (включить 223-ФЗ)
  customerPlace    — название региона (русским)
  customerInn      — ИНН заказчика
  publishDateFrom  — дата от (DD.MM.YYYY)
  publishDateTo    — дата до (DD.MM.YYYY)

RSS-поток (XML, до последних 100 записей без авторизации):
  https://zakupki.gov.ru/epz/order/extendedsearch/rss
"""

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from app.db import log, get_settings

BASE_URL = "https://zakupki.gov.ru"
SEARCH_URL = BASE_URL + "/epz/order/extendedsearch/results.html"
RSS_URL = BASE_URL + "/epz/order/extendedsearch/rss"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class EISClient:
    """Клиент публичного поиска ЕИС без авторизации."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def reload_settings(self):
        """API-совместимость с интерфейсом главного окна (заготовка)."""
        pass

    def check_connection(self) -> tuple:
        """Проверить доступность публичного поиска ЕИС."""
        try:
            resp = self.session.get(
                BASE_URL + "/epz/main/public/home.html", timeout=15
            )
            if resp.status_code == 200:
                return True, "Сайт ЕИС доступен"
            return False, f"Сервер вернул код {resp.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Нет подключения к интернету"
        except requests.exceptions.Timeout:
            return False, "Таймаут подключения"
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------------
    # Главный метод: поиск по профилю
    # ------------------------------------------------------------------

    def search_tenders(
        self,
        inn_list: List[str],
        region: Optional[str] = None,
        city: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> List[Dict]:
        """
        Получить закупки через публичный поиск ЕИС.

        Стратегия:
          1. Если есть ИНН — делаем отдельный запрос по каждому ИНН
          2. Если есть ключевые слова без ИНН — поиск по каждому слову
          3. Далее фильтрация по региону/городу через filter_engine
        """
        if not date_from:
            date_from = (datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y")
        if not date_to:
            date_to = datetime.now().strftime("%d.%m.%Y")

        all_tenders: List[Dict] = []
        seen_ids: set = set()

        # По ИНН
        if inn_list:
            for inn in inn_list:
                tenders = self._search_by_inn(
                    inn=inn,
                    region=region,
                    keywords=keywords,
                    date_from=date_from,
                    date_to=date_to,
                    page=page,
                    page_size=page_size,
                )
                for t in tenders:
                    if t["external_id"] not in seen_ids:
                        seen_ids.add(t["external_id"])
                        all_tenders.append(t)
                time.sleep(1)  # вежливость

        # По ключевым словам (если есть и нет ИНН, или хотят дополнить)
        if keywords and not inn_list:
            for kw in keywords:
                tenders = self._search_by_keyword(
                    keyword=kw,
                    region=region,
                    date_from=date_from,
                    date_to=date_to,
                    page=page,
                    page_size=page_size,
                )
                for t in tenders:
                    if t["external_id"] not in seen_ids:
                        seen_ids.add(t["external_id"])
                        all_tenders.append(t)
                time.sleep(1)

        log(
            "eis_client",
            f"Итого получено {len(all_tenders)} закупок"
            f" (ИНН: {inn_list}, регион: {region}, ключи: {keywords})",
        )
        return all_tenders

    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------

    def _search_by_inn(
        self,
        inn: str,
        region: Optional[str],
        keywords: Optional[List[str]],
        date_from: str,
        date_to: str,
        page: int,
        page_size: int,
    ) -> List[Dict]:
        """HTML-парсинг результатов по ИНН заказчика."""
        params = {
            "searchString": " ".join(keywords) if keywords else inn,
            "morphology": "on",
            "search-filter": "Дате размещения",
            "pageNumber": str(page),
            "sortDirection": "false",
            "recordsPerPage": f"_{min(page_size, 50)}",
            "showLotsInfoHidden": "false",
            "sortBy": "UPDATE_DATE",
            "fz44": "on",
            "fz223": "on",
            "af": "on",
            "ca": "on",
            "pc": "on",
            "pa": "on",
            "currencyIdGeneral": "-1",
            "customerInn": inn,
            "publishDateFrom": date_from,
            "publishDateTo": date_to,
        }
        if region:
            params["customerPlace"] = region

        return self._fetch_html_results(params, context=f"INN={inn}")

    def _search_by_keyword(
        self,
        keyword: str,
        region: Optional[str],
        date_from: str,
        date_to: str,
        page: int,
        page_size: int,
    ) -> List[Dict]:
        """HTML-парсинг результатов по ключевому слову."""
        params = {
            "searchString": keyword,
            "morphology": "on",
            "search-filter": "Дате размещения",
            "pageNumber": str(page),
            "sortDirection": "false",
            "recordsPerPage": f"_{min(page_size, 50)}",
            "showLotsInfoHidden": "false",
            "sortBy": "UPDATE_DATE",
            "fz44": "on",
            "fz223": "on",
            "af": "on",
            "ca": "on",
            "pc": "on",
            "pa": "on",
            "currencyIdGeneral": "-1",
            "publishDateFrom": date_from,
            "publishDateTo": date_to,
        }
        if region:
            params["customerPlace"] = region

        return self._fetch_html_results(params, context=f"keyword={keyword}")

    def _fetch_html_results(self, params: dict, context: str = "") -> List[Dict]:
        """HTML-запрос к странице результатов и парсинг таблицы."""
        try:
            resp = self.session.get(SEARCH_URL, params=params, timeout=30)
            resp.raise_for_status()
            tenders = self._parse_html(resp.text)
            log("eis_client", f"Парсинг [{context}]: {len(tenders)} записей")
            return tenders
        except requests.exceptions.HTTPError as e:
            log("eis_client", f"HTTP-ошибка [{context}]: {e}", level="ERROR")
            return []
        except requests.exceptions.ConnectionError as e:
            log("eis_client", f"Нет соединения [{context}]: {e}", level="ERROR")
            return []
        except Exception as e:
            log("eis_client", f"Ошибка [{context}]: {e}", level="ERROR", details=str(e))
            return []

    # ------------------------------------------------------------------
    # Парсинг HTML
    # ------------------------------------------------------------------

    def _parse_html(self, html: str) -> List[Dict]:
        """Извлечь закупки из HTML-страницы результатов единого стиля."""
        soup = BeautifulSoup(html, "html.parser")
        tenders = []

        # Каждая закупка — блок .registry-entry__form
        cards = soup.select(".registry-entry__form, .search-registry-entry-block")
        if not cards:
            # запасной вариант
            cards = soup.select("div[class*='registry-entry']") or soup.select(".order-row")

        for card in cards:
            try:
                tender = self._parse_card(card)
                if tender and tender.get("external_id"):
                    tenders.append(tender)
            except Exception as e:
                log("eis_client", f"Ошибка парсинга карточки: {e}", level="WARNING")

        return tenders

    def _parse_card(self, card) -> Optional[Dict]:
        """Извлечь данные из одной карточки закупки."""
        # Номер закупки
        number_el = (
            card.select_one(".registry-entry__header-mid__number a") or
            card.select_one(".title a") or
            card.select_one("a[href*='regNumber']") or
            card.select_one("a[href*='notice']") or
            card.select_one(".lot-number")
        )
        if not number_el:
            return None

        purchase_number = number_el.get_text(strip=True)
        source_url = number_el.get("href", "")
        if source_url and not source_url.startswith("http"):
            source_url = BASE_URL + source_url

        # ID — извлекаем из URL или из номера
        external_id = purchase_number
        m = re.search(r"regNumber=([\w-]+)", source_url)
        if m:
            external_id = m.group(1)

        # Название закупки
        title_el = (
            card.select_one(".registry-entry__body-value") or
            card.select_one(".subject-name") or
            card.select_one(".lot-subject")
        )
        title = title_el.get_text(strip=True) if title_el else purchase_number

        # Заказчик
        customer_el = (
            card.select_one(".registry-entry__body-href a") or
            card.select_one(".customer-name a") or
            card.select_one(".org-name")
        )
        customer_name = customer_el.get_text(strip=True) if customer_el else ""

        # ИНН заказчика — попытаемся извлечь из доп. значений
        customer_inn = ""
        for el in card.select(".registry-entry__body-value"):
            text = el.get_text(strip=True)
            if re.match(r"^\d{10}$|^\d{12}$", text):
                customer_inn = text
                break

        # Дата публикации
        date_el = (
            card.select_one(".data-block__value") or
            card.select_one(".publish-date")
        )
        publish_date = ""
        if date_el:
            raw_date = date_el.get_text(strip=True)
            publish_date = self._normalize_date(raw_date)

        # Регион
        region_el = card.select_one(".registry-entry__body-value:last-of-type")
        region = region_el.get_text(strip=True) if region_el else ""

        # Статус
        status_el = (
            card.select_one(".registry-entry__header-top__title") or
            card.select_one(".purchase-status")
        )
        status = status_el.get_text(strip=True) if status_el else ""

        return {
            "external_id": external_id,
            "purchase_number": purchase_number,
            "title": title,
            "publish_date": publish_date,
            "region": region,
            "customer_name": customer_name,
            "customer_inn": customer_inn,
            "status": status,
            "source_url": source_url,
            "raw_payload": {},
        }

    @staticmethod
    def _normalize_date(raw: str) -> str:
        """Привести дату еИС к формату YYYY-MM-DD."""
        raw = raw.strip()
        # DD.MM.YYYY HH:MM или DD.MM.YYYY
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", raw)
        if m:
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        return raw


# ------------------------------------------------------------------
# RSS-альтернатива (используется для быстрой проверки по ключевым словам)
# ------------------------------------------------------------------

def fetch_rss_tenders(keyword: str, region: Optional[str] = None) -> List[Dict]:
    """
    Быстрый путь: запрос RSS-потока ЕИС без авторизации.
    Возвращает до 100 последних закупок в формате словарей.
    """
    params = {
        "searchString": keyword,
        "morphology": "on",
        "sortBy": "UPDATE_DATE",
        "sortDirection": "false",
        "recordsPerPage": "_50",
        "fz44": "on",
        "fz223": "on",
    }
    if region:
        params["customerPlace"] = region

    try:
        resp = requests.get(
            RSS_URL, params=params, headers=HEADERS, timeout=20
        )
        resp.raise_for_status()
        return _parse_rss(resp.text)
    except Exception as e:
        log("eis_client", f"RSS-ошибка [{keyword}]: {e}", level="ERROR")
        return []


def _parse_rss(xml_text: str) -> List[Dict]:
    """Парсинг RSS/XML ответа еИС."""
    tenders = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        channel = root.find("channel")
        if channel is None:
            return []
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description = (item.findtext("description") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()

            # external_id — из ссылки
            external_id = link
            m = re.search(r"regNumber=([\w-]+)", link)
            if m:
                external_id = m.group(1)

            # Дата
            publish_date = ""
            dm = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", pub_date)
            if dm:
                publish_date = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}"

            if external_id:
                tenders.append({
                    "external_id": external_id,
                    "purchase_number": external_id,
                    "title": title,
                    "publish_date": publish_date,
                    "region": "",
                    "customer_name": "",
                    "customer_inn": "",
                    "status": "",
                    "source_url": link,
                    "raw_payload": {"description": description},
                })
    except ET.ParseError as e:
        log("eis_client", f"Ошибка парсинга RSS: {e}", level="ERROR")
    return tenders
