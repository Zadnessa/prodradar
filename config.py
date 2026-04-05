"""Конфигурация проекта Vacancy Radar."""

import os

SHOW_DESCRIPTION = False
TEST_MODE = False
TEST_LIMIT = 3
VACANCY_TTL_DAYS = 30

# Абсолютный pre-filter. Отсекает до проверки зон. Расширять эмпирически.
TITLE_PREFILTER_REJECT = [
    "стажер",
    "стажёр",
    "intern",
]

TITLE_EXACT_WHITELIST = [
    # Руководящие
    "product lead",
    "product-lead",
    "product director",
    "head of product",
    "chief product officer",
    "chief product owner",
    "cpo",
    "директор по продукт",
    "лидер продукт",
    "лид продукт",
    "продакт-лид",
    "продакт лид",
    # Product manager
    "product manager",
    "product-manager",
    "менеджер продукта",
    "менеджер продуктов",
    "менеджер продукту",
    "менеджер по продукту",
    "менеджер по продуктам",
    "продакт-менеджер",
    "продакт менеджер",
    "продукт-менеджер",
    "продукт менеджер",
    "продуктовый менеджер",
    "продуктового менеджмент",
    # Миксы рус/англ
    "product менеджер",
    "product-менеджер",
    "продакт manager",
    # Product owner
    "product owner",
    "product-owner",
    "владелец продукта",
    "владелец продуктов",
    # Прочие
    "продуктолог",
    "специалист по продукт",
    "специалист продуктов",
    # AI/ML
    "ai продакт",
    "ai-продакт",
    "ml продакт",
    "ml-продакт",
    "ai product",
    "ai-product",
    "ml product",
    "ml-product",
    # Growth
    "growth-менеджер",
    "growth менеджер",
]

# Regex-паттерны. Blacklist применяется после матча.
TITLE_REGEX_PATTERNS = [
    r"менеджер.{0,40}продукт",
    r"руководитель.{0,40}продукт",
    r"директор.{0,40}продукт",
    r"владелец.{0,40}продукт",
    r"лидер.{0,40}продукт",
    r"лид.{0,40}продукт",
    r"product.{0,20}lead",
    r"manager.{0,40}продукт",
    r"\bpm\b",
]

# Серая зона. Blacklist применяется. AI-фаза (Wave 7) уточнит.
TITLE_GREY_PATTERNS = [
    ("руководитель продукт", False),
    ("бизнес-лид", False),
    ("бизнес лид", False),
    ("бизнес-партнер по продукт", False),
    ("бизнес партнер по продукт", False),
    ("growth manager", False),
    (r"руководитель направлен", True),
    (r"руководитель бизнес", True),
    (r"лидер направлен", True),
    ("бизнес-лидер", False),
    (r"лидер стрим", True),
    ("category lead", False),
    (r"руководитель категор", True),
    (r"менеджер направлен", True),
    (r"менеджер по развити", True),
    (r"лидер кластера", True),
    (r"лидер трансформаци", True),
]

TITLE_BLACKLIST_PATTERNS = [
    "проджект",
    "project",
    "проект",
    "продаж",
    "presale",
    "пресейл",
    "пресеил",
    "pre-sale",
    "pre sale",
    "бренд",
    "brand",
    "категорийн",
    "delivery",
    "деливери",
    "scrum",
    "сценарист",
    "дизайн",
    "аналитик",
    "marketing",
    "маркетинг",
    "маркетолог",
    "pmm",
    "bdm",
    "по развитию бизнеса",
    "business development",
    "аккаунт",
    "account",
    "разработк",
    "закупк",
    "методолог",
    "поддержк",
    "сопровожден",
]

GRADE_OVERRIDE_PATTERNS = [
    (r"\bмладш", "Junior"),
    (r"\bjunior\b", "Junior"),
    (r"head of product", "Lead+"),
    (r"chief product", "Lead+"),
    (r"\bcpo\b", "Lead+"),
    (r"директор.{0,40}продукт", "Lead+"),
    (r"лидер.{0,40}продукт", "Lead+"),
    (r"лид.{0,40}продукт", "Lead+"),
    (r"product.{0,20}lead", "Lead+"),
]

CHROME_VERSION = os.getenv("CHROME_VERSION", "146.0.0.0")
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    f"Chrome/{CHROME_VERSION} Safari/537.36"
)

REQUEST_HEADERS = {
    "User-Agent": CHROME_USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

BOTS = {
    "main": {
        "token_env": "TELEGRAM_BOT_TOKEN",
        "name": "Vacancy Radar",
    }
}

SBER_EXPERIENCE_MAP = {
    "4a14da73-ed71-43f0-aa42-0c5ffe5033e7": "Без опыта / Стажер",
    "07544111-3b15-475c-9980-1d0fa3d031c5": "От 1 до 3 лет",
    "7d2adf16-4635-4f0f-bf6e-f6089a702b5d": "От 3 до 6 лет",
    "17b55c6a-0559-499b-aa2c-d76559d46dc0": "От 6 лет",
}

ALFA_EXPERIENCE_MAP = {
    "custom_voc_5_entry_1": "Без опыта",
    "custom_voc_5_entry_2": "До 1 года",
    "custom_voc_5_entry_5": "От 1 до 3 лет",
    "custom_voc_5_entry_6": "От 3 до 5 лет",
    "custom_voc_5_entry_4": "От 5 лет",
}

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
