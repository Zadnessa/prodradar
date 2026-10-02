"""Откат ограничений и возврат по одному: потери target видны отдельно."""
from delivery.roles import classify


def _no_title_filter(_vacancy):
    return {'status': 'selected', 'families': ['project', 'bizdev']}


def variants():
    return [
        ('0_all_catalog', _no_title_filter),
        ('1_named_roles_only', lambda v: classify(v, apply_blacklist=False, disambiguate=False, enable_aliases=False, precision_guards=[])),
        ('2_technical_primary_blacklist', lambda v: classify(v, disambiguate=False, enable_aliases=False, precision_guards=[])),
        ('3_other_primary_role_guard', lambda v: classify(v, enable_aliases=False, precision_guards=[])),
        ('4_company_aliases_without_duty_guards', lambda v: classify(v, precision_guards=[])),
        ('5_sales_account_duties', lambda v: classify(v, precision_guards=['sales_account'])),
        ('6_other_primary_duties', lambda v: classify(v, precision_guards=['sales_account', 'other_primary'])),
        ('7_mixed_commercial_review', classify),
        ('8_restore_legacy_intern_blacklist', lambda v: classify(v, exclude_internships=True)),
    ]


def native_product_gate(vacancy):
    source = vacancy.get('source')
    raw = vacancy.get('source_json') or {}
    if source == 'alfa':
        return str(raw.get('businessLineId')) == '1020'
    if source == 'vk':
        return any(str(tag.get('id')) == '2259' for tag in raw.get('tags') or [] if isinstance(tag, dict))
    if source == 'ozon':
        return any(str(role.get('ID')) == '73' for role in raw.get('professionalRoles') or [] if isinstance(role, dict))
    return None


def ablate(pool, gold):
    result = []
    previous_targets = None
    for name, classifier in variants():
        tp = fp = fn = 0
        retained = set()
        missed = []
        for row in gold['rows']:
            expected = set(row['families'])
            actual = set(classifier(row)['families'])
            tp += len(expected & actual)
            fp += len(actual - expected)
            fn += len(expected - actual)
            for family in expected & actual:
                retained.add((row.get('company', ''), row['title'], family))
            for family in expected - actual:
                missed.append({'title': row['title'], 'family': family})
        result.append({'step': name, 'selected_records': sum(classifier(v)['status'] == 'selected' for v in pool),
                       'true_positive': tp, 'false_positive': fp, 'false_negative': fn,
                       'recall': tp / (tp + fn) if tp + fn else None,
                       'precision': tp / (tp + fp) if tp + fp else None,
                       'missed_targets': missed,
                       'target_losses_vs_previous': [{'company': c, 'title': t, 'family': f} for c, t, f in sorted((previous_targets or retained) - retained)]})
        previous_targets = retained
    native = []
    for source in ('alfa', 'vk', 'ozon'):
        source_pool = [v for v in pool if v.get('source') == source]
        selected = [v for v in source_pool if classify(v)['status'] == 'selected']
        retained = [v for v in selected if native_product_gate(v)]
        native.append({'source': source, 'available_records': len(source_pool), 'target_records': len(selected),
                       'retained_by_previous_product_group': len(retained),
                       'lost_target_ids': [v['id'] for v in selected if not native_product_gate(v)]})
    return {'stages': result, 'native_product_group_rollback': native,
            'decision': 'Intern blacklist removed: named target roles are lost. Native product groups are not used. Other-role guards retained only with zero losses on audited targets.'}
