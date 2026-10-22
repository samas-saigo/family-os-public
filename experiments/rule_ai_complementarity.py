"""Offline fixed-report analysis; no inference, private input or application wiring."""
import argparse
from collections import Counter
from datetime import datetime, timedelta
from hashlib import sha256
import json
import math
import re
from uuid import uuid4

from experiments import local_thinking_benchmark as bench
from experiments import _fixed_report_io as files

ROOT = bench.ROOT
VERSION = 'rule-ai-complementarity-v1'
MODEL = 'qwen3:8b-q4_K_M'
DIGEST = '500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41'
SCORING = 'historical-zero-confidence-plus-disjoint-diagnostics-v1'
BENCHMARK_VERSION = 'local-thinking-experiment-v1'
PINS = ('529f81a7adb293ecf89297996ea62237a65a931b8fead1f3f92a2ebea1ac2047',
        'ce795381831bceed14df9ca29a30135d0b1293d1060e6a510208925bf5fac14e',
        'd732b467076a6ed077a5f02457aa5c2c93f171b8e99b77b4c4d267b5d9daf473')
BUCKETS = ('both_correct', 'rules_only', 'ai_only', 'both_wrong')
ZERO = bench.AnalysisOutput('uncertain', 0.0, None, None, 0.0, 'uncertain', 0.0)


class ReportRejected(Exception):
    pass


def require(condition):
    if not condition:
        raise ReportRejected()


def same(left, right):
    # JSON equality is type-sensitive (True != 1), unlike Python dict equality.
    require(bench.wire_json(left) == bench.wire_json(right))


def finite(value, maximum):
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum)


def decode(raw):
    require(type(raw) is bytes and 0 < len(raw) <= files.MAX_BYTES)
    report = bench.old.strict_json(raw.decode('utf-8'))
    def bounded(value, depth=0):
        require(depth <= 32)
        if type(value) is dict:
            for v in value.values():
                bounded(v, depth + 1)
        elif type(value) is list:
            for v in value:
                bounded(v, depth + 1)
        elif type(value) in (float, int):
            require(math.isfinite(value))
    bounded(report)
    return report


def validate_manifest(report, policy, cases, rules):
    require(type(report) is dict and set(report) == {
        'notice', 'started_at_utc', 'manifest', 'manifest_fingerprint', 'reference_denominators_full37',
        'residency_before', 'residency_after', 'runs', 'completed', 'identity_verified', 'repeat_comparison'})
    require(report['completed'] is True and report['identity_verified'] is True)
    require(report['notice'] == 'SYNTHETIC ONLY / NOT PRODUCTION QUALITY OR ACTION AUTHORITY')
    timestamp = report['started_at_utc']
    require(type(timestamp) is str and len(timestamp) <= 48)
    require(datetime.fromisoformat(timestamp).utcoffset() == timedelta(0))
    same(report['reference_denominators_full37'], {'required': 6, 'decisive_action': 14})
    manifest = report['manifest']
    require(type(manifest) is dict)
    version, details, capabilities = (manifest.get(k) for k in ('ollama_version', 'details', 'capabilities'))
    require(type(version) is str and len(version) <= 64 and bool(re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-.][A-Za-z0-9]+)*', version)))
    require(type(details) is dict and set(details) == {'format', 'family', 'parameter_size', 'quantization_level'})
    require(details['format'] == 'gguf' and details['family'] == 'qwen3' and details['quantization_level'] == 'Q4_K_M')
    require(type(details['parameter_size']) is str and bool(re.fullmatch(r'8(?:\.[0-9]+)?B', details['parameter_size'])))
    require(type(capabilities) is list and 1 <= len(capabilities) <= 16 and 'thinking' in capabilities)
    require(all(type(v) is str and re.fullmatch('[a-z_]{1,32}', v) for v in capabilities))
    repeats = manifest.get('repeats')
    require(type(repeats) is int and 1 <= repeats <= 3)
    projections = []
    for input, _, _, _ in cases:
        try:
            projections.append(bench.project_metadata(input).fingerprint)
        except bench.AnalysisError:
            pass
    expected = dict(model=MODEL, digest=DIGEST, ollama_version=version, details=details, capabilities=capabilities,
        historical_weights_verified=False, contract=BENCHMARK_VERSION, thinking='off', options=bench.FIXED_OPTIONS,
        endpoint='/api/generate', wire_variant='flat-domain', corpus_sha256=bench.CORPUS_SHA,
        prompt_sha256=bench.PROMPT_SHA, schema_sha256=bench.SCHEMA_SHA,
        configuration_files_sha256=bench.CONFIG_SHA, selected=37, repeats=repeats,
        budgets={'request_seconds': 60, 'run_seconds': 600, 'response_bytes': 65536, 'final_response_bytes': 4096},
        projection_engine=bench.old.ENGINE_VERSION, projection_schema='metadata_only_v1',
        rules_fingerprint=rules.ruleset.fingerprint, taxonomy_digest=bench.old.digest(dict(policy.categories)),
        threshold_digest=bench.old.digest(policy.thresholds.__dict__), scoring=SCORING,
        projected_inputs_digest=bench.old.digest(projections))
    same(manifest, expected)
    same(report['manifest_fingerprint'], bench.old.digest(expected))
    require(type(report['runs']) is list and len(report['runs']) == repeats)
    for key in ('residency_before', 'residency_after'):
        value = report[key]
        if value is None:
            continue
        require(type(value) is dict and set(value) == {'size_bytes', 'size_vram_bytes', 'gpu_fraction'})
        require(type(value['size_bytes']) is int and type(value['size_vram_bytes']) is int and
                0 <= value['size_vram_bytes'] <= value['size_bytes'] and value['size_bytes'] > 0)
        finite(value['gpu_fraction'], 1)
        same(value['gpu_fraction'], value['size_vram_bytes'] / value['size_bytes'])


