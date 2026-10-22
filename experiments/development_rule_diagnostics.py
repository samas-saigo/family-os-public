"""Fixed Development-only offline diagnostics; no model, provider or DB dependency.

Never call the full dataset loader. Frozen hashes are the authority for unchanged
annotations/schema; only Development's internal semantics are revalidated here.
"""
import argparse
from collections import Counter
from itertools import combinations
import json
import os
from pathlib import Path
import stat
from uuid import uuid4

from family_os import action_evaluation as data
from family_os.analysis import AnalysisInput, AnalysisError, freeze_json, validate_output
from family_os.audit import HumanLabels, ratio, validate_labels
from family_os.metadata_classifier import MetadataRulesAnalyzer, load_rules

ROOT = data.ROOT
VERSION = 'development-rule-diagnostics-v1'
# Same reviewed Development projection identity as action_model_benchmark; do not
# import its model transport or call its full-dataset selection/runner.
PROJECTION_SHA256 = 'b3fac7d7c286a0a2c1f7ba013825a3bbc19e1cbf2dd0faefd0a8500f3cabe6f0'
NAMES = ('development.json', 'rubric.json', 'manifest.json')
LOCAL = Path('.local/development-rule-diagnostics')


class Rejected(Exception):
    """Content-free rejection; underlying source/driver text never reaches output."""


def require(ok):
    if not ok:
        raise Rejected()


def regular(path, *, directory=False):
    """Trusted checkout/local output only; reject links, Windows reparse points."""
    info = path.lstat()
    require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400)
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
    return info


def file_identity(info):
    # Reading may update atime (notably on a fresh Windows checkout). It is not
    # an integrity signal; compare identity/content metadata, never access time.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def check_parents(path):
    for parent in reversed(path.absolute().parents):
        regular(parent, directory=True)


def read_fixed(name):
    require(name in NAMES)
    path = ROOT / 'fixtures/action-evaluation-v1' / name
    check_parents(path)
    before = regular(path)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino))
        require(stat.S_ISREG(opened.st_mode) and opened.st_nlink == 1)
        raw = stream.read(data.FILE_BYTES + 1)
        require(file_identity(os.fstat(stream.fileno())) == file_identity(opened))
    require(file_identity(regular(path)) == file_identity(before))
    return data.strict_json(raw.decode('utf-8'))


def validate_development(corpus, rubric, manifest, policy):
    """Pinned canonical content plus fresh Development-only semantic checks.

    No fake/stub Holdout is passed to the existing validator. Cross-split and
    original-37 non-overlap remain assertions of the previously reviewed freeze.
    """
    try:
        require(data.digest(manifest) == data.FROZEN_MANIFEST_SHA256)
        require(type(rubric) is dict and set(rubric) == data.RUBRIC_KEYS)
        require(data.digest(rubric) == manifest['rubric_sha256'])
        require(manifest['projection_schema'] == 'metadata_only_v1')
        require(manifest['projection_engine'] == data.PROJECTION_ENGINE)
        require(data.digest({'version': policy.taxonomy_version, 'categories': policy.categories}) == manifest['taxonomy_sha256'])
        require(type(corpus) is dict and set(corpus) == {'synthetic_only', 'dataset_version', 'split', 'cases'})
        require(corpus['synthetic_only'] is True and corpus['split'] == 'development' and corpus['dataset_version'] == data.VERSION)
        require(type(corpus['cases']) is list and len(corpus['cases']) == 60)
        ordered = dict(corpus, cases=sorted(corpus['cases'], key=lambda c: c['id']))
        frozen = manifest['splits']['development']
        require(frozen['case_count'] == 60 and data.digest(ordered) == frozen['annotated_sha256'])
        require(data.digest([c['input'] for c in ordered['cases']]) == frozen['input_sha256'])
        parsed, groups, fingerprints = [], {}, set()
        for c in ordered['cases']:
            require(type(c) is dict and set(c) == data.CASE_KEYS)
            source = c['input']
            occurred = data._timestamp(source['occurred_at'])
            data.MetadataProjection(dict(source, occurred_at=occurred.isoformat(timespec='microseconds').replace('+00:00', 'Z')))
            domain = c['expected']['domain']
            human = validate_labels(HumanLabels(c['expected']['relevance'], *(domain or (None, None)), c['expected']['action']), policy)
            value = AnalysisInput(c['id'], 'raw-' + c['id'], source['provider'], 'unknown', None,
                source['record_type'], 'object-' + c['id'], occurred, source['subject'], source.get('sender'), (), source['raw_metadata'])
            annotations = freeze_json({k: c[k] for k in ('scenario', 'temporal', 'truth_certainty', 'counterfactual_group', 'cue_field')})
            case = data.SyntheticCase(c['id'], 'development', value, human, annotations)
            projected = data.model_projection(case)
            require(projected.byte_count <= 1024 and projected.fingerprint not in fingerprints)
            fingerprints.add(projected.fingerprint)
            parsed.append(case)
            if c['counterfactual_group']:
                groups.setdefault(c['counterfactual_group'], []).append(c)
        require(len({c.id for c in parsed}) == 60)
        require(Counter(c.expected.action_label for c in parsed) == Counter(dict.fromkeys(data.ACTIONS, 20)))
        require(len(groups) == 16)
        for members in groups.values():
            require(len(members) == 3 and {c['expected']['action'] for c in members} == set(data.ACTIONS))
            require(len({c['cue_field'] for c in members}) == 1)
            require(len({data.canonical_json({k: c['expected'][k] for k in ('relevance', 'domain')}) for c in members}) == 1)
            masked = []
            cues = []
            for c in members:
                value = json.loads(data.canonical_json(c['input']))
                parts = c['cue_field'].split('.')
                target = value
                for part in parts[:-1]:
                    target = target[part]
                cues.append(data.canonical_json(target[parts[-1]]))
                target[parts[-1]] = '<controlled-cue>'
                masked.append(value)
            require(len(set(cues)) == 3 and all(v == masked[0] for v in masked))
        require(data.digest([data.model_projection(c).fields for c in parsed]) == PROJECTION_SHA256)
        return tuple(parsed)
    except Exception:
        raise Rejected() from None


