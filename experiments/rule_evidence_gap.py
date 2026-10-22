"""Fixed synthetic rule-evidence traces. No inference, rule changes or application wiring."""
import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from itertools import combinations
import os
from pathlib import Path
from uuid import uuid4

from experiments import development_rule_diagnostics as dev
from family_os import metadata_classifier as matcher
from family_os.synthetic_reasoning_comparison import _cases

ROOT = dev.ROOT
VERSION = 'rule-evidence-gap-v1'
LEGACY_SHA256 = '529f81a7adb293ecf89297996ea62237a65a931b8fead1f3f92a2ebea1ac2047'
CONFIG_SHA256 = {'classification.yaml': 'c5c7a324e7c292a268966cb138eeb04804bb39f9e17604011182414f412d9a64',
    'metadata-classifier.yaml': '9a7351aefa078dfb6cb13b4c0d2dfc9464e86f7cc9fae4ea8220ee77895f1d84'}
STATES = ('no_evidence', 'weak_only', 'conflict', 'strong_unanimous')
REFUSED = {'synthetic-url', 'synthetic-oversize', 'synthetic-wrong-shape'}
LOCAL = Path('.local/rule-evidence-gap')


def read_checked(path):
    """Fixed callers only; no file argument is exposed through the CLI."""
    dev.require(path in {ROOT / 'config' / name for name in CONFIG_SHA256} |
                {ROOT / 'fixtures/metadata-reasoning.synthetic.json'})
    dev.check_parents(path)
    before = dev.regular(path)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        dev.require(dev.file_identity(before) == dev.file_identity(opened))
        value = stream.read(dev.data.FILE_BYTES + 1)
        dev.require(dev.file_identity(os.fstat(stream.fileno())) == dev.file_identity(opened))
    dev.require(len(value) <= dev.data.FILE_BYTES and dev.file_identity(dev.regular(path)) == dev.file_identity(before))
    return value.replace(b'\r\n', b'\n')


def load():
    # The frozen rules/config pins make the comparison reproducible; version
    # changes need a separately reviewed diagnostic baseline, never quiet tuning.
    for name, expected in CONFIG_SHA256.items():
        dev.require(sha256(read_checked(ROOT / 'config' / name)).hexdigest() == expected)
    development, policy, rules, manifest = dev.load_development()
    raw = read_checked(ROOT / 'fixtures/metadata-reasoning.synthetic.json')
    dev.require(sha256(raw).hexdigest() == LEGACY_SHA256)
    parsed = _cases(dev.data.strict_json(raw.decode('utf-8')), policy)
    dev.require(len(parsed) == 37)
    legacy = tuple(dev.data.SyntheticCase(value.source_record_id, 'legacy37', value, human,
        dev.freeze_json(dict(scenario='unannotated', temporal='historical' if 'historical' in tags else
            'current' if 'recent' in tags else 'unknown', truth_certainty='unannotated',
            counterfactual_group=None, cue_field=None))) for value, human, tags, _ in parsed)
    dev.require(Counter(c.expected.action_label for c in legacy)['required'] == 6)
    dev.require(sum(c.expected.action_label != 'uncertain' for c in legacy) == 14)
    rejected = set()
    for c in legacy:
        try:
            dev.data.model_projection(c)
        except dev.AnalysisError:
            rejected.add(c.id)
            dev.require(c.expected.action_label == 'uncertain')
    dev.require(rejected == REFUSED)
    return development, legacy, policy, rules, manifest


def checked_diagnosis(value, policy, rules):
    diag = rules.diagnose(value, policy)
    dev.require(type(diag) is matcher.RuleDiagnostics)
    dev.validate_output(diag.output, value, policy)
    by_id = {r.id: r for r in rules.ruleset.rules}
    dev.require(set(diag.states) == {'action', 'domain', 'relevance'})
    dev.require(all(s in STATES for s in diag.states.values()))
    for ids in (diag.matched_rule_ids, diag.strong_rule_ids, diag.vetoed_rule_ids):
        dev.require(type(ids) is tuple and len(ids) == len(set(ids)) and set(ids) <= set(by_id))
    dev.require(not set(diag.matched_rule_ids) & set(diag.vetoed_rule_ids))
    dev.require(set(diag.strong_rule_ids) == {i for i in diag.matched_rule_ids if by_id[i].strength == 'strong'})
    for dim, state in diag.states.items():
        candidates = [by_id[i] for i in diag.matched_rule_ids if dim in by_id[i].prediction]
        labels = {r.prediction[dim] for r in candidates}
        expected = 'no_evidence' if not candidates else 'conflict' if len(labels) > 1 else (
            'strong_unanimous' if any(r.strength == 'strong' for r in candidates) else 'weak_only')
        dev.require(state == expected)
    return diag


