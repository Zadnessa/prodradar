"""Регистрация доступных парсеров."""

from parsers.alfa import AlfaParser
from parsers.avito import AvitoParser
from parsers.cian import CianParser
from parsers.dodo import DodoParser
from parsers.kontur import KonturParser
from parsers.ozon import OzonParser
from parsers.sber import SberParser
from parsers.tbank import TBankParser
from parsers.tochka import TochkaParser
from parsers.vk import VKParser
from parsers.wildberries import WildberriesParser
from parsers.yandex import YandexParser

PARSER_REGISTRY = {
    "wildberries": WildberriesParser,
    "yandex": YandexParser,
    "ozon": OzonParser,
    "tbank": TBankParser,
    "vk": VKParser,
    "avito": AvitoParser,
    "sber": SberParser,
    "alfa": AlfaParser,
    "dodo": DodoParser,
    "cian": CianParser,
    "tochka": TochkaParser,
    "kontur": KonturParser,
}
