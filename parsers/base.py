"""Базовый интерфейс парсера вакансий."""

import inspect
from abc import ABC, abstractmethod


class BaseParser(ABC):
    """Базовый класс для всех парсеров."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        parse_method = cls.__dict__.get("parse")
        if parse_method is None:
            return

        params = inspect.signature(parse_method).parameters
        if "browser_secrets" in params:
            return

        async def parse_with_browser_secrets(self, session, existing_ids, city_mappings, browser_secrets=None):
            del browser_secrets
            return await parse_method(self, session, existing_ids, city_mappings)

        setattr(cls, "parse", parse_with_browser_secrets)

    @abstractmethod
    async def parse(self, session, existing_ids, city_mappings, browser_secrets=None):
        """Возвращает список вакансий в едином формате."""
        raise NotImplementedError

    async def enrich(self, session, vacancy):
        """Обогащает вакансию данными из API отдельной вакансии."""
        return vacancy
