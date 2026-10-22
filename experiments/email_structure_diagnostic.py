"""Six fixed synthetic cases: finite rejection annotations, never accuracy scoring."""
import argparse
from collections import Counter
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import time
from uuid import uuid4

from experiments import email_model_compat as prior

compat, parent, wording, engine = prior.compat, prior.parent, prior.wording, prior.engine
ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path('experiments/configs/synthetic-email-structure-diagnostic-v1.json')
CONFIG_SHA = '3e756cd1112e27a9acb6a00dc93c6b665eeda0196f0de7aedf701e6ea27c6741'
FREEZE = '0d1a2c80c1c4e1feababca56e2697b4bfe1124a2'
EXPERIMENT = 'synthetic-email-structure-diagnostic-v1'
LOCAL = Path('.local/email-structure-diagnostic-v1')
REPORT_BYTES = 524288
SELECTED = ('WC01-1', 'WC01-3', 'WC05-1', 'WC10-1', 'WC11-1', 'WC12-1')
SOURCE_PINS = {'experiments/single_email_compat.py': '124d71d0cbb2120bd60921d341d45df64582023701c45ce4e90724dd622dd3b3', 'experiments/configs/single-email-runtime-diagnostic-v2.json': '461b7e83eb51798aa261446c440c20a0908963b40fd4902bd14cd61ac1332aa7', 'experiments/single_email_diagnostic.py': 'b5451e7b0c971602d234b0c137a0eb8f9e96b90fb9a666bdb643707c26f95ca3', 'experiments/email_model_evidence.py': 'b0b1dc39f974af8c6f3c74cefeee4950663e83f8bc7bacff006a9c05aa035fd8', 'experiments/email_model_compat.py': '5406859b660fa5a7c2c75b1e96d8511d697678cae0e8b9a012e75f00911a730e', 'experiments/configs/synthetic-email-model-evidence-v2.json': '3088c54578456f242846164b8b121c3311f49d536c3f41789ff3dde04dc11042'}
REASONS = ('not_obtained', 'not_applicable', 'none', 'unknown', 'content_encoding', 'field_set', 'field_type', 'enum', 'cardinality', 'duplicate_action', 'state_steps', 'date_value', 'date_action_binding', 'date_state_relation', 'notice_kind_relation')
need, Error = parent.need, parent.ExperimentError
read_bounded = prior.read_bounded


def setup():
    need(ROOT == prior.ROOT and Path(prior.__file__).absolute() == ROOT / 'experiments/email_model_compat.py', 'input_rejected')
    for path, expected in {CONFIG.as_posix(): CONFIG_SHA, **SOURCE_PINS}.items():
        raw = read_bounded(ROOT / path, 65536).replace(b'\r\n', b'\n')
        need(sha256(raw).hexdigest() == expected, 'input_rejected')
    config = parent.strict_json(read_bounded(ROOT / CONFIG, 65536).decode('utf-8'))
    previous, wire, corpus = prior.setup()  # No old run(), scoring or report reads.
    need(config['source_pins'] == SOURCE_PINS, 'input_rejected')
    need(all(config[k] == previous[k] for k in ('model', 'prompt', 'output_schema', 'generation', 'limits', 'runtime_version')), 'input_rejected')
    need(tuple(config['input']['selected_ids']) == SELECTED and tuple(config['diagnostic']['reasons']) == REASONS, 'input_rejected')
    selected = [next(c for c in corpus if c['id'] == i) for i in SELECTED]
    return config, wire, selected


