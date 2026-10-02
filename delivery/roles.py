"""Объяснимый отбор project/bizdev: сильные роли и контекст серой зоны."""

import re
import unicodedata

from delivery.role_aliases import ALIASES

VERSION = 'project-bizdev-2026-10-02.4'

PROJECT_RULES = {
    'project_en': r'\b(?:project|program(?:me)?)\s+(?:manager|lead|director|coordinator)\b',
    'project_ru': r'\b(?:менеджер\w*|руководител[ья]|лидер\w*|директор\w*|координатор\w*|администратор\w*)\s+(?:[\w-]+\s+){0,5}(?:[а-я]*проект(?:а|ов|ами|ам|ы|ом|е|ах)?|программ(?:а|ы|ами|ам|ой|е|ах)?)\b',
    'project_adjective': r'\b(?:проектн\w*|проджект)\s*(?:менеджер|менеджмент|лид|руководитель)\b',
    'delivery_en': r'\bdelivery\s+(?:manager|lead|director)\b',
    'project_activity': r'\b(?:менеджер|руководитель|директор)\s+(?:[\w]+\s+){0,3}проектн\w*\s+деятельност\w*\b',
    'project_team': r'\b(?:руководитель|менеджер)\s+проектн\w*\s+команд\w*\b',
    'project_office': r'\b(?:менеджер|руководитель|директор)\s+(?:[\w-]+\s+){0,3}проектн(?:ого|ый|ом)\s+офис\w*\b',
}
BIZDEV_RULES = {
    'bizdev_en': r'\b(?:business\s+development|bizdev|bdm)\b',
    'new_business': r'\b(?:new\s+business|corporate\s+development)\s+(?:manager|director|lead)\b',
    'bizdev_ru': r'\b(?:менеджер\w*|руководител[ья]|директор\w*|лидер\w*|глава)\s+(?:[\w-]+\s+){0,5}развити\w*\s+(?:(?:мал\w*|средн\w*|крупн\w*|международн\w*|нов\w*|цифров\w*|еком|ecom|и)\s+){0,5}бизнес\w*\b(?!\s+(?:процесс|продукт))',
    'partner_growth_ru': r'\b(?:менеджер|руководитель|директор)\s+(?:[\w]+\s+){0,3}(?:привлечени\w*|расширени\w*)\s+(?:[\w]+\s+){0,3}партнер\w*\b',
    'strategic_partnerships_ru': r'\b(?:менеджер|руководитель|директор)\s+(?:стратегическ\w*\s+)?партнерств\w*\b',
    'partnerships_en': r'\b(?:strategic\s+)?partner(?:ship)?s?\s+(?:manager|lead|director|executive)\b|\b(?:head|director)\s+of\s+partnerships?\b',
    'partnerships_ru': r'\b(?:менеджер\w*|руководител[ья]|директор\w*|лидер\w*)\s+(?:[\w-]+\s+){0,5}развити\w*\s+(?:[\w-]+\s+){0,3}партнер\w*\b',
}
HARD_REJECT = {
    'engineering_or_analysis': r'^(?:(?:ведущий|старший|главный|senior|lead|ml|системный|бизнес|продуктовый)\s+){0,3}(?:аналитик\w*|разработчик\w*|developer|engineer|инженер\w*|дизайнер\w*|проектировщик\w*)\b',
}
GREY_RULES = {
    'launch': r'\b(?:менеджер|руководитель)\s+(?:[\w]+\s+){0,3}запуск\w*\b',
    'customer_journey': r'\bcje\b|\bcustomer journey expert\b',
    'operations': r'\b(?:operations|product operations)\s+manager\b|\bменеджер\s+операц\w*\b',
    'producer': r'\bпродюсер\b|\bкоординатор\b',
    'implementation': r'\b(?:менеджер|руководитель)\s+(?:[\w-]+\s+){0,3}внедрен\w*\b|\bimplementation\s+manager\b',
    'development': r'\b(?:менеджер|руководитель|директор|лидер)\s+(?:[\w-]+\s+){0,3}развити\w*\b',
    'direction': r'\b(?:менеджер|руководитель|директор|лидер|продюсер)\s+(?:[\w-]+\s+){0,2}(?:направлен\w*|стрим\w*|трансформаци\w*)\b',
    'partner_accounts': r'\b(?:менеджер|руководитель)\s+(?:[\w-]+\s+){0,5}партнер\w*\b',
    'agile': r'\bscrum\s+master\b|\bagile\s+coach\b',
}
SIGNALS = {
    'monetization': r'монетизац\w*|\bmoneti[sz]ation\b',
    'advertising': r'реклам\w*|\badvertis\w*\b|\badtech\b',
    'partnerships': r'партнер\w*|\bpartnership\w*\b',
}


