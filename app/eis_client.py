"""Модуль интеграции с официальным сервисом отдачи информации ЕИС.

Официальный сервис: https://zakupki.gov.ru
С 01.01.2025 машиночитаемые данные доступны исключительно через сервисы отдачи информации.
Для получения доступа необходимо зарегистрироваться как получатель данных на сайте ЕИС.

Документация: https://zakupki.gov.ru (раздел «Сервисы отдачи информации»)

ПРИМЕЧАНИЕ: Точные URL эндпоинтов, формат запроса и ответа уточняются
в документации сервиса после получения доступа. Данный модуль реализует
базовую структуру клиента, которую нужно адаптировать под реальный API.
"""

import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from app.db import log, get_settings


EIS_BASE_URL = "https://zakupki.gov.ru"


class EISClient:
    """Клиент для работы с сервисом отдачи информации ЕИС."""

    def __init__(self):
        self.settings = get_settings() or {}
        self.base_url = self.settings.get("eis_base_url", EIS_BASE_URL).rstrip("/")
        self.login = self.settings.get("eis_login", "")
        self.token = self.settings.get("eis_token", "")
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def reload_settings(self):
        """Перезагрузить настройки из базы."""
        self.settings = get_settings() or {}
        self.login = self.settings.get("eis_login", "")
        self.token = self.settings.get("eis_token", "")
        self.base_url = self.settings.get("eis_base_url", EIS_BASE_URL).rstrip("/")
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def check_connection(self) -> tuple:
        """Проверить доступность сервиса ЕИС. Возвращает (успех, сообщение)."""
        try:
            resp = self.session.get(self.base_url + "/epz/main/public/home.html", timeout=10)
            if resp.status_code == 200:
                return True, "Сайт ЕИС доступен"
            return False, f"Сервер ответил кодом {resp.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Нет подключения к интернету или сайт ЕИС недоступен"
        except requests.exceptions.Timeout:
            return False, "Превышено время ожидания ответа от ЕИС"
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
        page_size: int = 100,
    ) -> List[Dict]:
        """
        Получить закупки из ЕИС по параметрам поиска.

        ПРИМЕЧАНИЕ: Точные параметры запроса определяются документацией
        сервиса отдачи информации ЕИС после получения доступа.
        Текущая реализация — заготовка под реальный API.
        """
        if not date_from:
            date_from = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
        if not date_to:
            date_to = datetime.now().strftime("%Y-%m-%dT23:59:59")

        params = {
            "publishDateFrom": date_from,
            "publishDateTo": date_to,
            "pageNumber": page,
            "recordsPerPage": page_size,
        }
        if inn_list:
            params["customerINN"] = ",".join(inn_list)
        if region:
            params["regionCode"] = region
        if keywords:
            params["searchString"] = " ".join(keywords)

        try:
            log("eis_client", f"Запрос к ЕИС: ИНН={inn_list}, регион={region}, ключи={keywords}")
            resp = self.session.get(
                self.base_url + "/epz/order/ws/receiver/recieve",
                params=params,
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            tenders = self._parse_response(data)
            log("eis_client", f"Получено {len(tenders)} закупок из ЕИС")
            return tenders
        except requests.exceptions.HTTPError as e:
            log("eis_client", f"Ошибка HTTP при запросе ЕИС: {e}", level="ERROR", details=str(e))
            return []
        except requests.exceptions.ConnectionError as e:
            log("eis_client", "Нет подключения к ЕИС", level="ERROR", details=str(e))
            return []
        except Exception as e:
            log("eis_client", f"Ошибка при запросе ЕИС: {e}", level="ERROR", details=str(e))
            return []

    def _parse_response(self, data: dict) -> List[Dict]:
        """Преобразовать ответ ЕИС во внутренний формат закупки."""
        tenders = []
        items = data if isinstance(data, list) else data.get("data",
                 data.get("items", data.get("results", [])))
        for item in items:
            try:
                tender = {
                    "external_id": str(
                        item.get("id") or item.get("regNum") or item.get("purchaseNumber", "")
                    ),
                    "purchase_number": item.get("purchaseNumber") or item.get("regNum", ""),
                    "title": (
                        item.get("purchaseObjectInfo") or
                        item.get("name") or
                        item.get("subject", "")
                    ),
                    "publish_date": item.get("publishDate") or item.get("createDate", ""),
                    "region": item.get("regionName") or item.get("region", ""),
                    "customer_name": (
                        item.get("customer", {}).get("fullName") or
                        item.get("customerName", "")
                    ),
                    "customer_inn": (
                        item.get("customer", {}).get("inn") or
                        item.get("customerInn", "")
                    ),
                    "status": item.get("purchaseStateName") or item.get("status", ""),
                    "source_url": (
                        item.get("url") or
                        f"https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html"
                        f"?regNumber={item.get('purchaseNumber', '')}"
                    ),
                    "raw_payload": item,
                }
                if tender["external_id"]:
                    tenders.append(tender)
            except Exception as e:
                log("eis_client", f"Ошибка разбора записи ЕИС: {e}", level="WARNING", details=str(item))
        return tenders