def _constraint(raw, projection):
    # Annotation only. Never called to decide acceptance. No invalid data leaves
    # this function, including exception messages, unknown keys or original values.
    try:
        raw.encode('utf-8')
    except UnicodeError:
        return 'content_encoding'
    v = parent.strict_json(raw)
    if type(v) is not dict or set(v) != {'state', 'steps', 'dates'}:
        return 'field_set'
    if type(v['state']) is not str or type(v['steps']) is not list or type(v['dates']) is not list:
        return 'field_type'
    if len(v['steps']) > 2 or len(v['dates']) > 1:
        return 'cardinality'
    for item in v['steps']:
        if type(item) is not dict or set(item) != {'action', 'status'}:
            return 'field_set'
        if not all(type(x) is str for x in item.values()):
            return 'field_type'
    for item in v['dates']:
        if type(item) is not dict or set(item) != {'role', 'value', 'action'}:
            return 'field_set'
        if type(item['role']) is not str or type(item['value']) is not str or (item['action'] is not None and type(item['action']) is not str):
            return 'field_type'
    if v['state'] not in set(engine.State):
        return 'enum'
    for s in v['steps']:
        if s['action'] not in set(engine.Action) or s['status'] not in set(engine.Status):
            return 'enum'
    for d in v['dates']:
        if d['role'] not in set(engine.DateRole) or (d['action'] is not None and d['action'] not in set(engine.Action)):
            return 'enum'
        try:
            if not re.fullmatch(r'20[0-9]{2}-[0-9]{2}-[0-9]{2}', d['value']) or not 2015 <= date.fromisoformat(d['value']).year <= 2035:
                return 'date_value'
        except ValueError:
            return 'date_value'
        if (d['action'] is not None) != (d['role'] in ('due_date', 'reported_completion_date')):
            return 'date_action_binding'
    if len({s['action'] for s in v['steps']}) != len(v['steps']):
        return 'duplicate_action'
    state, steps, dates = v['state'], v['steps'], v['dates']
    if state == 'abstain':
        return 'state_steps' if steps or dates else 'unknown'
    if projection.fields['notice_kind'] != ('promotional' if state == 'promotional' else 'service'):
        return 'notice_kind_relation'
    if (state == 'explicit_outstanding' and not any(s['status'] == 'reported_outstanding' for s in steps)
        or state == 'explicit_completion' and (not steps or not all(s['status'] == 'reported_completed' for s in steps))
        or state == 'informational' and not all(s['status'] in ('reported_failed', 'reported_cancelled') for s in steps)
        or state == 'promotional' and steps):
        return 'state_steps'
    for d in dates:
        if d['role'] in ('due_date', 'reported_completion_date'):
            wanted_state, wanted_status = ('explicit_outstanding', 'reported_outstanding') if d['role'] == 'due_date' else ('explicit_completion', 'reported_completed')
            if state != wanted_state:
                return 'date_state_relation'
            if not any(s['action'] == d['action'] and s['status'] == wanted_status for s in steps):
                return 'date_action_binding'
        elif state != ('promotional' if d['role'] == 'offer_expiry' else 'informational'):
            return 'date_state_relation'
    return 'unknown'


def response_result(value, projection, limits):
    out = compat.response_result(value, projection, limits)  # Sole authority, unchanged.
    reason = 'none' if out['status'] == 'valid' else 'not_applicable'
    if out['status'] == 'invalid_structure' and out['subreason'] == 'prediction_structure':
        try:
            reason = _constraint(value['message']['content'], projection)
            if reason not in REASONS[3:]:
                reason = 'unknown'
        except Exception:
            reason = 'unknown'
    return dict(out, structure_reason=reason)


class Transport(compat.old.Transport):
    def __init__(self, config, case_id, deadline):
        expected, wire, selected = setup()
        need(config == expected and case_id in SELECTED, 'input_rejected')
        case = next(c for c in selected if c['id'] == case_id)
        self.config, self.limits, self.deadline = wire, config['limits'], deadline
        self.allowed = {wording.canonical(dict(engine.EmailMetadata(case['input']).fields))}
        self.chat_attempts, self.requests = 0, []