def validate_row(row, case, policy):
    input, truth, _, _ = case
    require(type(row) is dict and row.get('id') == input.source_record_id)
    base = {'id': input.source_record_id, 'expected': truth.action_label, 'status': 'projection_rejected',
            'predicted': None, 'correct': None, 'requires_human_confirmation': None,
            'false_positive': None, 'missed_possible_action': None, 'raw_envelope': None,
            'request': None, 'json_valid': None}
    try:
        request = bench.payload(input, policy, MODEL, 'off')
    except bench.AnalysisError:
        same(row, base)
        return None
    same(row.get('request'), request)
    envelope = row.get('raw_envelope')
    require(type(envelope) is dict and len(bench.wire_json(envelope).encode()) <= bench.API_BYTES)
    finite(row.get('wall_seconds'), 65)
    base.update(request=request, raw_envelope=envelope, wall_seconds=row['wall_seconds'])
    require(envelope.get('thinking', '') == '' and type(envelope.get('thinking', '')) is str)
    try:
        telemetry = bench.parse_envelope(envelope, MODEL, 'off')
    except bench.ExperimentError as error:
        require(str(error) == 'budget_truncated')
        # The historical truncation path exits before most envelope checks. Validate
        # the remaining envelope fields separately; never repair it into a prediction.
        probe = dict(envelope, done_reason='stop', response='{}')
        bench.parse_envelope(probe, MODEL, 'off')
        require(type(envelope.get('response')) is str and len(envelope['response'].encode()) <= 4096)
        base['status'] = 'budget_truncated'
        same(row, base)
        return None
    base.update(telemetry=telemetry, thinking_observation='trace_absent_not_internal_proof',
        tokens_per_second=bench.old.ratio(telemetry['eval_count'], telemetry['eval_duration'] / 1e9 if telemetry['eval_duration'] else None),
        reasoning_token_count=None, final_token_count=None, status='invalid_output', json_valid=False)
    output = None
    try:
        bench.old.strict_json(envelope['response'])
        base['json_valid'] = True
        output = bench.old.labels(envelope['response'], input, policy, 'flat-domain')
    except bench.AnalysisError:
        pass
    if output is not None:
        predicted = output.action_label
        base.update(status='valid', predicted=predicted, correct=predicted == truth.action_label,
                    requires_human_confirmation=True, uncertainty_retained=predicted == 'uncertain',
                    false_positive=truth.action_label == 'not_required' and predicted == 'required',
                    missed_possible_action=truth.action_label == 'required' and predicted != 'required')
    same(row, base)
    return output


