"""Модуль получения закупок с ЕИС.

Структура HTML-карточки (2025-2026):

  .registry-entry__header-top__title       <- Тип (ФЗ, вид процедуры)
  .registry-entry__header-mid__number a   <- номер + ссылка
  .registry-entry__header-mid__title      <- статус ("Закупка завершена")

  .registry-entry__body-block (1-й):
    .registry-entry__body-title = "Объект закупки"
    .registry-entry__body-value             <- название (внутри может быть <span.highlightColor>)

  .registry-entry__body-block (2-й):
    .registry-entry__body-title = "Заказчик"
    .registry-entry__body-href a            <- название орг, href содержит inn=...

  .price-block__value                      <- цена
  .data-block__value (первый)             <- дата размещения

  Регион в карточке НЕ указан. Фильтрация по региону
  выполняется на стороне ЕИС (параметр customerPlace).
"""

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from app.db import log

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
    "Referer": "https://zakupki.gov.ru/epz/main/public/home.html",
}

DEFAULT_DAYS_BACK = 7


class EISClient:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def check_connection(self) -> tuple:
        try:
            resp = self.session.get(BASE_URL + "/epz/main/public/home.html", timeout=15)
            if resp.status_code == 200:
                return True, "Сайт ЕИС доступен"
            return False, f"Сервер вернул код {resp.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Нет подключения к интернету"
        except requests.exceptions.Timeout:
            return False, "Таймаут подключения"
        except Exception as e:
            return False, str(e)

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
        if not date_from:
            date_from = (datetime.now() - timedelta(days=DEFAULT_DAYS_BACK)).strftime("%d.%m.%Y")
        if not date_to:
            date_to = datetime.now().strftime("%d.%m.%Y")

        all_tenders: List[Dict] = []
        seen_ids: set = set()

        if inn_list:
            for inn in inn_list:
                tenders = self._search_by_inn(
                    inn=inn, region=region, keywords=keywords,
                    date_from=date_from, date_to=date_to,
                    page=page, page_size=page_size,
                )
                for t in tenders:
                    if t["external_id"] not in seen_ids:
                        seen_ids.add(t["external_id"])
                        all_tenders.append(t)
                time.sleep(1)

        if keywords and not inn_list:
            for kw in keywords:
                tenders = self._search_by_keyword(
                    keyword=kw, region=region,
                    date_from=date_from, date_to=date_to,
                    page=page, page_size=page_size,
                )
                for t in tenders:
                    if t["external_id"] not in seen_ids:
                        seen_ids.add(t["external_id"])
                        all_tenders.append(t)
                time.sleep(1)

        log("eis_client",
            f"Итого получено {len(all_tenders)} закупок"
            f" (ИНН: {inn_list}, регион: {region}, ключи: {keywords})")
        return all_tenders

    def _search_by_inn(self, inn, region, keywords, date_from, date_to, page, page_size):
        params = {
            "searchString": " ".join(keywords) if keywords else "",
            "morphology": "on",
            "search-filter": "Дате размещения",
            "pageNumber": str(page),
            "sortDirection": "false",
            "recordsPerPage": f"_{min(page_size, 50)}",
            "showLotsInfoHidden": "false",
            "sortBy": "UPDATE_DATE",
            "fz44": "on", "fz223": "on",
            "af": "on", "ca": "on", "pc": "on", "pa": "on",
            "currencyIdGeneral": "-1",
            "customerIdOrg": inn,
            "publishDateFrom": date_from,
            "publishDateTo": date_to,
        }
        if region:
            params["customerPlace"] = region
        return self._fetch_html_results(params, context=f"INN={inn}")

    def _search_by_keyword(self, keyword, region, date_from, date_to, page, page_size):
        params = {
            "searchString": keyword,
            "morphology": "on",
            "search-filter": "Дате размещения",
            "pageNumber": str(page),
            "sortDirection": "false",
            "recordsPerPage": f"_{min(page_size, 50)}",
            "showLotsInfoHidden": "false",
            "sortBy": "UPDATE_DATE",
            "fz44": "on", "fz223": "on",
            "af": "on", "ca": "on", "pc": "on", "pa": "on",
            "currencyIdGeneral": "-1",
            "publishDateFrom": date_from,
            "publishDateTo": date_to,
        }
        if region:
            params["customerPlace"] = region
        return self._fetch_html_results(params, context=f"keyword={keyword}")

    def _fetch_html_results(self, params: dict, context: str = "") -> List[Dict]:
        try:
            log("eis_client",
                f"Запрос к ЕИС [{context}]: {SEARCH_URL}?"
                + "&".join(f"{k}={v}" for k, v in params.items() if v))
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
            log("eis_client", f"Ошибка [{context}]: {e}", level="ERROR")
            return []

    def _parse_html(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".registry-entry__form")
        tenders = []
        for card in cards:
            try:
                t = self._parse_card(card)
                if t and t.get("external_id"):
                    tenders.append(t)
            except Exception as e:
                log("eis_client", f"Ошибка парсинга карточки: {e}", level="WARNING")
        return tenders

    def _parse_card(self, card) -> Optional[Dict]:
        # --- Номер и ссылка ---
        number_el = card.select_one(".registry-entry__header-mid__number a")
        if not number_el:
            return None
        purchase_number = number_el.get_text(strip=True).lstrip("\u2116 ")
        source_url = number_el.get("href", "")
        if source_url and not source_url.startswith("http"):
            source_url = BASE_URL + source_url

        external_id = purchase_number
        m = re.search(r"regNumber=([\w-]+)", source_url)
        if m:
            external_id = m.group(1)

        # --- Статус: .registry-entry__header-mid__title ---
        status_el = card.select_one(".registry-entry__header-mid__title")
        status = status_el.get_text(strip=True) if status_el else ""

        # --- Название закупки: первый .registry-entry__body-value ---
        # Внутри может быть <span class="highlightColor">электрод</span>
        # get_text() сцепляет все части вместе, но без separator слипаются слова
        title_block = card.select_one(".registry-entry__body-value")
        title = ""
        if title_block:
            # Вставляем пробел перед каждым <span>, чтобы не слипались слова
            for span in title_block.find_all("span"):
                span.insert_before(" ")
            title = " ".join(title_block.get_text().split())

        # --- Заказчик: имя из .registry-entry__body-href a, ИНН из href ---
        customer_name = ""
        customer_inn = ""
        customer_link = card.select_one(".registry-entry__body-href a")
        if customer_link:
            customer_name = customer_link.get_text(strip=True)
            href = customer_link.get("href", "")
            m_inn = re.search(r"[?&]inn=(\d{10,12})", href)
            if m_inn:
                customer_inn = m_inn.group(1)

        # --- Цена ---
        price = ""
        price_el = card.select_one(".price-block__value")
        if price_el:
            price = price_el.get_text(strip=True)

        # --- Дата размещения: первый .data-block__value ---
        publish_date = ""
        date_el = card.select_one(".data-block__value")
        if date_el:
            publish_date = self._normalize_date(date_el.get_text(strip=True))

        # --- Регион: не передаётся в карточке ЕИС ---
        # Фильтрация по региону уже выполнена на стороне ЕИС
        # через параметр customerPlace.
        region = ""

        return {
            "external_id": external_id,
            "purchase_number": purchase_number,
            "title": title,
            "publish_date": publish_date,
            "price": price,
            "region": region,
            "customer_name": customer_name,
            "customer_inn": customer_inn,
            "status": status,
            "source_url": source_url,
            "raw_payload": {},
        }

    @staticmethod
    def _normalize_date(raw: str) -> str:
        raw = raw.strip()
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", raw)
        if m:
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        return raw


def fetch_rss_tenders(keyword: str, region: Optional[str] = None) -> List[Dict]:
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
        resp = requests.get(RSS_URL, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return _parse_rss(resp.text)
    except Exception as e:
        log("eis_client", f"RSS-ошибка [{keyword}]: {e}", level="ERROR")
        return []


def _parse_rss(xml_text: str) -> List[Dict]:
    tenders = []
    try:
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return []
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description = (item.findtext("description") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()

            external_id = link
            m = re.search(r"regNumber=([\w-]+)", link)
            if m:
                external_id = m.group(1)

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
                    "price": "",
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
