"""Объяснимый отбор project/bizdev: сильные роли и контекст серой зоны."""

import re
import unicodedata

VERSION = 'project-bizdev-2026-10-02.2'

PROJECT_RULES = {
    'project_en': r'\b(?:project|program(?:me)?)\s+(?:manager|lead|director|coordinator)\b',
    'project_ru': r'\b(?:менеджер\w*|руководител[ья]|лидер\w*|директор\w*|координатор\w*|администратор\w*)\s+(?:[\w-]+\s+){0,5}(?:[а-я]*проект(?:а|ов|ами|ам|ы|ом|е|ах)?|программ(?:а|ы|ами|ам|ой|е|ах)?)\b',
    'project_adjective': r'\b(?:проектн\w*|проджект)\s*(?:менеджер|менеджмент|лид|руководитель)\b',
    'delivery_en': r'\bdelivery\s+(?:manager|lead|director)\b',
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
    'internship': r'\b(?:стажер\w*|intern(?:ship)?|trainee)\b',
    'engineering_or_analysis': r'^(?:(?:ведущий|старший|главный|senior|lead|ml|системный|бизнес|продуктовый)\s+){0,3}(?:аналитик\w*|разработчик\w*|developer|engineer|инженер\w*|дизайнер\w*|проектировщик\w*)\b',
}
GREY_RULES = {
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
    text = unicodedata.normalize('NFKC', str(text or '')).lower().replace('ё', 'е')
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
                'professionalRoles', 'mainCategory', 'mainSpecialization', 'specialty', 'tags', 'department'):
        names(source.get(key))
    names((source.get('info') or {}).get('category'))
    return list(dict.fromkeys(groups))


def classify(vacancy):
    title = normalized(vacancy.get('title'))
    groups = native_groups(vacancy)
    body = normalized(vacancy.get('description'))
    signals = [name for name, pattern in SIGNALS.items() if re.search(pattern, title + ' ' + body)]
    rejected = [name for name, pattern in HARD_REJECT.items() if re.search(pattern, title)]
    result = {'version': VERSION, 'status': 'rejected', 'families': [], 'zone': None,
              'rules': [], 'excluded_by': rejected, 'native_groups': groups, 'signals': signals}
    if rejected:
        return result
    for family, rules in (('project', PROJECT_RULES), ('bizdev', BIZDEV_RULES)):
        matched = [name for name, pattern in rules.items() if re.search(pattern, title)]
        if matched:
            result['families'].append(family)
            result['rules'].extend(matched)
    # Названная другая профессия/руководство разработчиками не становится PM
    # лишь из-за упоминания проектов или проектной команды в конце заголовка.
    other_role = re.search(r'\bменеджер\s+по\s+(?:логистик\w*|маркетинг\w*|продаж\w*|коммуникац\w*)\b', title)
    technical_team = re.search(r'\b(?:руководитель|лидер)\s+(?:ml|llm|разработки|разработчиков)\s+команд\w*', title)
    if 'project' in result['families'] and (other_role or technical_team):
        result['families'].remove('project')
        result['excluded_by'].append('other_primary_role')
        result.update(status='review', zone='grey')
    if result['families']:
        result.update(status='selected', zone='exact')
        return result
    grey = [name for name, pattern in GREY_RULES.items() if re.search(pattern, title)]
    if not grey:
        return result
    result.update(status='review', zone='grey', rules=grey)
    # Группа не подменяет название роли: ambiguous позиции сохраняются
    # для ручной оценки, но не доставляются без явного имени project/bizdev.
    return result


def apply_selection(vacancy, decision):
    vacancy['selection_profile'] = 'project_bizdev'
    vacancy['role_families'] = decision['families']
    vacancy['selection_version'] = decision['version']
    vacancy.setdefault('source_json', {})['selection'] = decision
    return vacancy
