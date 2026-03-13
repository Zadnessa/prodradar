"""Вспомогательные функции для парсеров."""


def normalize_city(city_mappings, city, source="general"):
    """Нормализует город через таблицу маппингов."""
    if not city:
        return "Не указан"
    value = str(city).strip()
    if not value:
        return "Не указан"
    return city_mappings.get((source, value), value)