def normalized(text):
    text = unicodedata.normalize('NFKC', str(text or '')).lower().replace('ё', 'е').replace('&', ' ')
    text = re.sub(r'[-\u2010-\u2015\u2212/]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def native_groups(vacancy):
    source = vacancy.get('source_json') or {}
    groups = []
    def names(value):
        if isinstance(value, str):
            groups.append(value)
        elif isinstance(value, list):
            for item in value:
                names(item)
        elif isinstance(value, dict):
            for key in ('name', 'title', 'slug'):
                if value.get(key):
                    names(value[key])
    for key in ('group', 'group_name', 'category', 'direction', 'directions', 'prof_area',
                'specialization', 'businessLine', 'businessLineName', 'direction_title', 'direction_role_title',
                'professionalRoles', 'mainCategory', 'mainSpecialization', 'specialty', 'tags', 'department'):
        names(source.get(key))
    names((source.get('info') or {}).get('category'))
    return list(dict.fromkeys(groups))


def classify(vacancy, *, apply_blacklist=True, disambiguate=True, exclude_internships=False, enable_aliases=True):
    title = normalized(vacancy.get('title'))
    groups = native_groups(vacancy)
    body = normalized(vacancy.get('description'))
    signals = [name for name, pattern in SIGNALS.items() if re.search(pattern, title + ' ' + body)]
    rejected = [name for name, pattern in HARD_REJECT.items() if apply_blacklist and re.search(pattern, title)]
    if exclude_internships and re.search(r'\b(?:стажер\w*|intern(?:ship)?|trainee)\b', title):
        rejected.append('internship')
    result = {'version': VERSION, 'status': 'rejected', 'families': [], 'zone': None,
              'rules': [], 'excluded_by': rejected, 'native_groups': groups, 'signals': signals}
    if enable_aliases:
        for alias in ALIASES:
            if vacancy.get('company') != alias['company'] or title != normalized(alias['title']):
                continue
            if all(any(re.search(pattern, body) for pattern in group) for group in alias['evidence_patterns']):
                result.update(status='selected', zone='semantic', families=alias['families'],
                              rules=['company_alias:' + alias['id']], excluded_by=[])
                return result
    if rejected:
        return result
    for family, rules in (('project', PROJECT_RULES), ('bizdev', BIZDEV_RULES)):
        matched = [name for name, pattern in rules.items() if re.search(pattern, title)]
        if matched:
            result['families'].append(family)
            result['rules'].extend(matched)
    # Названная другая профессия/руководство разработчиками не становится PM
    # лишь из-за упоминания проектов или проектной команды в конце заголовка.
    exclusions = {
        'other_primary_role': r'\bменеджер\s+по\s+(?:логистик\w*|маркетинг\w*|коммуникац\w*)\b.*\bв\b.*\bпроект(?:ы|ов|е|ах)?\b',
        'technical_team': r'\b(?:руководитель|лидер)\s+(?:ml|llm|разработки|разработчиков)\s+команд\w*',
        'product_role': r'\bменеджер\s+(?:по\s+)?продукт\w*\b',
        'sales_role': r'\b(?:менеджер|руководитель|директор)\s+(?:(?:направления|отдела|по)\s+){0,3}(?:продаж\w*|продаже)\b',
        'client_role': r'\bклиентский\s+менеджер\b',
    }
    reasons = [name for name, pattern in exclusions.items() if disambiguate and re.search(pattern, title)]
    if disambiguate and re.search(r'партнер\w*\s+программ\w*', title) and not re.search(r'проект', title):
        reasons.append('partner_program_role')
    if 'project' in result['families'] and reasons:
        result['families'].remove('project')
        result['excluded_by'].extend(reasons)
        result.update(status='review', zone='grey')
    if result['families']:
        result.update(status='selected', zone='exact')
        return result
    grey = [name for name, pattern in GREY_RULES.items() if re.search(pattern, title)]
    if not grey:
        return result
    result.update(status='review', zone='grey', rules=grey)
    # Группа не доказывает функцию: смежные позиции требуют проверки
    # обязанностей и company alias до доставки.
    return result


async def resolve_role(session, vacancy, parser=None):
    """При live сборе известный алиас проверяется после detail API/HTML."""
    decision = classify(vacancy)
    known_alias = any(vacancy.get('company') == a['company'] and
                      normalized(vacancy.get('title')) == normalized(a['title']) for a in ALIASES)
    if known_alias and decision['zone'] != 'semantic' and parser is not None:
        await parser.enrich(session, vacancy)
        decision = classify(vacancy)
    return decision


def apply_selection(vacancy, decision):
    vacancy['selection_profile'] = 'project_bizdev'
    vacancy['role_families'] = decision['families']
    vacancy['selection_version'] = decision['version']
    vacancy.setdefault('source_json', {})['selection'] = decision
    return vacancy