def predicate_trace(value, rules, diag):
    """Use the actual matcher one predicate at a time, never a paraphrased matcher.

    No replacement rule is executed as a classifier or used to alter an output.
    Predicate failures are conjunction diagnostics, NOT counterfactual correctness.
    """
    words = matcher.tokens(value.subject) if value.subject is not None else ()
    domain = matcher._sender_domain(value.sender)
    traces = {}
    for rule in rules.ruleset.rules:
        failed = [key for key, val in rule.when.items()
                  if not matcher._matches(replace(rule, when={key: val}), value, words, domain)]
        raw_match = not failed
        dev.require(raw_match == (rule.id in diag.matched_rule_ids or rule.id in diag.vetoed_rule_ids))
        fields = set(rule.when.get('metadata_present', ())) | set(rule.when.get('metadata_equals', {}))
        traces[rule.id] = dict(scope_eligible=not bool(set(failed) & {'providers', 'record_types'}),
            failed_predicates=sorted(failed), missing_metadata_fields=sorted(f for f in fields if matcher._metadata(value, f) is None))
    caution = []
    if set(words) & matcher.CAUTION: caution.append('subject_caution')
    if matcher._metadata(value, 'status') == 'cancelled': caution.append('cancelled_status')
    if matcher._metadata(value, 'trashed') is True: caution.append('trashed')
    if matcher._metadata(value, 'removed') is True: caution.append('removed')
    return traces, caution


def trace(c, policy, rules):
    row = dict(id=c.id, provider=c.input.provider, **dict(c.annotations),
        expected_action=c.expected.action_label, expected_relevance=c.expected.relevance_label,
        predicted_action=None, predicted_relevance=None, predicted_domain=None,
        status='projection_rejected', states=None, matched_rule_ids=[], strong_rule_ids=[],
        weak_rule_ids=[], vetoed_rule_ids=[], caution_conditions=[], predicates={}, projection_trace_equal=None)
    try:
        projection = dev.data.model_projection(c)
    except dev.AnalysisError:
        return row
    try:
        diag = checked_diagnosis(c.input, policy, rules)
        predicates, caution = predicate_trace(c.input, rules, diag)
        # Same safe visible metadata, without annotations. Test whether approved
        # projection changes the actual trace/output, not whether unseen mail
        # contents might have supported a different judgment.
        fields = projection.fields
        projected = replace(c.input, subject=fields.get('subject'), sender=fields.get('sender'),
                            raw_metadata=fields.get('raw_metadata', {}))
        projected_diag = checked_diagnosis(projected, policy, rules)
        projected_predicates, _ = predicate_trace(projected, rules, projected_diag)
        row.update(status='valid', states=dict(diag.states), matched_rule_ids=list(diag.matched_rule_ids),
            strong_rule_ids=list(diag.strong_rule_ids),
            weak_rule_ids=sorted(set(diag.matched_rule_ids) - set(diag.strong_rule_ids)),
            vetoed_rule_ids=list(diag.vetoed_rule_ids), caution_conditions=caution, predicates=predicates,
            projection_trace_equal=diag == projected_diag and predicates == projected_predicates,
            predicted_action=diag.output.action_label, predicted_relevance=diag.output.relevance_label,
            predicted_domain=diag.output.category)
    except dev.AnalysisError:
        row['status'] = 'diagnosis_rejected'
    except Exception:
        row['status'] = 'diagnosis_invalid'
    return row


def summary(rows, rules):
    valid = [r for r in rows if r['status'] == 'valid']
    return dict(**dev.metrics(rows), action_states=dict(Counter(r['states']['action'] for r in valid)),
        no_rule_matched=sum(not r['matched_rule_ids'] and not r['vetoed_rule_ids'] for r in valid),
        non_action_matches_only=sum(bool(r['matched_rule_ids']) and r['states']['action'] == 'no_evidence' for r in valid),
        veto_cases=sum(bool(r['vetoed_rule_ids']) for r in valid),
        caution_cases=sum(bool(r['caution_conditions']) for r in valid),
        projection_comparisons=len(valid), projection_trace_changes=sum(not r['projection_trace_equal'] for r in valid),
        by_rule={rule.id: dict(strength=rule.strength, action_prediction=rule.prediction.get('action'),
            predicate_match_count=sum(rule.id in r['matched_rule_ids'] or rule.id in r['vetoed_rule_ids'] for r in valid),
            accepted_match_count=sum(rule.id in r['matched_rule_ids'] for r in valid),
            strong_matches=sum(rule.id in r['strong_rule_ids'] for r in valid),
            weak_matches=sum(rule.id in r['weak_rule_ids'] for r in valid),
            vetoed_matches=sum(rule.id in r['vetoed_rule_ids'] for r in valid),
            required_miss_accepted_matches=sum(r['expected_action'] == 'required' and r['predicted_action'] != 'required' and rule.id in r['matched_rule_ids'] for r in valid),
            required_miss_vetoed_matches=sum(r['expected_action'] == 'required' and r['predicted_action'] != 'required' and rule.id in r['vetoed_rule_ids'] for r in valid),
            decisive_error_accepted_matches=sum(r['expected_action'] != 'uncertain' and r['predicted_action'] != r['expected_action'] and rule.id in r['matched_rule_ids'] for r in valid),
            scope_eligible=sum(r['predicates'][rule.id]['scope_eligible'] for r in valid),
            scope_failed_predicates=dict(Counter(key for r in valid if r['predicates'][rule.id]['scope_eligible']
                for key in r['predicates'][rule.id]['failed_predicates'])),
            scope_missing_metadata=dict(Counter(key for r in valid if r['predicates'][rule.id]['scope_eligible']
                for key in r['predicates'][rule.id]['missing_metadata_fields']))) for rule in rules.ruleset.rules})


