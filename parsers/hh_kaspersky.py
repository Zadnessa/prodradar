"""Парсер вакансий Касперского через HeadHunter API."""

from parsers.hh_base import HHBaseParser


class HHKasperskyParser(HHBaseParser):
    EMPLOYER_ID = 1057
    COMPANY_NAME = "Касперский"
    VACANCY_ID_PREFIX = "hh_kaspersky_"
