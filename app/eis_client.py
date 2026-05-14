"""Модуль получения закупок с ЕИС без авторизации."""

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
    "Referer": "https://zakupki.gov.ru/epz/main/public/home.html",
}

DEFAULT_DAYS_BACK = 7


class EISClient:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def reload_settings(self):
        pass

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
            log("eis_client", f"Запрос к ЕИС [{context}]: {SEARCH_URL}?" +
                "&".join(f"{k}={v}" for k, v in params.items() if v))
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

    def _parse_html(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        tenders = []
        cards = soup.select(".registry-entry__form")
        if not cards:
            cards = soup.select(".search-registry-entry-block")
        if not cards:
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
        """
        Разбор карточки закупки с сайта ЕИС.

        Структура HTML-карточки (актуальная вёрстка):

          .registry-entry__header-top         <- статус ("Размещена")
          .registry-entry__header-mid         <- номер закупки
            .registry-entry__header-mid__number a  <- номер + ссылка
          .registry-entry__body               <- тело
            блок «Объект закупки»    <- название (значение после label)
            блок «Заказчик»             <- название организации + ИНН
            блок «Регион»               <- регион (на основе label)
            блок «Дата»                 <- дата публикации
        """
        # --- Номер и ссылка ---
        number_el = card.select_one(".registry-entry__header-mid__number a")
        if not number_el:
            return None

        purchase_number = number_el.get_text(strip=True)
        source_url = number_el.get("href", "")
        if source_url and not source_url.startswith("http"):
            source_url = BASE_URL + source_url

        external_id = purchase_number
        m = re.search(r"regNumber=([\w-]+)", source_url)
        if m:
            external_id = m.group(1)

        # --- Статус ---
        status_el = card.select_one(".registry-entry__header-top__title span")
        if not status_el:
            status_el = card.select_one(".registry-entry__header-top__title")
        status = status_el.get_text(strip=True) if status_el else ""

        # --- Парсинг блоков по label ---
        # Все блоки вида:
        #   <div class="registry-entry__body-block">
        #     <span class="registry-entry__body-title">Объект закупки</span>
        #     <span class="registry-entry__body-value">...название...</span>
        #   </div>
        title = ""
        customer_name = ""
        customer_inn = ""
        region = ""
        publish_date = ""

        for block in card.select(".registry-entry__body-block"):
            label_el = block.select_one(".registry-entry__body-title")
            value_el = block.select_one(".registry-entry__body-value")
            if not label_el or not value_el:
                continue
            label = label_el.get_text(strip=True).lower()
            value = value_el.get_text(" ", strip=True)

            if "объект" in label or "предмет" in label:
                title = value
            elif "заказчик" in label:
                customer_name = value
                # ИНН часто в соседнем блоке или внутри value
                inn_m = re.search(r"\b(\d{10}|\d{12})\b", value)
                if inn_m:
                    customer_inn = inn_m.group(1)
            elif "инн" in label:
                inn_m = re.search(r"\b(\d{10}|\d{12})\b", value)
                if inn_m:
                    customer_inn = inn_m.group(1)
            elif "регион" in label or "место" in label:
                region = value
            elif "дата" in label or "размещен" in label:
                publish_date = self._normalize_date(value)

        # --- Запасные варианты ---
        # Если title всё ещё пустой — берём первый .registry-entry__body-value
        if not title:
            val = card.select_one(".registry-entry__body-value")
            if val:
                title = val.get_text(strip=True)

        # Дата из .data-block
        if not publish_date:
            date_el = card.select_one(".data-block__value")
            if date_el:
                publish_date = self._normalize_date(date_el.get_text(strip=True))

        # ИНН из ссылки на заказчика
        if not customer_inn:
            customer_link = card.select_one(".registry-entry__body-href a")
            if customer_link:
                if not customer_name:
                    customer_name = customer_link.get_text(strip=True)
                href = customer_link.get("href", "")
                m_inn = re.search(r"inn=(\d{10,12})", href)
                if m_inn:
                    customer_inn = m_inn.group(1)

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