def triads(rows):
    groups = {}
    for r in rows:
        if r['counterfactual_group']:
            groups.setdefault(r['counterfactual_group'], []).append(r)
    details = {}
    fields = ('matched_rule_ids', 'vetoed_rule_ids', 'states', 'predicted_action', 'predicates')
    for name, members in sorted(groups.items()):
        pairs = [pair for pair in combinations(members, 2) if all(r['status'] == 'valid' for r in pair)]
        details[name] = dict(ids=sorted(r['id'] for r in members), cue_field=members[0]['cue_field'],
            selected_pairs=len(list(combinations(members, 2))), valid_pairs=len(pairs),
            changed_pairs={field: sum(a[field] != b[field] for a, b in pairs) for field in fields},
            correct_pairs=sum(all(r['predicted_action'] == r['expected_action'] for r in pair) for pair in pairs))
    return dict(classification=dev.triads(rows), groups=details,
        changed_pairs={field: sum(g['changed_pairs'][field] for g in details.values()) for field in fields})


def report():
    development, legacy, policy, rules, manifest = load()
    cohorts = {}
    for name, cases in (('development60', development), ('legacy37', legacy)):
        rows = [trace(c, policy, rules) for c in cases]
        # Frozen projection failures are known cases, never a fallback prediction.
        dev.require({r['id'] for r in rows if r['status'] == 'projection_rejected'} == (REFUSED if name == 'legacy37' else set()))
        cohorts[name] = dict(summary=summary(rows, rules),
            by_dimension={dim: {key: summary([r for r in rows if r[dim] == key], rules)
                for key in sorted({r[dim] for r in rows})} for dim in ('provider', 'scenario', 'temporal', 'expected_action')},
            triads=triads(rows), cases=rows)
    return dict(contract=VERSION, notice='SYNTHETIC OFFLINE DIAGNOSIS — NOT REAL-WORLD ACCURACY',
        holdout_content_read=False, cross_split_content_revalidated=False,
        development_manifest_sha256=dev.data.digest(manifest), development_projection_sha256=dev.PROJECTION_SHA256,
        legacy_lf_sha256=LEGACY_SHA256, configuration_lf_sha256=CONFIG_SHA256,
        definition=dict(name=rules.name, version=rules.version, fingerprint=rules.ruleset.fingerprint,
                        policy_fingerprint=policy.fingerprint(rules.name, rules.version)), cohorts=cohorts)


def save(result):
    target = ROOT / LOCAL
    for part in (ROOT / '.local', target):
        dev.check_parents(part)
        part.mkdir(mode=0o700, exist_ok=True)
        dev.regular(part, directory=True)
    run = target / uuid4().hex
    run.mkdir(mode=0o700)
    path = run / 'report.json'
    with path.open('x', encoding='utf-8') as stream:
        stream.write(dev.data.canonical_json(result) + '\n')
    return path.relative_to(ROOT).as_posix()


def short_summary(result, path):
    lines = ['规则行动证据缺口诊断（仅合成数据；不代表真实世界准确率）']
    for name in ('development60', 'legacy37'):
        m = result['cohorts'][name]['summary']
        lines.append(f"{name}：明确标签正确 {m['decisive_correct']}/{m['decisive_count']}；required 识别 {m['required_recognized']}/{m['required_count']}；行动状态 {m['action_states']}；veto 案例 {m['veto_cases']}")
    lines.extend(['两组分母独立；uncertain 不代表已建立 Pending。未读取 Holdout，未运行 AI。', f'本地详细诊断：{path}'])
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Fixed synthetic rule evidence gap analysis, no model execution')
    parser.add_argument('--synthetic-only', required=True, action='store_true')
    parser.parse_args(argv)
    try:
        result = report()
        print(short_summary(result, save(result)))
        return 0
    except Exception:
        print('证据缺口诊断失败；未输出部分结果或案例内容。')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
