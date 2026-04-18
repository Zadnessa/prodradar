"""Парсер вакансий Циан через API HeadHunter."""

from parsers.hh_base import HHBaseParser


class HHCianParser(HHBaseParser):
    EMPLOYER_ID = 1429999
    COMPANY_NAME = "Циан"
    VACANCY_ID_PREFIX = "hh_cian_"
