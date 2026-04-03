"""Регистрация доступных парсеров."""

from parsers.alfa import AlfaParser
from parsers.aviasales import AviasalesParser
from parsers.avito import AvitoParser
from parsers.cian import CianParser
from parsers.dodo import DodoParser
from parsers.domclick import DomClickParser
from parsers.hh import HHParser
from parsers.kontur import KonturParser
from parsers.kuper import KuperParser
from parsers.lamoda import LamodaParser
from parsers.mts import MtsParser
from parsers.mtslink import MtsLinkParser
from parsers.ozon import OzonParser
from parsers.sber import SberParser
from parsers.tbank import TBankParser
from parsers.tochka import TochkaParser
from parsers.vk import VKParser
from parsers.wildberries import WildberriesParser
from parsers.x5 import X5Parser
from parsers.yandex import YandexParser

PARSER_REGISTRY = {
    "alfa": AlfaParser,
    "aviasales": AviasalesParser,
    "avito": AvitoParser,
    "cian": CianParser,
    "dodo": DodoParser,
    "domclick": DomClickParser,
    "hh": HHParser,
    "kontur": KonturParser,
    "kuper": KuperParser,
    "lamoda": LamodaParser,
    "mts": MtsParser,
    "mtslink": MtsLinkParser,
    "ozon": OzonParser,
    "sber": SberParser,
    "tbank": TBankParser,
    "tochka": TochkaParser,
    "vk": VKParser,
    "wildberries": WildberriesParser,
    "x5": X5Parser,
    "yandex": YandexParser,
}