def validate_diagnostics(rows, cases, outputs):
    valid = [r for r in rows if r['status'] == 'valid']
    return {'status_counts': dict(Counter(r['status'] for r in rows)),
        'json_validity_rate_sent': bench.old.ratio(sum(r['json_valid'] is True for r in rows), sum(r['request'] is not None for r in rows)),
        'label_validity_rate_sent': bench.old.ratio(len(valid), sum(r['request'] is not None for r in rows)),
        'required_to_not_required': sum(r['expected'] == 'required' and r['predicted'] == 'not_required' for r in valid),
        'required_to_uncertain': sum(r['expected'] == 'required' and r['predicted'] == 'uncertain' for r in valid),
        'uncertain_to_required': sum(r['expected'] == 'uncertain' and r['predicted'] == 'required' for r in valid),
        'uncertain_to_not_required': sum(r['expected'] == 'uncertain' and r['predicted'] == 'not_required' for r in valid),
        'required_miss_rate_legacy': bench.old.ratio(sum(h.action_label == 'required' and o.action_label != 'required' for (_, h, _, _), o in zip(cases, outputs)), 6),
        'not_required_false_positive_rate': bench.old.ratio(sum(r['false_positive'] is True for r in valid), 8),
        'invalid_required_count': sum(r['expected'] == 'required' and r['status'] != 'valid' for r in rows),
        'confusion_valid_only': dict(Counter(r['expected'] + '->' + r['predicted'] for r in valid)),
        'valid_only_action_accuracy': bench.old.ratio(sum(r['correct'] for r in valid), len(valid)),
        'invalid_rate_sent': bench.old.ratio(sum(r['status'] in {'invalid_output', 'budget_truncated'} for r in rows), sum(r['request'] is not None for r in rows)),
        'latency_seconds': bench.old.distribution([r.get('wall_seconds') for r in rows]),
        'output_token_rate': bench.old.distribution([r.get('tokens_per_second') for r in rows])}


def validate(report):
    require(bench.VERSION == BENCHMARK_VERSION and (bench.CORPUS_SHA, bench.PROMPT_SHA, bench.SCHEMA_SHA) == PINS)
    same(bench.CONFIG_SHA, {
        'classification.yaml': 'c5c7a324e7c292a268966cb138eeb04804bb39f9e17604011182414f412d9a64',
        'metadata-classifier.yaml': '9a7351aefa078dfb6cb13b4c0d2dfc9464e86f7cc9fae4ea8220ee77895f1d84'})
    policy, cases = bench.corpus()
    rules = bench.MetadataRulesAnalyzer(bench.load_rules(ROOT / 'config/metadata-classifier.yaml', policy))
    validate_manifest(report, policy, cases, rules)
    rule_outputs = [rules.analyze(c[0], policy) for c in cases]
    normalized = []
    for repeat, item in enumerate(report['runs'], 1):
        require(type(item) is dict and set(item) == {'repeat', 'cases', 'legacy_metrics', 'incremental_domain_coverage', 'diagnostics', 'coverage'})
        same(item['repeat'], repeat)
        rows = item['cases']
        require(type(rows) is list and len(rows) == 37 and all(type(r) is dict and type(r.get('id')) is str for r in rows))
        by_id = {r['id']: r for r in rows}
        require(len(by_id) == 37 and set(by_id) == {c[0].source_record_id for c in cases})
        ordered = [by_id[c[0].source_record_id] for c in cases]
        actual = [validate_row(row, case, policy) for row, case in zip(ordered, cases)]
        scored = [o if o is not None else ZERO for o in actual]
        same(item['coverage'], {'selected': 37, 'recorded': 37, 'not_attempted': 0,
                                'status_counts': dict(Counter(r['status'] for r in ordered))})
        same(item['legacy_metrics'], {'rules': bench.old.metric_records(cases, rule_outputs, policy),
                                      'model': bench.old.metric_records(cases, scored, policy)})
        same(item['incremental_domain_coverage'], bench.old.incremental_domain_coverage(cases, rule_outputs, scored))
        same(item['diagnostics'], validate_diagnostics(ordered, cases, scored))
        normalized.append((ordered, actual, scored))
    first = normalized[0][0]
    pairs = [(a, c) for rows, _, _ in normalized[1:] for a, c in zip(first, rows) if a['status'] == c['status'] == 'valid']
    same(report['repeat_comparison'], {'valid_pairs': len(pairs), 'action_disagreements': sum(a['predicted'] != c['predicted'] for a, c in pairs)})
    return policy, cases, rule_outputs, normalized


