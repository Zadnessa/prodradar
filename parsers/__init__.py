"""Регистрация доступных парсеров."""

from parsers.alfa import AlfaParser
from parsers.avito import AvitoParser
from parsers.cian import CianParser
from parsers.dodo import DodoParser
from parsers.domclick import DomClickParser
from parsers.kontur import KonturParser
from parsers.kuper import KuperParser
from parsers.lamoda import LamodaParser
from parsers.ozon import OzonParser
from parsers.sber import SberParser
from parsers.tbank import TBankParser
from parsers.tochka import TochkaParser
from parsers.vk import VKParser
from parsers.wildberries import WildberriesParser
from parsers.yandex import YandexParser

PARSER_REGISTRY = {
    "alfa": AlfaParser,
    "avito": AvitoParser,
    "cian": CianParser,
    "dodo": DodoParser,
    "domclick": DomClickParser,
    "kontur": KonturParser,
    "kuper": KuperParser,
    "lamoda": LamodaParser,
    "ozon": OzonParser,
    "sber": SberParser,
    "tbank": TBankParser,
    "tochka": TochkaParser,
    "vk": VKParser,
    "wildberries": WildberriesParser,
    "yandex": YandexParser,
}
