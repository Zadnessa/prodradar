"""Парсер вакансий Звук через HeadHunter API."""

from parsers.hh_base import HHBaseParser


class HHZvukParser(HHBaseParser):
    EMPLOYER_ID = 1829949
    COMPANY_NAME = "Звук"
    VACANCY_ID_PREFIX = "hh_zvuk_"