def conservative(rule, ai):
    """Frozen, truth-free offline proposal; never an execution/clearance policy.

    AI cannot demote rule-required or promote an uncertain rule into a confirmed
    obligation. Agreement is informational only, never authority to discard data.
    """
    if rule.action_label == 'required':
        return 'required', 'rule_required_preserved'
    if rule.action_label == 'not_required' and ai is not None and ai.action_label == 'not_required':
        return 'not_required', 'informational_agreement_no_auto_dismissal'
    return 'uncertain', 'human_review_only'


def bucket(rule_correct, ai_correct):
    return ('both_correct' if ai_correct else 'rules_only') if rule_correct else ('ai_only' if ai_correct else 'both_wrong')


def analyze(raw):
    report = decode(raw)
    policy, cases, rules, runs = validate(report)
    analysis = {'contract': VERSION, 'source_report_sha256': sha256(raw).hexdigest(),
                'source_manifest_fingerprint': report['manifest_fingerprint'], 'model_digest': DIGEST,
                'notice': 'Validated local artifact, NOT authenticated inference or deployable accuracy.', 'runs': []}
    for repeat, (rows, ai_outputs, scored) in enumerate(runs, 1):
        counts = dict.fromkeys(BUCKETS, 0)
        required = dict.fromkeys(BUCKETS, 0)
        detailed, policy_correct, policy_required = [], 0, 0
        recovery, usable_recovery = 0, 0
        for case, rule, ai, row in zip(cases, rules, ai_outputs, rows):
            input, truth, _, _ = case
            decisive = truth.action_label != 'uncertain'
            action, reason = conservative(rule, ai)
            admitted = row['status'] != 'projection_rejected'
            cohort = bucket(rule.action_label == truth.action_label,
                            ai is not None and ai.action_label == truth.action_label) if decisive else None
            recovered = truth.action_label == 'required' and rule.action_label != 'required' and ai is not None and ai.action_label == 'required'
            if decisive:
                counts[cohort] += 1
                policy_correct += action == truth.action_label
            if truth.action_label == 'required':
                required[cohort] += 1
                policy_required += action == 'required'
            recovery += recovered
            usable_recovery += recovered and ai.relevance_label == 'relevant'
            def error_kind(prediction):
                if prediction is None:
                    return row['status']
                if truth.action_label == 'required' and prediction.action_label != 'required':
                    return 'required_to_' + prediction.action_label
                return 'other_or_correct'
            detailed.append({'id': input.source_record_id, 'expected_action': truth.action_label,
                'expected_relevance': truth.relevance_label, 'rules_action': rule.action_label,
                'ai_action': ai.action_label if ai else None, 'rules_relevance': rule.relevance_label,
                'ai_relevance': ai.relevance_label if ai else None, 'ai_status': row['status'],
                'action_complementarity': cohort, 'rules_error': error_kind(rule), 'ai_error': error_kind(ai),
                'rule_miss_ai_recovery': bool(recovered), 'rules_false_irrelevant': truth.relevance_label == 'relevant' and rule.relevance_label == 'irrelevant',
                'ai_false_irrelevant': ai is not None and truth.relevance_label == 'relevant' and ai.relevance_label == 'irrelevant',
                'policy_action_proposal': action if admitted else None, 'policy_reason': reason if admitted else 'projection_rejected',
                'review_only_no_task_or_clearance': True,
                'ai_possible_action_review_signal': bool(admitted and ai and ai.action_label == 'required')})
        legacy = {'rules': bench.old.metric_records(cases, rules, policy), 'ai': bench.old.metric_records(cases, scored, policy)}
        analysis['runs'].append({'repeat': repeat, 'denominators': {'required': 6, 'decisive_action': 14},
            'legacy_metrics': legacy, 'action_overlap_decisive14': counts, 'required_overlap6': required,
            'recorded_diagnostics_not_remeasured': validate_diagnostics(rows, cases, scored),
            'rule_miss_ai_recovered': recovery, 'recovered_with_relevant_prediction': usable_recovery,
            'oracle_NOT_A_POLICY': {'action_correct': 14 - counts['both_wrong'], 'action_denominator': 14,
                'required_recall_count': 6 - required['both_wrong'], 'required_denominator': 6},
            'conservative_rule_priority': {'action_correct': policy_correct, 'action_denominator': 14,
                'required_recognized': policy_required, 'required_denominator': 6,
                'human_review_proposals': sum(d['policy_action_proposal'] == 'uncertain' for d in detailed),
                'automatic_tasks': 0, 'automatic_dismissals': 0},
            'status_counts': dict(Counter(row['status'] for row in rows)),
            'ai_required_miss_breakdown': dict(Counter(d['ai_error'] for d in detailed if d['expected_action'] == 'required' and d['ai_action'] != 'required')),
            'false_irrelevant': {'rules': sum(d['rules_false_irrelevant'] for d in detailed), 'ai': sum(d['ai_false_irrelevant'] for d in detailed)},
            'cases': detailed})
    return analysis


