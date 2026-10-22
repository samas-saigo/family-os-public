"""Opt-in, fixed-corpus localhost experiment. Never imported by application paths.

This is not the historical runner: explicit thinking controls have new identities.
Only the checked-in 37-case synthetic corpus is accepted; no user-data input exists.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import http.client
import json
import re
import socket
import threading
import time
from uuid import uuid4

from family_os import ollama_synthetic_benchmark as old
from family_os.analysis import AnalysisError, AnalysisOutput, load_classification
from family_os.metadata_classifier import MetadataRulesAnalyzer, load_rules
from family_os.synthetic_reasoning import project_metadata
from family_os.synthetic_reasoning_comparison import FIXTURE, ROOT, _cases

VERSION = 'local-thinking-experiment-v1'
MODELS = ('qwen3:4b-instruct', 'qwen3:8b-q4_K_M')
MODES = ('off', 'on', 'legacy-omitted')
FIXED_OPTIONS = {'temperature': 0, 'seed': 0, 'num_ctx': 4096, 'num_predict': 256}
CORPUS_SHA = '529f81a7adb293ecf89297996ea62237a65a931b8fead1f3f92a2ebea1ac2047'
CONFIG_SHA = {
    'classification.yaml': 'c5c7a324e7c292a268966cb138eeb04804bb39f9e17604011182414f412d9a64',
    'metadata-classifier.yaml': '9a7351aefa078dfb6cb13b4c0d2dfc9464e86f7cc9fae4ea8220ee77895f1d84',
}
PROMPT_SHA = 'ce795381831bceed14df9ca29a30135d0b1293d1060e6a510208925bf5fac14e'
SCHEMA_SHA = 'd732b467076a6ed077a5f02457aa5c2c93f171b8e99b77b4c4d267b5d9daf473'
REQUEST_SECONDS, RUN_SECONDS = 60, 600
API_BYTES = 65536
OUTPUT = ROOT / '.local/local-ai-benchmark'


class ExperimentError(Exception):
    """Content-free errors: never echo response bodies, paths or driver text."""


class Incompatible(ExperimentError):
    pass


def check_config(model, thinking):
    if (type(model) is not str or model not in MODELS or type(thinking) is not str
            or thinking not in MODES or (thinking == 'legacy-omitted' and model != MODELS[0])):
        raise ExperimentError('configuration_rejected')


def wire_json(value):
    # Deliberately separate from durable analysis JSON: the approved synthetic
    # wire envelope contains `prompt`, which durable-record validation forbids.
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def corpus():
    # Git may materialize CRLF on Windows. Identity is the original LF text bytes;
    # no fixture is rewritten and no expected label or projection is changed.
    raw = FIXTURE.read_bytes().replace(b'\r\n', b'\n')
    if wire_json(old.OPTIONS) != wire_json(FIXED_OPTIONS):
        raise ExperimentError('generation_options_changed')
    if sha256(raw).hexdigest() != CORPUS_SHA:
        raise ExperimentError('corpus_identity_rejected')
    for name, expected in CONFIG_SHA.items():
        if sha256((ROOT / 'config' / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() != expected:
            raise ExperimentError('policy_identity_rejected')
    policy = load_classification(ROOT / 'config/classification.yaml')
    cases = _cases(old.strict_json(raw.decode('utf-8')), policy)
    rejected = []
    for input, _, _, _ in cases:
        try:
            project_metadata(input)
        except AnalysisError:
            rejected.append(input.source_record_id)
    if (len(cases) != 37 or set(rejected) != {'synthetic-url', 'synthetic-oversize', 'synthetic-wrong-shape'}
            or old.digest(old.system_prompt(policy, 'flat-domain')) != PROMPT_SHA
            or old.digest(old.schema(policy, 'flat-domain')) != SCHEMA_SHA):
        raise ExperimentError('contract_identity_rejected')
    return policy, cases


def payload(input, policy, model, thinking):
    check_config(model, thinking)
    # Reuse the historical exact prompt/schema construction, not a new prompt.
    value = old.request_payload(project_metadata(input), policy, 'flat-domain')
    value['model'] = model
    if thinking != 'legacy-omitted':
        value['think'] = thinking == 'on'
    return value


class LocalAPI:
    """No configurable address, proxy, redirects, retry, shell, pull or server startup."""

    def request(self, method, path, body=None, *, deadline):
        allowed = {('GET', '/api/version'), ('GET', '/api/tags'), ('GET', '/api/ps'),
                   ('POST', '/api/show'), ('POST', '/api/generate')}
        if (method, path) not in allowed:
            raise ExperimentError('endpoint_rejected')
        if method == 'GET' and body is not None:
            raise ExperimentError('request_rejected')
        if path == '/api/show' and (type(body) is not dict or set(body) != {'model'} or body['model'] not in MODELS):
            raise ExperimentError('request_rejected')
        if path == '/api/generate':
            if type(body) is not dict:
                raise ExperimentError('request_rejected')
            policy, cases = corpus()
            # Exact fixed fixture requests only. Truth and fake scripts never reach HTTP.
            candidates = []
            for input, _, _, _ in cases:
                try:
                    candidates.append(payload(input, policy, body.get('model'),
                                              'on' if body.get('think') is True else
                                              'off' if body.get('think') is False else 'legacy-omitted'))
                except AnalysisError:
                    pass
            if not any(wire_json(body) == wire_json(v) for v in candidates):
                raise ExperimentError('request_rejected')
        connection = timer = None
        try:
            seconds = min(REQUEST_SECONDS, deadline - time.monotonic())
            if seconds <= 0:
                raise ExperimentError('deadline')
            data = wire_json(body).encode() if body is not None else None
            if data is not None and len(data) > old.REQUEST_BYTES:
                raise ExperimentError('request_size')
            connection = http.client.HTTPConnection('127.0.0.1', 11434, timeout=min(5, seconds))
            connection.connect()
            seconds = min(REQUEST_SECONDS, deadline - time.monotonic())
            if seconds <= 0:
                raise ExperimentError('deadline')
            wire = connection.sock
            wire.settimeout(seconds)

            def interrupt():
                try:
                    wire.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

            timer = threading.Timer(seconds, interrupt)
            timer.daemon = True
            timer.start()
            connection.request(method, path, body=data, headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
            response = connection.getresponse()
            if response.status in {400, 422} and path == '/api/generate':
                raise Incompatible('requested_configuration_rejected')
            if response.status != 200:
                raise ExperimentError('api_error')
            raw = response.read(API_BYTES + 1)
            if len(raw) > API_BYTES or time.monotonic() > deadline:
                raise ExperimentError('response_budget')
            value = old.strict_json(raw.decode('utf-8'))
            if type(value) is not dict or 'error' in value:
                raise ExperimentError('api_error')
            return value
        except ExperimentError:
            raise
        except Exception:
            raise ExperimentError('api_or_protocol_error') from None
        finally:
            if timer is not None:
                timer.cancel()
                timer.join()
            if connection is not None:
                connection.close()


def identity(api, model, deadline):
    tags = api.request('GET', '/api/tags', deadline=deadline).get('models')
    if type(tags) is not list or len(tags) > 128:
        raise ExperimentError('inventory_rejected')
    matches = [v for v in tags if type(v) is dict and v.get('name') == model]
    if len(matches) != 1:
        raise ExperimentError('model_missing_or_ambiguous')
    digest = matches[0].get('digest')
    if type(digest) is not str or not re.fullmatch(r'(?:sha256:)?[0-9a-f]{64}', digest):
        raise ExperimentError('model_identity_rejected')
    return digest.removeprefix('sha256:')


def inventory(api, model, deadline):
    if model not in MODELS:
        raise ExperimentError('model_rejected')
    digest = identity(api, model, deadline)
    version = api.request('GET', '/api/version', deadline=deadline).get('version')
    if type(version) is not str or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-.][A-Za-z0-9]+)*', version) or len(version) > 64:
        raise ExperimentError('runtime_rejected')
    show = api.request('POST', '/api/show', {'model': model}, deadline=deadline)
    details = show.get('details', {})
    capabilities = show.get('capabilities', [])
    if type(details) is not dict or type(capabilities) is not list or len(capabilities) > 16:
        raise ExperimentError('capabilities_rejected')
    selected = {k: details.get(k) for k in ('format', 'family', 'parameter_size', 'quantization_level')}
    if any(type(v) is not str or not re.fullmatch(r'[A-Za-z0-9_. +:-]{1,64}', v) for v in selected.values()):
        raise ExperimentError('model_details_unverified')
    if any(type(v) is not str or not re.fullmatch(r'[a-z_]{1,32}', v) for v in capabilities):
        raise ExperimentError('capabilities_rejected')
    if identity(api, model, deadline) != digest:
        raise ExperimentError('model_changed')
    return {'model': model, 'digest': digest, 'ollama_version': version, 'details': selected,
            'capabilities': capabilities, 'historical_weights_verified': False}


def residency(api, model, digest, deadline):
    try:
        values = api.request('GET', '/api/ps', deadline=deadline).get('models', [])
        if type(values) is not list or len(values) > 128:
            return None
        matches = [v for v in values if type(v) is dict and v.get('name') == model
                   and v.get('digest', '').removeprefix('sha256:') == digest]
        if len(matches) != 1:
            return None
        total, gpu = matches[0].get('size'), matches[0].get('size_vram')
        if type(total) is int and type(gpu) is int and 0 <= gpu <= total and total > 0:
            return {'size_bytes': total, 'size_vram_bytes': gpu, 'gpu_fraction': gpu / total}
    except Exception:
        pass
    return None


def parse_envelope(value, model, thinking):
    if type(value) is not dict or value.get('model') != model or value.get('done') is not True:
        raise ExperimentError('protocol_invalid')
    if value.get('done_reason') == 'length':
        raise ExperimentError('budget_truncated')
    trace = value.get('thinking', '')
    if type(trace) is not str or len(trace.encode()) > API_BYTES:
        raise ExperimentError('thinking_invalid')
    if thinking != 'on' and trace != '':
        raise Incompatible('thinking_off_not_observed')
    if thinking == 'on' and not trace.strip():
        raise Incompatible('thinking_on_not_observed')
    # Reuse envelope validation without altering final response. Only the separate
    # thinking field is handled here; an inline reasoning leak is never repaired.
    checked = dict(value, model=old.CANDIDATE_MODEL, thinking='')
    telemetry = old.envelope(checked, old.CANDIDATE_MODEL)
    return telemetry


def run(*, model, thinking, expected_digest, full=False, repeats=1, api=None):
    check_config(model, thinking)
    if (type(expected_digest) is not str or not re.fullmatch('[0-9a-f]{64}', expected_digest)
            or type(full) is not bool or type(repeats) is not int or not 1 <= repeats <= 3):
        raise ExperimentError('configuration_rejected')
    policy, all_cases = corpus()
    cases = all_cases if full else all_cases[:5]
    api = api or LocalAPI()
    deadline = time.monotonic() + RUN_SECONDS
    info = inventory(api, model, deadline)
    if info['digest'] != expected_digest:
        raise ExperimentError('expected_digest_mismatch')
    if thinking != 'legacy-omitted' and 'thinking' not in info['capabilities']:
        raise Incompatible('explicit_thinking_capability_unverified')
    expected_billions = '4' if model == MODELS[0] else '8'
    if (info['details']['family'] != 'qwen3' or info['details']['format'] != 'gguf'
            or not re.fullmatch(expected_billions + r'(?:\.[0-9]+)?B', info['details']['parameter_size'])):
        raise Incompatible('model_architecture_or_size_mismatch')
    if model == MODELS[1] and info['details']['quantization_level'] != 'Q4_K_M':
        raise Incompatible('quantization_mismatch')
    rules = MetadataRulesAnalyzer(load_rules(ROOT / 'config/metadata-classifier.yaml', policy))
    manifest = dict(info, contract=VERSION, thinking=thinking, options=dict(old.OPTIONS),
                    endpoint='/api/generate', wire_variant='flat-domain', corpus_sha256=CORPUS_SHA,
                    prompt_sha256=PROMPT_SHA, schema_sha256=SCHEMA_SHA,
                    configuration_files_sha256=CONFIG_SHA, selected=len(cases), repeats=repeats,
                    budgets={'request_seconds': REQUEST_SECONDS, 'run_seconds': RUN_SECONDS,
                             'response_bytes': API_BYTES, 'final_response_bytes': 4096})
    manifest.update(projection_engine=old.ENGINE_VERSION,
                    projection_schema='metadata_only_v1', rules_fingerprint=rules.ruleset.fingerprint,
                    taxonomy_digest=old.digest(dict(policy.categories)),
                    threshold_digest=old.digest(policy.thresholds.__dict__),
                    scoring='historical-zero-confidence-plus-disjoint-diagnostics-v1')
    projections = []
    for input, _, _, _ in all_cases:
        try:
            projections.append(project_metadata(input).fingerprint)
        except AnalysisError:
            pass
    manifest['projected_inputs_digest'] = old.digest(projections)
    report = {'notice': 'SYNTHETIC ONLY / NOT PRODUCTION QUALITY OR ACTION AUTHORITY',
              'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'manifest': manifest, 'manifest_fingerprint': old.digest(manifest),
              'reference_denominators_full37': {'required': 6, 'decisive_action': 14},
              'residency_before': residency(api, model, expected_digest, deadline),
              'runs': [], 'completed': False, 'identity_verified': False}
    try:
        for repeat in range(repeats):
            outputs = [AnalysisOutput('uncertain', 0.0, None, None, 0.0, 'uncertain', 0.0) for _ in cases]
            rows = []
            report['runs'].append({'repeat': repeat + 1, 'cases': rows})
            for i, (input, truth, _, _) in enumerate(cases):
                row = {'id': input.source_record_id, 'expected': truth.action_label,
                       'status': 'not_sent', 'predicted': None, 'correct': None,
                       'requires_human_confirmation': None, 'false_positive': None,
                       'missed_possible_action': None, 'raw_envelope': None, 'request': None}
                row['json_valid'] = None
                rows.append(row)
                try:
                    request = payload(input, policy, model, thinking)
                except AnalysisError:
                    row['status'] = 'projection_rejected'
                    continue
                if identity(api, model, deadline) != expected_digest:
                    raise ExperimentError('model_changed')
                row['request'] = request
                start = time.monotonic()
                try:
                    result = api.request('POST', '/api/generate', request, deadline=deadline)
                    row['raw_envelope'] = result
                    row['wall_seconds'] = time.monotonic() - start
                    row['telemetry'] = parse_envelope(result, model, thinking)
                    row['thinking_observation'] = ('separate_trace_present' if thinking == 'on'
                                                   else 'trace_absent_not_internal_proof')
                    row['tokens_per_second'] = old.ratio(row['telemetry']['eval_count'],
                        row['telemetry']['eval_duration'] / 1e9 if row['telemetry']['eval_duration'] else None)
                    row['reasoning_token_count'] = None  # API does not provide an independently verified split.
                    row['final_token_count'] = None
                    row['json_valid'] = False
                    old.strict_json(result['response'])
                    row['json_valid'] = True
                    outputs[i] = old.labels(result['response'], input, policy, 'flat-domain')
                    predicted = outputs[i].action_label
                    row.update(status='valid', predicted=predicted, correct=predicted == truth.action_label,
                               requires_human_confirmation=True, uncertainty_retained=predicted == 'uncertain',
                               false_positive=truth.action_label == 'not_required' and predicted == 'required',
                               missed_possible_action=truth.action_label == 'required' and predicted != 'required')
                except Incompatible:
                    row['status'] = 'incompatible'
                    row['wall_seconds'] = time.monotonic() - start
                    raise
                except old.ModelPredictionError:
                    row['status'] = 'invalid_output'
                except (AnalysisError, ExperimentError) as error:
                    row['status'] = ('api_failure' if row['raw_envelope'] is None else
                                     'budget_truncated' if str(error) == 'budget_truncated' else 'invalid_output')
                    if row['status'] == 'api_failure':
                        row['wall_seconds'] = time.monotonic() - start
                        raise ExperimentError('api_failure') from None
                    if 'telemetry' not in row and row['status'] != 'budget_truncated':
                        # Wrong model/envelope/bounds are not classifier errors.
                        # Stop without attributing accuracy to this response stream.
                        row['status'] = 'protocol_failure'
                        raise ExperimentError('response_protocol_failure') from None
            valid = [r for r in rows if r['status'] == 'valid']
            report['runs'][-1].update(
                legacy_metrics={'rules': old.metric_records(cases, [rules.analyze(c[0], policy) for c in cases], policy),
                                'model': old.metric_records(cases, outputs, policy)},
                incremental_domain_coverage=old.incremental_domain_coverage(
                    cases, [rules.analyze(c[0], policy) for c in cases], outputs),
                diagnostics={'status_counts': dict(Counter(r['status'] for r in rows)),
                    'json_validity_rate_sent': old.ratio(sum(r['json_valid'] is True for r in rows),
                                                         sum(r['request'] is not None for r in rows)),
                    'label_validity_rate_sent': old.ratio(len(valid), sum(r['request'] is not None for r in rows)),
                    'required_to_not_required': sum(r['expected'] == 'required' and r['predicted'] == 'not_required' for r in valid),
                    'required_to_uncertain': sum(r['expected'] == 'required' and r['predicted'] == 'uncertain' for r in valid),
                    'uncertain_to_required': sum(r['expected'] == 'uncertain' and r['predicted'] == 'required' for r in valid),
                    'uncertain_to_not_required': sum(r['expected'] == 'uncertain' and r['predicted'] == 'not_required' for r in valid),
                    'required_miss_rate_legacy': old.ratio(
                        sum(h.action_label == 'required' and o.action_label != 'required' for (_, h, _, _), o in zip(cases, outputs)),
                        sum(h.action_label == 'required' for _, h, _, _ in cases)),
                    'not_required_false_positive_rate': old.ratio(sum(r['false_positive'] is True for r in valid),
                        sum(h.action_label == 'not_required' for _, h, _, _ in cases)),
                    'invalid_required_count': sum(r['expected'] == 'required' and r['status'] != 'valid' for r in rows),
                    'confusion_valid_only': dict(Counter(r['expected'] + '->' + r['predicted'] for r in valid)),
                    'valid_only_action_accuracy': old.ratio(sum(r['correct'] for r in valid), len(valid)),
                    'invalid_rate_sent': old.ratio(sum(r['status'] in {'invalid_output', 'budget_truncated'} for r in rows),
                                                   sum(r['request'] is not None for r in rows)),
                    'latency_seconds': old.distribution([r.get('wall_seconds') for r in rows]),
                    'output_token_rate': old.distribution([r.get('tokens_per_second') for r in rows])})
        report['completed'] = True
    except Incompatible as error:
        report['abort_reason'] = str(error)
    except ExperimentError:
        report['abort_reason'] = 'api_deadline_or_identity_failure'
    except KeyboardInterrupt:
        report['abort_reason'] = 'operator_interrupted'
    finally:
        try:
            report['identity_verified'] = identity(api, model, deadline) == expected_digest
        except Exception:
            pass
        report['residency_after'] = residency(api, model, expected_digest, deadline)
        if not report['identity_verified']:
            report['completed'] = False
            report['abort_reason'] = 'final_identity_unverified'
            for item in report['runs']:
                item.pop('legacy_metrics', None)
                item.pop('diagnostics', None)
                item.pop('incremental_domain_coverage', None)
        first = report['runs'][0]['cases'] if report['runs'] else []
        pairs = [(a, c) for item in report['runs'][1:] for a, c in zip(first, item['cases'])
                 if a['status'] == c['status'] == 'valid']
        report['repeat_comparison'] = {
            'valid_pairs': len(pairs),
            'action_disagreements': sum(a['predicted'] != c['predicted'] for a, c in pairs),
        } if report['identity_verified'] else None
        for item in report['runs']:
            item['coverage'] = {'selected': len(cases), 'recorded': len(item['cases']),
                                'not_attempted': len(cases) - len(item['cases']),
                                'status_counts': dict(Counter(r['status'] for r in item['cases']))}
    return report


def save(report):
    directory = OUTPUT / uuid4().hex
    directory.mkdir(parents=True, mode=0o700)
    path = directory / 'report.json'
    # New run directory; never read/resume reports or overwrite earlier results.
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2)
    return path.relative_to(ROOT).as_posix()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Manual fixed synthetic Ollama experiment; no household data.')
    parser.add_argument('--synthetic-only', required=True, action='store_true')
    parser.add_argument('--model', choices=MODELS, required=True)
    parser.add_argument('--thinking', choices=MODES)
    parser.add_argument('--inventory', action='store_true', help='Read model/runtime metadata without generation')
    parser.add_argument('--expected-digest', help='Exact current SHA-256 from inventory, not historical identity proof')
    parser.add_argument('--full', action='store_true', help='Explicit original 37-case run; smoke is first five')
    parser.add_argument('--repeats', type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args(argv)
    try:
        if args.inventory:
            if args.thinking or args.expected_digest or args.full or args.repeats != 1:
                raise ExperimentError('inventory_configuration_rejected')
            result = inventory(LocalAPI(), args.model, time.monotonic() + REQUEST_SECONDS)
            print(old.canonical_json(result))
            return 0
        result = run(model=args.model, thinking=args.thinking, expected_digest=args.expected_digest,
                     full=args.full, repeats=args.repeats)
        location = save(result)
        summary = {k: v for k, v in result.items() if k != 'runs'}
        summary['runs'] = [{k: v for k, v in item.items() if k != 'cases'} for item in result['runs']]
        print(old.canonical_json(dict(summary, local_report=location)))
        return 0 if result['completed'] else 1
    except Incompatible:
        print('INCOMPATIBLE: explicit requested thinking/model configuration is unverified. No fallback.')
        return 2
    except (Exception, KeyboardInterrupt):
        print('Synthetic experiment failed; no automatic retry. Check local metadata, compatibility and budgets.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
