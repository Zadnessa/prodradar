"""Базовый интерфейс парсера вакансий."""

from abc import ABC, abstractmethod


class BaseParser(ABC):
    """Базовый класс для всех парсеров."""

    @abstractmethod
    async def parse(self, session, existing_ids, city_mappings):
        """Возвращает список вакансий в едином формате."""
        raise NotImplementedError