def run():
    started = time.monotonic()
    config, _, selected = setup()
    deadline = started + config['limits']['run_seconds']
    rows = []
    for c in selected:
        empty = compat.empty_observation()
        empty.pop('prediction')
        rows.append(dict(id=c['id'], **empty, structure_reason='not_obtained', attempted=False,
                         chat_response_seconds=None, validation_seconds=None))
    clients = [Transport(config, selected[0]['id'], deadline)]
    initial, final, resident, stopped, tainted = None, None, None, None, False

    def observe(client):
        nonlocal tainted
        try:
            value = client.identity()
            need(value['runtime_version'] == config['runtime_version'] and (initial is None or value == initial), 'identity_unverified')
            return value
        except (Error, KeyboardInterrupt):
            tainted = True
            raise
    try:
        initial = observe(clients[0])
        resident = clients[0].residency()
        for index, (c, row) in enumerate(zip(selected, rows, strict=True)):
            if index:
                clients.append(Transport(config, c['id'], deadline))
            client = clients[-1]
            observe(client)
            projection = engine.EmailMetadata(c['input'])
            payload = client.payload(projection)
            row['attempted'] = True
            begin = time.monotonic()
            try:
                response = client.request('POST', '/api/chat', payload)
                row['chat_response_seconds'] = round(max(0, time.monotonic() - begin), 6)
                validate_begin = time.monotonic()
                try:
                    observation = response_result(response, projection, config['limits'])
                    observation.pop('prediction')  # Neither valid predictions nor invalid strings are reported.
                    row.update(observation)
                    tainted |= row['status'] == 'identity_unverified'
                    client.remaining()
                finally:
                    row['validation_seconds'] = round(max(0, time.monotonic() - validate_begin), 6)
                if row['status'] != 'valid' and row['status'] not in config['protocol']['ordinary_failures_continue']:
                    stopped = row['status']
                    break
            except (Error, KeyboardInterrupt) as exc:
                code = exc.code if isinstance(exc, Error) else 'interrupted'
                row.update(status=code, subreason='reply_identity' if code == 'identity_unverified' else 'transport_boundary', structure_reason='not_applicable')
                row['chat_response_seconds'] = round(max(0, time.monotonic() - begin), 6)
                raise
    except Error as exc:
        stopped = exc.code
        tainted |= exc.code == 'identity_unverified'
    except KeyboardInterrupt:
        stopped = 'interrupted'
    finally:
        try:
            final = observe(clients[-1])
            if initial is None or final != initial:
                tainted = True
        except Error as exc:
            final = None
            if stopped is None: stopped = exc.code
        except KeyboardInterrupt:
            tainted = True
            if stopped is None: stopped = 'interrupted'
    verified = initial is not None and final == initial and not tainted
    complete = all(r['attempted'] for r in rows) and stopped is None and verified
    return dict(experiment=EXPERIMENT, freeze_commit=FREEZE, config_lf_sha256=CONFIG_SHA,
                source_pins=SOURCE_PINS,
                prompt_sha256=sha256(config['prompt'].encode()).hexdigest(),
                schema_sha256=sha256(wording.canonical(config['output_schema']).encode()).hexdigest(),
                mode='diagnose', run_status='complete' if complete else 'partial', stop_code=stopped,
                identity_verified_at_end=verified, observed_identity=final if verified else None,
                prediction_attribution='observed_candidate' if verified else 'unattributed_diagnostic',
                configured_candidate=config['model'], generation=config['generation'], limits=config['limits'],
                initial_residency=resident, total_elapsed_seconds=round(max(0, time.monotonic() - started), 6),
                telemetry_scope='validated_shape_and_budget_only; server_claim_not_ground_truth',
                selected=dict(cases=6), attempted=sum(r['attempted'] for r in rows),
                status_counts=dict(Counter(r['status'] for r in rows)),
                attributed_constraint_counts=dict(Counter(r['structure_reason'] for r in rows)) if verified else None,
                root_cause='unknown', metrics_scope='not_accuracy_evaluation', cases=rows,
                requests=[dict(request, case_id=c['id'] if request['endpoint'] == '/api/chat' else None) for client, c in zip(clients, selected) for request in client.requests],
                restrictions=dict(authority='none', sender_claim_only=True, human_review_required=True,
                                  independent_safety_and_authorization_required=True),
                notice='NEW STRUCTURE DIAGNOSTIC ONLY; CANNOT INFER HISTORICAL20 CAUSES; NOT ACCURACY; NO POOLING OR ACTIONS')


