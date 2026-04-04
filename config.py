"""Конфигурация проекта Vacancy Radar."""

import os

SHOW_DESCRIPTION = False
TEST_MODE = False
TEST_LIMIT = 3
VACANCY_TTL_DAYS = 30

TITLE_WHITELIST_PATTERNS = [
    # руководящие (проверяем первыми)
    (r"product.{0,20}lead", True),
    ("product director", False),
    (r"директор.{0,40}продукт", True),
    ("head of product", False),
    ("chief product", False),
    ("cpo", False),
    (r"лидер.{0,40}продукт", True),
    (r"лид.{0,40}продукт", True),
    (r"руководитель.{0,40}продукт", True),
    # product manager (латиница)
    ("product manager", False),
    ("product-manager", False),
    # менеджер продукт* (кириллица, regex)
    (r"менеджер.{0,40}продукт", True),
    # продакт-менеджер
    ("продакт-менеджер", False),
    ("продакт менеджер", False),
    ("продукт-менеджер", False),
    ("продукт менеджер", False),
    # продуктовый менеджер
    ("продуктовый менеджер", False),
    ("продуктового менеджмент", False),
    # миксы рус/англ
    ("product менеджер", False),
    ("product-менеджер", False),
    ("продакт manager", False),
    (r"manager.{0,40}продукт", True),
    # product owner / владелец продукта
    ("product owner", False),
    ("product-owner", False),
    (r"владелец.{0,40}продукт", True),
    # продуктолог
    ("продуктолог", False),
    # специалист по продукту
    ("специалист по продукт", False),
    ("специалист продуктов", False),
    # бизнес-партнёр по продукту
    ("бизнес-партнер по продукт", False),
    ("бизнес партнер по продукт", False),
    # продакт-лид (руководящие, но кириллица)
    (r"продакт.лид", True),
    (r"продакт-лид", True),
    # AI/ML продакт/product
    (r"ai.продакт", True),
    (r"ai-продакт", True),
    (r"ml.продакт", True),
    (r"ml-продакт", True),
    (r"ai.product", True),
    (r"ai-product", True),
    (r"ml.product", True),
    (r"ml-product", True),
    # growth-менеджер
    ("growth-менеджер", False),
    ("growth менеджер", False),
    # PM как отдельное слово
    (r"\bpm\b", True),
    # серая зона (включена в whitelist с комментарием)
    # grey zone — включаем в релиз, AI-фаза уточнит
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
    "стажер",
    "стажёр",
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
]

GRADE_OVERRIDE_PATTERNS = [
    (r"\bмладш", "Junior"),
    (r"\bjunior\b", "Junior"),
    (r"head of product", "Lead+"),
    (r"chief product", "Lead+"),
    (r"\bcpo\b", "Lead+"),
    (r"директор.{0,40}продукт", "Lead+"),
]

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
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
