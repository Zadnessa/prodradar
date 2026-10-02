"""Оценка относительно native подборок, с отдельной разметкой каждой вакансии."""
from delivery.roles import classify


COHORTS = {
    'ozon_project_107': ('ozon', 'professionalRoles', 'ID', '107'),
    'ozon_partners': ('ozon', 'professionalRoles', 'title', 'Менеджер по работе с партнерами'),
    'vk_project_2261': ('vk', 'tags', 'id', '2261'),
    'vk_business_263': ('vk', 'specialty', 'id', '263'),
    'sber_project_specializations': ('sber', 'specialization', None, None),
    'wb_project_direction': ('wildberries', 'direction_title', None, 'Управление проектами'),
}


def belongs(vacancy, cohort):
    source, field, attribute, expected = COHORTS[cohort]
    if vacancy.get('source') != source:
        return False
    value = (vacancy.get('source_json') or {}).get(field)
    if cohort == 'sber_project_specializations':
        return isinstance(value, str) and value.split(':')[-1] in {
            'Руководитель проектов', 'Руководитель строительного проекта'}
    if attribute:
        values = value if isinstance(value, list) else [value]
        return any(isinstance(item, dict) and str(item.get(attribute)) == expected for item in values)
    return value == expected


def evaluate_native_cohorts(pool, gold, classifier=classify):
    reports = {}
    for name in COHORTS:
        records = [v for v in pool if belongs(v, name)]
        labels = {r['id']: r for r in gold['cohorts'][name]}
        available = {v['id'] for v in records}
        metrics = {}
        for family in ('project', 'bizdev'):
            tp = fp = fn = 0
            errors = []
            for vacancy in records:
                label = labels.get(vacancy['id'])
                if not label:
                    continue
                # Переписанное название требует нового review, не наследует label.
                if vacancy['title'] != label['title']:
                    continue
                expected = family in label['families']
                actual = family in classifier(vacancy)['families']
                tp += bool(expected and actual)
                fp += bool(not expected and actual)
                fn += bool(expected and not actual)
                if expected != actual:
                    errors.append({'id': vacancy['id'], 'title': vacancy['title'],
                                   'expected': expected, 'actual': actual})
            metrics[family] = {'true_positive': tp, 'false_positive': fp, 'false_negative': fn,
                               'recall': tp / (tp + fn) if tp + fn else None,
                               'precision': tp / (tp + fp) if tp + fp else None, 'errors': errors}
        reports[name] = {'native_records': len(records),
                         'audited_records': sum(v['id'] in labels and v['title'] == labels[v['id']]['title'] for v in records),
                         'unaudited_ids': [v['id'] for v in records if v['id'] not in labels or v['title'] != labels[v['id']]['title']],
                         'missing_snapshot_ids': sorted(set(labels) - available), 'metrics': metrics}
    return {'method': gold['method'], 'cohorts': reports}
