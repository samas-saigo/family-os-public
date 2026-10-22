"""Manual wording36 semantic comparison using pinned PR109 validation. Mock-only CI."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import time
from uuid import uuid4

from experiments import single_email_compat as compat

parent, wording, engine = compat.parent, compat.wording, compat.engine
ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path('experiments/configs/synthetic-email-model-evidence-v2.json')
CONFIG_SHA = '3088c54578456f242846164b8b121c3311f49d536c3f41789ff3dde04dc11042'
FREEZE = '5c82246c031a606c71b0f848f98053faf97d09e5'
EXPERIMENT = 'synthetic-email-model-evidence-v2-ollama0406'
LOCAL = Path('.local/email-model-evidence-v2')
REPORT_BYTES = 524288
SOURCE_PINS = {
    'experiments/single_email_compat.py': '124d71d0cbb2120bd60921d341d45df64582023701c45ce4e90724dd622dd3b3',
    'experiments/configs/single-email-runtime-diagnostic-v2.json': '461b7e83eb51798aa261446c440c20a0908963b40fd4902bd14cd61ac1332aa7',
    'experiments/single_email_diagnostic.py': 'b5451e7b0c971602d234b0c137a0eb8f9e96b90fb9a666bdb643707c26f95ca3',
    'experiments/email_model_evidence.py': 'b0b1dc39f974af8c6f3c74cefeee4950663e83f8bc7bacff006a9c05aa035fd8',
}
need, Error = parent.need, parent.ExperimentError


def read_bounded(path, maximum):
    wording.parents(path)
    before = wording.regular(path)
    need(before.st_size <= maximum, 'resource_limit')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        handle = os.fstat(stream.fileno())
        need(wording.cross_api_identity(handle) == wording.cross_api_identity(before), 'input_rejected')
        raw = stream.read(maximum + 1)
        need(wording.identity(handle) == wording.identity(os.fstat(stream.fileno())), 'input_rejected')
    need(len(raw) <= maximum and wording.identity(before) == wording.identity(wording.regular(path)), 'input_rejected')
    return raw


def setup():
    need(ROOT == compat.ROOT and Path(compat.__file__).absolute() == ROOT / 'experiments/single_email_compat.py', 'input_rejected')
    for path, expected in {CONFIG.as_posix(): CONFIG_SHA, **SOURCE_PINS}.items():
        raw = read_bounded(ROOT / path, 65536).replace(b'\r\n', b'\n')
        need(sha256(raw).hexdigest() == expected, 'input_rejected')
    config = parent.strict_json(read_bounded(ROOT / CONFIG, 65536).replace(b'\r\n', b'\n').decode('utf-8'))
    previous, original, _ = compat.setup()  # Its original single-case setup stays unchanged.
    wire, cases = parent.setup()  # Its only fixed wording loader, not any split/PR104 loader.
    need(config['source_pins'] == SOURCE_PINS and wire == original, 'input_rejected')
    need(all(config[k] == previous[k] for k in ('model', 'prompt', 'output_schema', 'generation')), 'input_rejected')
    need(config['smoke'] == wire['smoke'] and config['input'] == wire['input'], 'input_rejected')
    return config, wire, cases


def select(config, cases, mode):
    need(mode in ('smoke', 'full'), 'input_rejected')
    return cases if mode == 'full' else [next(c for c in cases if c['id'] == i) for i in config['smoke']]


class Transport(compat.old.Transport):
    """Unchanged, one-chat-only request method; a fresh instance per fixed case.

    Never reset the inherited counter or alter a frozen constructor/config. Each
    instance permits only its selected case projection and the pinned wire payload.
    """
    def __init__(self, config, mode, case_id, deadline):
        expected, wire, cases = setup()
        need(config == expected, 'input_rejected')
        selected = [c for c in select(config, cases, mode) if c['id'] == case_id]
        need(len(selected) == 1, 'input_rejected')
        self.config, self.limits, self.deadline = wire, config['limits'], deadline
        self.allowed = {wording.canonical(dict(engine.EmailMetadata(selected[0]['input']).fields))}
        self.chat_attempts, self.requests = 0, []


def run(mode):
    started = time.monotonic()
    config, _, corpus = setup()
    selected = select(config, corpus, mode)
    deadline = started + config['limits']['run_seconds']
    rows, rules = [], []
    for c in selected:
        base = {k: c[k] for k in ('id', 'group', 'variant', 'reference')}
        empty = compat.empty_observation()
        empty.pop('prediction')
        rows.append(dict(base, **empty, actual=None, attempted=False,
                         chat_response_seconds=None, validation_seconds=None))
        rule = dict(base, status='interpreter_error', actual=None, reason=None)
        try:
            p = engine.EmailMetadata(c['input'])
            result = engine.interpret(p)
        except engine.EmailEvidenceError:
            rule['status'] = 'input_rejected'
        except Exception:
            pass  # Finite interpreter_error, still in the original scorer denominator.
        else:
            try:
                engine.validate_result(result, p)
                rule.update(status='valid', actual=wording.signature(result), reason=result.reason.value)
            except Exception:
                rule['status'] = 'invalid_output'
        rules.append(rule)
    clients = [Transport(config, mode, selected[0]['id'], deadline)]
    initial, final, resident, stopped, tainted = None, None, None, None, False

    def observe(client):
        nonlocal tainted
        try:
            value = client.identity()
            need(value['runtime_version'] == config['runtime_version'] and (initial is None or value == initial), 'identity_unverified')
            return value
        except (Error, KeyboardInterrupt):
            # An interrupted observation cannot establish identity; latch before
            # propagating. A later successful observation must not restore it.
            tainted = True
            raise
    try:
        initial = observe(clients[0])
        resident = clients[0].residency()
        for index, (c, row) in enumerate(zip(selected, rows, strict=True)):
            if index:
                clients.append(Transport(config, mode, c['id'], deadline))
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
                    observation = compat.response_result(response, projection, config['limits'])
                    row['actual'] = observation.pop('prediction')
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
                row.update(status=code, subreason='reply_identity' if code == 'identity_unverified' else 'transport_boundary')
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
    metrics = parent.score(rows) if verified else None
    return dict(experiment=EXPERIMENT, freeze_commit=FREEZE, config_lf_sha256=CONFIG_SHA,
                source_pins=SOURCE_PINS, input_fixture_lf_sha256=wording.FIXTURE_SHA256,
                prompt_sha256=sha256(config['prompt'].encode()).hexdigest(),
                schema_sha256=sha256(wording.canonical(config['output_schema']).encode()).hexdigest(),
                interpreter_version=wording.VERSION, interpreter_lf_sha256=wording.ENGINE_SHA256,
                rule_fingerprint=wording.RULE_FINGERPRINT, scorer_lf_sha256=parent.SCORER_SHA,
                mode=mode, run_status='complete' if complete else 'partial', stop_code=stopped,
                identity_verified_at_end=verified, observed_identity=final if verified else None,
                prediction_attribution='observed_candidate' if verified else 'unattributed_diagnostic',
                configured_candidate=config['model'], generation=config['generation'], limits=config['limits'],
                initial_residency=resident, total_elapsed_seconds=round(max(0, time.monotonic() - started), 6),
                telemetry_scope='validated_shape_and_budget_only; server_claim_not_ground_truth',
                corpus=dict(cases=36, clear=24, ambiguous=12, groups=12),
                selected=dict(cases=len(rows), clear=sum(r['variant'] != 'ambiguous' for r in rows),
                              ambiguous=sum(r['variant'] == 'ambiguous' for r in rows), groups=len({r['group'] for r in rows})),
                attempted=sum(r['attempted'] for r in rows), status_counts=dict(Counter(r['status'] for r in rows)),
                metrics_scope='same_selection_complete_execution' if complete else 'partial_selected_denominators_only; no_complete_comparison',
                model_metrics=metrics,
                by_group={g: parent.score([r for r in rows if r['group'] == g]) for g in wording.GROUPS if any(r['group'] == g for r in rows)} if verified else None,
                rule_metrics=wording.summarize(rules),
                rule_by_group={g: wording.summarize([r for r in rules if r['group'] == g]) for g in wording.GROUPS if any(r['group'] == g for r in rules)},
                comparison=parent.compare(rules, rows) if complete and all(r['status'] == 'valid' for r in rules) else None,
                cases=rows, rule_cases=rules,
                requests=[dict(request, case_id=c['id'] if request['endpoint'] == '/api/chat' else None) for client, c in zip(clients, selected) for request in client.requests],
                restrictions=dict(authority='none', sender_claim_only=True, human_review_required=True,
                                  independent_safety_and_authorization_required=True),
                notice='SEEN CORRELATED SYNTHETIC CASES; NOT BLIND/INDEPENDENT/REAL-WORLD ACCURACY; NO POOLING OR ACTIONS')


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


def collect(mode):
    report, path, expected, error, verified, experiment_code = None, None, None, None, False, None
    try:
        report = run(mode)  # Exactly one run, no retry or automatic full.
        experiment_code = 0 if report['run_status'] == 'complete' else 2
        expected = sha256(encoded(report)).hexdigest()
        path = save(report)
        loaded = read_report(Path(path).parent.name, expected)
        need(loaded == report, 'input_rejected')
        verified = True
    except (Exception, KeyboardInterrupt):
        error = 'experiment_or_publication_or_readback_failed'
    return dict(workflow=EXPERIMENT, operation=mode, workflow_exit_code=1 if error else experiment_code,
                experiment_exit_code=experiment_code, error_code=error, report_path=path,
                report_sha256=expected, report_read_verified=verified,
                report_source='published_readback' if verified else 'retained_in_memory', report=report)


def version():
    return sys.version_info[:3]


def main(argv=None):
    parser = argparse.ArgumentParser(description='Compatible synthetic wording comparison; manual, no retry')
    parser.add_argument('--synthetic-only', action='store_true', required=True)
    modes = parser.add_subparsers(dest='mode', required=True)
    modes.add_parser('smoke'); modes.add_parser('full')
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
        result = collect(args.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return result['workflow_exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
