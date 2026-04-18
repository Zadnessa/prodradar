"""Парсер вакансий HeadHunter."""

from parsers.hh_base import HHBaseParser


class HHParser(HHBaseParser):
    EMPLOYER_ID = 1455
    COMPANY_NAME = "HeadHunter"
    VACANCY_ID_PREFIX = "hh_"