def summary(analysis, location):
    lines = ['原始37条合成报告：离线一致性校验通过（不是推理真实性认证）。']
    for item in analysis['runs']:
        overlap, legacy, oracle, policy = (item[k] for k in ('action_overlap_decisive14', 'legacy_metrics', 'oracle_NOT_A_POLICY', 'conservative_rule_priority'))
        lines.extend([
            f"第{item['repeat']}次（独立分母14/6，不合并重复）：规则 {legacy['rules']['action_correct_count']}/14；AI {legacy['ai']['action_correct_count']}/14。",
            f"互补：均正确 {overlap['both_correct']}；仅规则 {overlap['rules_only']}；仅AI {overlap['ai_only']}；均错误 {overlap['both_wrong']}。",
            f"6条 required：规则漏判 {legacy['rules']['action_required_miss_count']}/6；AI漏判 {legacy['ai']['action_required_miss_count']}/6；规则漏判而AI识别 {item['rule_miss_ai_recovered']}。",
            f"Oracle事后上限 {oracle['action_correct']}/14；保守策略 {policy['action_correct']}/14（不自动创建任务或忽略事项）。",
            f"错误 irrelevant：规则 {item['false_irrelevant']['rules']}；AI {item['false_irrelevant']['ai']}。AI漏判分项 {json.dumps(item['ai_required_miss_breakdown'], sort_keys=True)}。",
        ])
    lines.append('逐案例诊断：' + location)
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline fixed synthetic report only. No Ollama or arbitrary paths.')
    parser.add_argument('--synthetic-only', required=True, action='store_true')
    parser.parse_args(argv)
    try:
        with files.directory(ROOT) as directory:
            analysis = analyze(directory.read())
            name = 'complementarity-' + uuid4().hex + '.json'
            directory.write(name, json.dumps(analysis, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode('utf-8'))
        location = '/'.join((*files.PARTS, name))
        print(summary(analysis, location))
        return 0
    except (Exception, KeyboardInterrupt):
        print('报告拒绝或分析未完成；请核对固定合成报告、版本、完整覆盖及本地文件权限。未运行模型，未执行报告内容。')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