def load_development():
    try:
        # Only these five checked-in files can be read. Config loaders are the
        # existing rules/taxonomy parsers; no generic dataset loader is used.
        for name in ('classification.yaml', 'metadata-classifier.yaml'):
            path = ROOT / 'config' / name
            check_parents(path)
            regular(path)
        policy = data.load_classification(ROOT / 'config/classification.yaml')
        corpus, rubric, manifest = (read_fixed(name) for name in NAMES)
        cases = validate_development(corpus, rubric, manifest, policy)
        rules = MetadataRulesAnalyzer(load_rules(ROOT / 'config/metadata-classifier.yaml', policy))
        return cases, policy, rules, manifest
    except Exception:
        raise Rejected() from None


def metrics(rows):
    """Fixed selected denominators: failures cannot disappear or become correct."""
    cohorts = {a: [r for r in rows if r['expected_action'] == a] for a in data.ACTIONS}
    required, negative, uncertain = (cohorts[a] for a in data.ACTIONS)
    correct = lambda rs: sum(r['status'] == 'valid' and r['predicted_action'] == r['expected_action'] for r in rs)
    predict = lambda rs, a: sum(r['status'] == 'valid' and r['predicted_action'] == a for r in rs)
    decisive = required + negative
    return dict(selected=len(rows), status_counts=dict(Counter(r['status'] for r in rows)),
        action_matrix={a: dict(Counter(r['predicted_action'] for r in rs if r['status'] == 'valid')) for a, rs in cohorts.items()},
        decisive_count=len(decisive), decisive_correct=correct(decisive), decisive_accuracy=ratio(correct(decisive), len(decisive)),
        required_count=len(required), required_recognized=predict(required, 'required'),
        required_misses=len(required) - predict(required, 'required'),
        required_to_not_required=predict(required, 'not_required'), required_to_uncertain=predict(required, 'uncertain'),
        required_invalid_or_rejected=sum(r['status'] != 'valid' for r in required),
        not_required_to_required=predict(negative, 'required'),
        relevant_false_irrelevant=sum(r['status'] == 'valid' and r['expected_relevance'] == 'relevant' and r['predicted_relevance'] == 'irrelevant' for r in rows),
        uncertain_count=len(uncertain), uncertain_predictions={a: predict(uncertain, a) for a in data.ACTIONS},
        uncertain_concrete=predict(uncertain, 'required') + predict(uncertain, 'not_required'),
        uncertain_invalid_or_rejected=sum(r['status'] != 'valid' for r in uncertain),
        valid_action_abstentions=predict(rows, 'uncertain'),
        unclassified_domain=sum(r['status'] == 'valid' and r['predicted_domain'] is None for r in rows))


