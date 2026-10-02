"""Офлайн-оценка роли по сохранённому пулу и ручной title-разметке."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery.roles import classify, VERSION


def evaluate(pool, gold, classifier=classify):
    metrics = {}
    for split in sorted({r['split'] for r in gold['rows']}):
        metrics[split] = {}
        for family in ('project', 'bizdev'):
            tp = fp = fn = 0
            errors = []
            for row in gold['rows']:
                if row['split'] != split:
                    continue
                expected = family in row['families']
                actual = family in classifier({'title': row['title']})['families']
                tp += bool(expected and actual)
                fn += bool(expected and not actual)
                fp += bool(not expected and actual)
                if expected != actual:
                    errors.append({'title': row['title'], 'expected': expected, 'actual': actual})
            metrics[split][family] = {'true_positive': tp, 'false_positive': fp, 'false_negative': fn,
                                      'recall': tp / (tp + fn) if tp + fn else None,
                                      'precision': tp / (tp + fp) if tp + fp else None, 'errors': errors}
    classified = [(v, classifier(v)) for v in pool]
    selected = [(v, d) for v, d in classified if d['status'] == 'selected']
    audited_titles = {r['title'] for r in gold['rows']}
    return {'version': VERSION, 'scope': 'Captured native catalogs; unavailable sources excluded; title recall is not crawl coverage',
            'pool_count': len(pool), 'selected_count': len(selected),
            'families': dict(Counter(f for _, d in selected for f in d['families'])),
            'by_company': dict(sorted(Counter(v['company'] for v, _ in selected).items())),
            'review_count': sum(d['status'] == 'review' for _, d in classified),
            'audited_unique_titles': len(audited_titles), 'gold_method': gold['method'],
            'unaudited_selected_titles': sorted({v['title'] for v, _ in selected} - audited_titles),
            'metrics': metrics}, classified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pool', type=Path, required=True)
    parser.add_argument('--gold', type=Path, default=Path('tests/fixtures/project_bizdev_gold.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    summary, rows = evaluate(json.loads(args.pool.read_text()), json.loads(args.gold.read_text()))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    with (args.output / 'decisions.csv').open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['id', 'company', 'title', 'status', 'families', 'rules', 'native_groups', 'url'])
        for v, decision in rows:
            writer.writerow([v['id'], v['company'], v['title'], decision['status'],
                             ','.join(decision['families']), ','.join(decision['rules']),
                             '|'.join(decision['native_groups']), v['url']])
    from scripts.role_filter_ablation import ablate
    (args.output / 'ablation.json').write_text(json.dumps(ablate(json.loads(args.pool.read_text()), json.loads(args.gold.read_text())), ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