def encoded(report):
    return (wording.canonical(report) + '\n').encode('utf-8')


def save(report):
    raw = encoded(report)
    need(len(raw) <= REPORT_BYTES, 'resource_limit')
    target = ROOT / LOCAL
    for p in (ROOT / '.local', target):
        wording.parents(p); p.mkdir(mode=0o700, exist_ok=True); wording.regular(p, True)
    directory = target / uuid4().hex
    directory.mkdir(mode=0o700)
    temporary, path = directory / 'report.json.tmp', directory / 'report.json'
    created = False
    try:
        with temporary.open('xb') as stream:
            created = True; stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if created:
            try: temporary.unlink(missing_ok=True)
            except OSError: pass
        try: directory.rmdir()
        except OSError: pass
        raise
    return path.relative_to(ROOT).as_posix()


def read_report(run_id, expected_sha):
    # No arbitrary file input. Expected hash comes from the original console output.
    need(type(run_id) is str and re.fullmatch('[0-9a-f]{32}', run_id), 'input_rejected')
    need(type(expected_sha) is str and re.fullmatch('[0-9a-f]{64}', expected_sha), 'input_rejected')
    raw = read_bounded(ROOT / LOCAL / run_id / 'report.json', REPORT_BYTES)
    need(sha256(raw).hexdigest() == expected_sha, 'input_rejected')
    report = parent.strict_json(raw.decode('utf-8'))
    need(type(report) is dict and report.get('experiment') == EXPERIMENT and report.get('config_lf_sha256') == CONFIG_SHA and report.get('freeze_commit') == FREEZE and report.get('source_pins') == SOURCE_PINS, 'input_rejected')
    need(encoded(report) == raw, 'input_rejected')
    return report


def collect():
    report, path, expected, error, verified, experiment_code = None, None, None, None, False, None
    try:
        report = run()  # Exactly one run, no retry or automatic full.
        experiment_code = 0 if report['run_status'] == 'complete' else 2
        expected = sha256(encoded(report)).hexdigest()
        path = save(report)
        loaded = read_report(Path(path).parent.name, expected)
        need(loaded == report, 'input_rejected')
        verified = True
    except (Exception, KeyboardInterrupt):
        error = 'experiment_or_publication_or_readback_failed'
    return dict(workflow=EXPERIMENT, operation='diagnose', workflow_exit_code=1 if error else experiment_code,
                experiment_exit_code=experiment_code, error_code=error, report_path=path,
                report_sha256=expected, report_read_verified=verified,
                report_source='published_readback' if verified else 'retained_in_memory', report=report)


def version():
    return sys.version_info[:3]


def main(argv=None):
    parser = argparse.ArgumentParser(description='Six fixed cases: structure diagnostics only; manual, no retry')
    parser.add_argument('--synthetic-only', action='store_true', required=True)
    modes = parser.add_subparsers(dest='mode', required=True)
    modes.add_parser('diagnose')
    recovery = modes.add_parser('recover', help='Read prior report only; never requests inference')
    recovery.add_argument('run_id'); recovery.add_argument('expected_sha256')
    args = parser.parse_args(argv)
    if version() != (3, 12, 10):
        result = dict(workflow=EXPERIMENT, workflow_exit_code=1, error_code='python_version_mismatch', report=None)
    elif args.mode == 'recover':
        try:
            report = read_report(args.run_id, args.expected_sha256)
            result = dict(workflow=EXPERIMENT, operation='recover', workflow_exit_code=0,
                          experiment_exit_code=0 if report['run_status'] == 'complete' else 2,
                          error_code=None, report_path=(LOCAL / args.run_id / 'report.json').as_posix(),
                          report_sha256=args.expected_sha256, report_read_verified=True,
                          report_source='published_readback', report=report)
        except (Exception, KeyboardInterrupt):
            result = dict(workflow=EXPERIMENT, operation='recover', workflow_exit_code=1,
                          error_code='report_recovery_failed', report=None)
    else:
        result = collect()
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return result['workflow_exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