def triads(rows):
    groups = {}
    for r in rows:
        if r['counterfactual_group']:
            groups.setdefault(r['counterfactual_group'], []).append(r)
    def summary(members):
        members = list(members)
        complete = [g for g in members if all(r['status'] == 'valid' for r in g)]
        pairs = [p for g in members for p in combinations(g, 2)]
        valid_pairs = [p for p in pairs if all(r['status'] == 'valid' for r in p)]
        changed = sum(a['predicted_action'] != b['predicted_action'] for a, b in valid_pairs)
        return dict(selected_triads=len(members), valid_triads=len(complete),
            all_three_correct=sum(all(r['predicted_action'] == r['expected_action'] for r in g) for g in complete),
            distinct_predictions=sum(len({r['predicted_action'] for r in g}) == 3 for g in complete),
            unchanged_prediction_triads=sum(len({r['predicted_action'] for r in g}) == 1 for g in complete),
            selected_pairs=len(pairs), valid_pairs=len(valid_pairs), changed_pairs=changed,
            correct_pairs=sum(all(r['predicted_action'] == r['expected_action'] for r in p) for p in valid_pairs),
            pair_change_rate=ratio(changed, len(valid_pairs)))
    return dict(**summary(groups.values()), by_cue={cue: summary(g for g in groups.values() if g[0]['cue_field'] == cue)
                for cue in ('subject', 'raw_metadata.status')})


def diagnose():
    cases, policy, rules, manifest = load_development()
    rows = []
    for c in cases:
        row = dict(id=c.id, provider=c.input.provider, **dict(c.annotations),
            expected_action=c.expected.action_label, expected_relevance=c.expected.relevance_label,
            predicted_action=None, predicted_relevance=None, predicted_domain=None, status='rejected')
        try:
            out = rules.analyze(c.input, policy)
        except AnalysisError:
            pass
        except Exception:
            row['status'] = 'rule_error'
        else:
            try:
                validate_output(out, c.input, policy)
                row.update(status='valid', predicted_action=out.action_label, predicted_relevance=out.relevance_label,
                           predicted_domain=out.category)
            except Exception:
                row['status'] = 'invalid_output'
        row.update(action_correct=row['status'] == 'valid' and row['predicted_action'] == row['expected_action'],
                   required_not_recognized=row['expected_action'] == 'required' and (row['status'] != 'valid' or row['predicted_action'] != 'required'))
        rows.append(row)
    return dict(contract=VERSION, notice='DEVELOPMENT DIAGNOSTICS ONLY — NOT REAL-WORLD ACCURACY',
        synthetic_only=True, split='development', holdout_content_read=False,
        cross_split_content_revalidated=False, manifest_sha256=data.digest(manifest),
        development_identity=manifest['splits']['development'], projection_sha256=PROJECTION_SHA256,
        rubric_sha256=manifest['rubric_sha256'], reference_time='2026-10-09T12:00:00Z',
        definition=dict(analyzer=rules.name, version=rules.version, rules_fingerprint=rules.ruleset.fingerprint,
                        policy_fingerprint=policy.fingerprint(rules.name, rules.version)),
        metrics=metrics(rows), triads=triads(rows),
        by_dimension={dim: {key: metrics([r for r in rows if r[dim] == key]) for key in sorted({r[dim] for r in rows})}
                      for dim in ('provider', 'scenario', 'temporal')}, cases=rows)


def save(report):
    # No arbitrary input or output path. Fresh private local directory, no overwrite.
    target = ROOT / LOCAL
    for part in (ROOT / '.local', target):
        check_parents(part)
        part.mkdir(mode=0o700, exist_ok=True)
        regular(part, directory=True)
    run = target / uuid4().hex
    run.mkdir(mode=0o700)
    path = run / 'report.json'
    with path.open('x', encoding='utf-8') as file:
        file.write(data.canonical_json(report) + '\n')
    return path.relative_to(ROOT).as_posix()


def short_summary(report, path):
    m = report['metrics']
    return (f"Development 规则诊断（虚构数据；不代表真实世界准确率）\n"
        f"明确标签正确：{m['decisive_correct']}/{m['decisive_count']}；required 识别：{m['required_recognized']}/{m['required_count']}；漏判：{m['required_misses']}\n"
        f"漏判→不需行动：{m['required_to_not_required']}；→待确认：{m['required_to_uncertain']}；无效/拒绝：{m['required_invalid_or_rejected']}\n"
        f"错误升级：{m['not_required_to_required']}；相关事项误判 irrelevant：{m['relevant_false_irrelevant']}；人工不确定被确定化：{m['uncertain_concrete']}/{m['uncertain_count']}\n"
        f"有效输出：{m['status_counts'].get('valid', 0)}/{m['selected']}；triad 全对：{report['triads']['all_three_correct']}/16\n"
        f"未读取 Holdout；未运行 AI；uncertain 预测不代表已创建 Pending。\n本地详细诊断：{path}")


def main(argv=None):
    parser = argparse.ArgumentParser(description='Fixed synthetic Development-only offline rules diagnostics')
    parser.add_argument('--synthetic-only', required=True, action='store_true')
    parser.parse_args(argv)
    try:
        report = diagnose()
        path = save(report)
        print(short_summary(report, path))
        return 0
    except Exception:
        print('Development 诊断失败；未输出部分结果或案例正文。请检查固定文件身份及本地输出目录。')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
