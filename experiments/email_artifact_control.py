"""One frozen A/B artifact comparison. Offline preparation; no default real execution."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from types import FunctionType, SimpleNamespace

from experiments import email_structure_diagnostic as diagnostic

parent, wording, engine = diagnostic.parent, diagnostic.wording, diagnostic.engine
compat, prior = diagnostic.compat, diagnostic.prior
need, Error, read_bounded = parent.need, parent.ExperimentError, prior.read_bounded
ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = 'email-model-artifact-control-v1'
FREEZE = '29ad25c947827c115a6e8d3ef72315186556deb7'
CONFIG = Path('experiments/configs/email-model-artifact-control-v1.json')
CONFIG_SHA = 'c2e41c00cc7559f9deaf1588e5c9f615eddf12438606679d1b615bccf5c9c55f'
LOCAL = Path('.local/email-model-artifact-control-v1')
REPORT_BYTES = 524288
STAGES = (('smoke', 'A'), ('smoke', 'B'), ('full', 'A'), ('full', 'B'))
SHA = r'[0-9a-f]{40}'


def clone(function, **overrides):
    """Detached globals, same audited bytecode. Never modify a frozen module."""
    need(function.__closure__ is None, 'input_rejected')
    return FunctionType(function.__code__, dict(function.__globals__, **overrides),
                        function.__name__, function.__defaults__)


def signature_wire(signature):
    return dict(state=signature['state'],
                steps=[dict(zip(('action', 'status'), s, strict=True)) for s in signature['steps']],
                dates=[dict(zip(('role', 'value', 'action'), d, strict=True)) for d in signature['dates']])


def validate_cases(items, mode):
    need(mode in ('smoke', 'full') and type(items) is list, 'input_rejected')
    n, prefix = (24, 'eval') if mode == 'full' else (2, 'smoke')
    need(len(items) == n, 'input_rejected')
    for i, c in enumerate(items, 1):
        need(type(c) is dict and set(c) == {'id', 'group', 'variant', 'input', 'gold', 'rationale'}, 'input_rejected')
        need(c['id'] == f'{prefix}-{i:02}' and c['group'] == (f'g{(i-1)//3+1}' if mode == 'full' else f's{i}'), 'input_rejected')
        ambiguous = i % 3 == 0 if mode == 'full' else i == 2
        need(c['variant'] == ('ambiguous' if ambiguous else 'clear'), 'input_rejected')
        need(set(c['input']) == {'schema', 'provider', 'record_type', 'notice_kind', 'subject', 'synthetic_only'}, 'input_rejected')
        projection = engine.EmailMetadata(c['input'])
        gold = c['gold']
        need(type(gold) is dict and set(gold) == {'state', 'steps', 'dates'}, 'input_rejected')
        parsed = parent.parse_prediction(wording.canonical(signature_wire(gold)), projection).signature()
        need(parsed == gold and (gold['state'] == 'abstain') == ambiguous, 'input_rejected')
        need(set(re.findall(r'20\d{2}-\d{2}-\d{2}', c['input']['subject'])) == {d[1] for d in gold['dates']}, 'input_rejected')
    need(len({c['input']['subject'] for c in items}) == n, 'input_rejected')
    if mode == 'full':
        need(Counter(c['gold']['state'] for c in items) == Counter(explicit_outstanding=8, explicit_completion=3, informational=4, promotional=1, abstain=8), 'input_rejected')
        need(Counter(d[0] for c in items for d in c['gold']['dates']) == Counter(due_date=3, reported_completion_date=2, event_date=1, available_date=1, offer_expiry=1), 'input_rejected')
        need({s[0] for c in items for s in c['gold']['steps']} == set(engine.Action), 'input_rejected')
        need({s[1] for c in items for s in c['gold']['steps']} == set(engine.Status), 'input_rejected')
        doubles = {c['id']: tuple(s[1] for s in c['gold']['steps']) for c in items if c['gold']['state'] == 'explicit_outstanding' and len(c['gold']['steps']) == 2}
        need(doubles == {'eval-02': ('reported_failed','reported_outstanding'), 'eval-04': ('reported_cancelled','reported_outstanding'), 'eval-14': ('reported_completed','reported_outstanding'), 'eval-16': ('reported_outstanding','reported_outstanding')}, 'input_rejected')
        info = [c for c in items if c['gold']['state'] == 'informational']
        need(any(c['gold']['steps'] for c in info) and any(not c['gold']['steps'] for c in info), 'input_rejected')
    else:
        need(items[0]['gold']['state'] == 'explicit_outstanding' and len(items[0]['gold']['steps']) == 2 and len(items[0]['gold']['dates']) == 1 and items[0]['gold']['dates'][0][0] == 'due_date', 'input_rejected')
    return items


def setup():
    source_root = Path(__file__).resolve().parents[1]
    for module, path in ((parent,'experiments/email_model_evidence.py'),
                         (wording,'experiments/email_wording_challenge.py'),
                         (engine,'src/family_os/_synthetic_email_evidence.py'),
                         (compat,'experiments/single_email_compat.py'),
                         (compat.old,'experiments/single_email_diagnostic.py'),
                         (prior,'experiments/email_model_compat.py'),
                         (diagnostic,'experiments/email_structure_diagnostic.py')):
        need(Path(module.__file__).absolute() == source_root / path, 'input_rejected')
    raw = read_bounded(ROOT / CONFIG, 65536).replace(b'\r\n', b'\n')
    need(sha256(raw).hexdigest() == CONFIG_SHA, 'input_rejected')
    config = parent.strict_json(raw.decode('utf-8'))
    for path, expected in config['source_pins'].items():
        raw = read_bounded(ROOT / path, 65536).replace(b'\r\n', b'\n')
        need(sha256(raw).hexdigest() == expected, 'input_rejected')
    baseline = parent.strict_json(read_bounded(ROOT / 'experiments/configs/synthetic-email-semantic-prompt-v1.json', 65536).decode('utf-8'))
    need(sha256(baseline['prompt'].encode()).hexdigest() == '5008dbe3028f54869e9234b809699123e1f478544c9c40d450a11312f8fe8bed', 'input_rejected')
    need(sha256(wording.canonical(baseline['output_schema']).encode()).hexdigest() == 'e0e6d820eb846139116df553962b5d884d0a94e9192df892f6f71b0cf9799083', 'input_rejected')
    corpora = {}
    for mode, pin in config['fixtures'].items():
        raw = read_bounded(ROOT / 'fixtures/email-model-artifact-control-v1' / pin['file'], 65536).replace(b'\r\n', b'\n')
        need(b'\r' not in raw and sha256(raw).hexdigest() == pin['sha256'], 'input_rejected')
        corpora[mode] = validate_cases(parent.strict_json(raw.decode('utf-8'))['items'], mode)
    need(not {c['input']['subject'] for c in corpora['smoke']} & {c['input']['subject'] for c in corpora['full']}, 'input_rejected')
    need(int(config['fixtures']['full']['sha256'][0], 16) % 2 == 0 and config['order'] == ['A','B'], 'input_rejected')
    for c in corpora['full'] + corpora['smoke']:
        text = wording.canonical(dict(engine.EmailMetadata(c['input']).fields))
        bound = len(baseline['prompt'].encode()) + len(text.encode()) + 1024 + 512
        need(bound <= 4096, 'resource_limit')
        for arm in ('A', 'B'):
            payload = dict(model=config['models'][arm]['tag'], messages=[dict(role='system', content=baseline['prompt']), dict(role='user', content=text)], format=baseline['output_schema'], **baseline['generation'])
            need(len(wording.canonical(payload).encode()) <= 16384, 'resource_limit')
    return config, baseline, corpora


def reply_boundary(tag):
    def identity(value):
        need(type(value) is dict and value.get('model') == tag, 'identity_unverified')
    return SimpleNamespace(**dict(vars(parent), require_reply_identity=identity))


class Transport(compat.old.Transport):
    """Reuse PR109's single-request transport, numeric loopback and hard deadlines."""
    def __init__(self, config, baseline, case, arm, deadline):
        self.model = config['models'][arm]
        self.config = dict(baseline, model=self.model)
        self.limits, self.deadline = baseline['limits'], deadline
        self.allowed = {wording.canonical(dict(engine.EmailMetadata(case['input']).fields))}
        self.chat_attempts, self.requests = 0, []

    def request(self, method, path, value=None):
        return clone(compat.old.Transport.request, parent=reply_boundary(self.model['tag']))(self, method, path, value)

    def identity(self):
        version = self.request('GET', '/api/version').get('version')
        need(version == '0.40.6', 'identity_unverified')
        models = self.request('GET', '/api/tags').get('models')
        need(type(models) is list and len(models) <= self.limits['metadata_models'], 'identity_unverified')
        tag = self.model['tag']
        matches = [v for v in models if type(v) is dict and (v.get('name') == tag or v.get('model') == tag)]
        need(len(matches) == 1 and matches[0].get('digest') == self.model['digest'] and all(matches[0].get(k, tag) == tag for k in ('name','model')), 'identity_unverified')
        show = self.request('POST', '/api/show', {'model':tag, 'verbose':False})
        d, info, caps = show.get('details'), show.get('model_info'), show.get('capabilities')
        need(type(d) is dict and type(info) is dict and type(caps) is list, 'identity_unverified')
        need(d.get('format') == 'gguf' and d.get('family') == info.get('general.architecture') == self.model['family'] and d.get('quantization_level') == 'Q4_K_M', 'identity_unverified')
        size = d.get('parameter_size')
        need(type(size) is str and len(size) <= 32 and re.fullmatch(self.model['parameter_pattern'], size), 'identity_unverified')
        need('completion' in caps and 'thinking' in caps, 'protocol_error')
        return dict(tag=tag, digest=self.model['digest'], family=self.model['family'], parameter_size=size,
                    format='gguf', quantization='Q4_K_M', runtime_version=version, thinking='advertised')


def response_result(value, projection, limits, tag):
    # Only the selected artifact identity binding changes; protocol/parser bytecode
    # and finite structure annotation are unchanged. The original modules stay frozen.
    out = clone(compat.response_result, parent=reply_boundary(tag))(value, projection, limits)
    reason = 'none' if out['status'] == 'valid' else 'not_applicable'
    if out['status'] == 'invalid_structure' and out['subreason'] == 'prediction_structure':
        try:
            reason = diagnostic._constraint(value['message']['content'], projection)
            if reason not in diagnostic.REASONS[3:]: reason = 'unknown'
        except Exception:
            reason = 'unknown'
    return dict(out, structure_reason=reason)


def scored(rows, selected):
    return parent.score([dict(row, **{k:c[k] for k in ('group','variant')}, reference=c['gold'])
                         for row, c in zip(rows, selected, strict=True)])


def run(mode, arm, *, client_factory, execution):
    """One explicitly selected stage; injected clients in offline tests only."""
    started = time.monotonic()
    config, baseline, corpora = setup()
    need((mode, arm) in STAGES, 'input_rejected')
    selected = corpora[mode]
    deadline = started + config['budgets'][mode + '_seconds']
    rows = []
    for c in selected:
        obs = compat.empty_observation(); obs.pop('prediction')
        rows.append(dict(obs, id=c['id'], attempted=False, actual=None, structure_reason='not_obtained',
                         chat_response_seconds=None, validation_seconds=None))
    initial = final = before = after = stop = None
    tainted = False
    client = None

    def observe():
        nonlocal tainted
        try:
            identity = client.identity()
            need(initial is None or identity == initial, 'identity_unverified')
            return identity
        except BaseException:
            tainted = True
            raise

    try:
        client = client_factory(config, baseline, selected[0], arm, deadline)
        initial = observe()
        before = client.residency()
        for i, (case, row) in enumerate(zip(selected, rows, strict=True)):
            if i: client = client_factory(config, baseline, case, arm, deadline)
            observe()
            projection = engine.EmailMetadata(case['input'])
            payload = client.payload(projection)
            row['attempted'] = True
            begin = time.monotonic()
            try:
                response = client.request('POST', '/api/chat', payload)
                row['chat_response_seconds'] = round(max(0, time.monotonic() - begin), 6)
                validation_begin = time.monotonic()
                try:
                    observation = response_result(response, projection, baseline['limits'], config['models'][arm]['tag'])
                    row['actual'] = observation.pop('prediction')
                    row.update(observation)
                    tainted |= row['status'] == 'identity_unverified'
                    client.remaining()
                finally:
                    row['validation_seconds'] = round(max(0, time.monotonic() - validation_begin), 6)
                if row['status'] != 'valid' and (mode == 'smoke' or row['status'] not in ('invalid_json','invalid_structure','refused')):
                    stop = row['status']; break
            except (Exception, KeyboardInterrupt) as exc:
                code = exc.code if isinstance(exc, Error) else 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'transport_error'
                row.update(status=code, subreason='transport_boundary', actual=None, structure_reason='not_applicable')
                raise
            finally:
                if row['chat_response_seconds'] is None:
                    row['chat_response_seconds'] = round(max(0, time.monotonic() - begin), 6)
    except (Exception, KeyboardInterrupt) as exc:
        stop = exc.code if isinstance(exc, Error) else 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'transport_error'
        tainted |= stop == 'identity_unverified'
    finally:
        if client is not None:
            try:
                final = observe()
                if initial is None or final != initial: tainted = True
                after = client.residency()
                client.remaining()
            except (Exception, KeyboardInterrupt) as exc:
                code = exc.code if isinstance(exc, Error) else 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'transport_error'
                tainted |= code == 'identity_unverified'
                if stop is None: stop = code
        else:
            tainted = True
    elapsed = round(max(0, time.monotonic() - started), 6)
    if elapsed > config['budgets'][mode + '_seconds']: stop = 'resource_limit'
    verified = initial is not None and final == initial and not tainted
    complete = all(r['attempted'] for r in rows) and stop is None and verified
    return dict(experiment=EXPERIMENT, freeze_commit=FREEZE, config_lf_sha256=CONFIG_SHA,
        implementation_lf_sha256=sha256(read_bounded(Path(__file__), 65536).replace(b'\r\n', b'\n')).hexdigest(),
        execution=execution, mode=mode, arm=arm, run_status='complete' if complete else 'partial',
        stop_code=stop, identity_tainted=tainted, identity_verified_at_end=verified,
        prediction_attribution='observed_candidate' if verified else 'unattributed_diagnostic',
        observed_identity=final if verified else None, initial_residency=before, final_residency=after,
        cpu_offload_measurement=None, total_elapsed_seconds=elapsed,
        selected=len(selected), attempted=sum(r['attempted'] for r in rows),
        status_counts=dict(Counter(r['status'] for r in rows)),
        model_metrics=scored(rows, selected) if verified else None,
        by_group={g:scored([r for r,c in zip(rows,selected) if c['group']==g], [c for c in selected if c['group']==g]) for g in sorted({c['group'] for c in selected})} if verified else None,
        unobserved_predictions=sum(r['status'] != 'valid' for r in rows),
        metric_scope='frozen_scorer_all_selected; harmful_counts_observed_valid_only; rejected_content_unknown',
        cases=rows)


def encoded(report):
    return (wording.canonical(report) + '\n').encode('utf-8')


def validate_report(report):
    """Reject arbitrary publication/recovery data; recompute every metric."""
    config, _, corpora = setup()
    keys = {'experiment','freeze_commit','config_lf_sha256','implementation_lf_sha256','execution','mode','arm','run_status','stop_code','identity_tainted','identity_verified_at_end','prediction_attribution','observed_identity','initial_residency','final_residency','cpu_offload_measurement','total_elapsed_seconds','selected','attempted','status_counts','model_metrics','by_group','unobserved_predictions','metric_scope','cases'}
    need(type(report) is dict and set(report) == keys, 'input_rejected')
    need(report['experiment'] == EXPERIMENT and report['freeze_commit'] == FREEZE and report['config_lf_sha256'] == CONFIG_SHA, 'input_rejected')
    need(report['implementation_lf_sha256'] == sha256(read_bounded(Path(__file__), 65536).replace(b'\r\n', b'\n')).hexdigest(), 'input_rejected')
    mode, arm = report['mode'], report['arm']
    need((mode,arm) in STAGES, 'input_rejected')
    cases = corpora[mode]; rows = report['cases']
    need(type(rows) is list and len(rows) == len(cases) == report['selected'], 'input_rejected')
    row_keys = set(compat.empty_observation()) - {'prediction'} | {'id','attempted','actual','structure_reason','chat_response_seconds','validation_seconds'}
    reasons = {'not_obtained','none','reply_identity','transport_boundary','telemetry_type','telemetry_bounds','thinking_present','top_level_fields','done_not_true','message_shape','message_role','tool_calls','content_type','inline_thinking','content_limit','end_reason','truncated','refused','prediction_json','prediction_structure'}
    def finite_time(v): return v is None or type(v) in (int,float) and 0 <= v <= 86400
    for row, case in zip(rows, cases, strict=True):
        need(type(row) is dict and set(row) == row_keys and row['id'] == case['id'], 'input_rejected')
        need(type(row['attempted']) is bool and row['status'] in parent.CODES and row['subreason'] in reasons and row['structure_reason'] in diagnostic.REASONS, 'input_rejected')
        need(finite_time(row['chat_response_seconds']) and finite_time(row['validation_seconds']), 'input_rejected')
        if row['status'] == 'valid':
            need(row['attempted'] and parent.parse_prediction(wording.canonical(signature_wire(row['actual'])), engine.EmailMetadata(case['input'])).signature() == row['actual'], 'input_rejected')
        else: need(row['actual'] is None, 'input_rejected')
        for key, allowed in [('presence_top', compat.TOP), ('presence_message', compat.MESSAGE)]:
            need(type(row[key]) is dict and set(row[key]) == set(allowed) and all(v is None or type(v) is bool for v in row[key].values()), 'input_rejected')
        need(set(row['telemetry']) == set(compat.METRICS) == set(row['telemetry_validation']), 'input_rejected')
        need(all(v is None or type(v) is int and 0 <= v <= 2**63-1 for v in row['telemetry'].values()), 'input_rejected')
        need(all(v in ('not_obtained','validated','absent','unavailable','invalid_type','out_of_bounds') for v in row['telemetry_validation'].values()), 'input_rejected')
        need(all(row[k] is None or type(row[k]) is int and 0 <= row[k] <= 65536 for k in ('unknown_top_level_count','unknown_message_field_count')), 'input_rejected')
    execution = report['execution']
    need(type(execution) is dict and set(execution) == {'commit','tree','kind'} and execution['kind'] in ('offline_mock','reviewed_manual'), 'input_rejected')
    need(all(type(execution[k]) is str and re.fullmatch(SHA, execution[k]) for k in ('commit','tree')), 'input_rejected')
    for key in ('initial_residency','final_residency'):
        value = report[key]
        need(value is None or type(value) is dict and set(value) == {'size','size_vram','context_length'} and all(v is None or type(v) is int and 0 <= v <= 2**63-1 for v in value.values()), 'input_rejected')
    identity = report['observed_identity']
    if identity is not None:
        need(set(identity) == {'tag','digest','family','parameter_size','format','quantization','runtime_version','thinking'}, 'input_rejected')
        model = config['models'][arm]
        need(all(identity[k] == model[k] for k in ('tag','digest','family')) and type(identity['parameter_size']) is str and re.fullmatch(model['parameter_pattern'], identity['parameter_size']), 'input_rejected')
        need(identity['format'] == 'gguf' and identity['quantization'] == 'Q4_K_M' and identity['runtime_version'] == '0.40.6' and identity['thinking'] == 'advertised', 'input_rejected')
    verified = report['identity_verified_at_end']
    need(type(verified) is bool and type(report['identity_tainted']) is bool and (not verified or not report['identity_tainted'] and identity is not None), 'input_rejected')
    need((identity is not None) == verified and report['cpu_offload_measurement'] is None, 'input_rejected')
    need(report['prediction_attribution'] == ('observed_candidate' if verified else 'unattributed_diagnostic'), 'input_rejected')
    need(report['stop_code'] is None or report['stop_code'] in parent.CODES, 'input_rejected')
    complete = all(r['attempted'] for r in rows) and report['stop_code'] is None and verified
    need(report['run_status'] == ('complete' if complete else 'partial') and finite_time(report['total_elapsed_seconds']), 'input_rejected')
    need(report['attempted'] == sum(r['attempted'] for r in rows) and report['status_counts'] == dict(Counter(r['status'] for r in rows)), 'input_rejected')
    need(report['unobserved_predictions'] == sum(r['status'] != 'valid' for r in rows), 'input_rejected')
    need(report['metric_scope'] == 'frozen_scorer_all_selected; harmful_counts_observed_valid_only; rejected_content_unknown', 'input_rejected')
    need(report['model_metrics'] == (scored(rows,cases) if verified else None), 'input_rejected')
    groups = {g:scored([r for r,c in zip(rows,cases) if c['group']==g], [c for c in cases if c['group']==g]) for g in sorted({c['group'] for c in cases})} if verified else None
    need(report['by_group'] == groups, 'input_rejected')
    return report


def save(report):
    validate_report(report)
    return clone(prior.save, ROOT=ROOT, LOCAL=LOCAL, encoded=encoded)(report)


def read_report(run_id, expected_sha):
    need(type(run_id) is str and re.fullmatch('[0-9a-f]{32}', run_id), 'input_rejected')
    need(type(expected_sha) is str and re.fullmatch('[0-9a-f]{64}', expected_sha), 'input_rejected')
    raw = read_bounded(ROOT / LOCAL / run_id / 'report.json', REPORT_BYTES)
    need(sha256(raw).hexdigest() == expected_sha, 'input_rejected')
    report = parent.strict_json(raw.decode('utf-8'))
    need(encoded(report) == raw, 'input_rejected')
    return validate_report(report)


def prerequisites(mode, arm, reports, execution):
    """Explicit hash-verified prior reports, no scanning/selecting a best run."""
    need((mode,arm) in STAGES, 'input_rejected')
    index = STAGES.index((mode,arm))
    need(len(reports) == index, 'input_rejected')
    for report, (m,a) in zip(reports,STAGES[:index],strict=True):
        validate_report(report)
        need((report['mode'],report['arm']) == (m,a) and report['execution'] == execution, 'input_rejected')
        need(report['identity_verified_at_end'] and report['run_status'] == 'complete', 'input_rejected')
        if m == 'smoke': need(all(r['status'] == 'valid' for r in report['cases']), 'input_rejected')


def execution_gate(execution):
    # No source constant is updated to pin its own containing commit. A later,
    # reviewed interactive launcher supplies the approved public commit/tree.
    need(type(execution) is dict and set(execution) == {'commit','tree','kind'}, 'input_rejected')
    need(execution['kind'] == 'reviewed_manual' and sys.platform == 'win32' and sys.version_info[:3] == (3,12,10), 'input_rejected')
    def git(*args):
        return subprocess.run(['git',*args], cwd=ROOT, check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=10).stdout.decode('ascii').strip()
    need(all(type(execution[k]) is str and re.fullmatch(SHA,execution[k]) for k in ('commit','tree')), 'input_rejected')
    need(git('rev-parse','HEAD') == execution['commit'] and git('rev-parse','HEAD^{tree}') == execution['tree'], 'input_rejected')
    need(git('status','--porcelain','--untracked-files=all') == '', 'input_rejected')
    need(git('merge-base','--is-ancestor',FREEZE,'HEAD') == '', 'input_rejected')


def claim_stage(mode, arm):
    """Consume a stage before any metadata/model request; never overwrite/retry."""
    target = ROOT / LOCAL
    for p in (ROOT / '.local',target,target / 'claims'):
        wording.parents(p); p.mkdir(mode=0o700,exist_ok=True); wording.regular(p,True)
    with (target / 'claims' / f'{mode}-{arm}').open('xb') as f:
        f.write(b'claimed; no retry or resume\n'); f.flush(); prior.os.fsync(f.fileno())


def collect(mode, arm, *, previous=(), execution=None, client_factory=None):
    """One manual stage. Default real transport is gated; tests inject Mock only."""
    report = path = expected = None
    try:
        config, _, _ = setup()
        if client_factory is None:
            # This PR freezes preparation only. A separate reviewed launch freeze
            # must enable real execution; caller-supplied SHA strings cannot do so.
            need(config['execution_freeze'] is not None, 'input_rejected')
            execution_gate(execution)
            client_factory = Transport
        else:
            need(type(execution) is dict and execution.get('kind') == 'offline_mock', 'input_rejected')
        reports = [read_report(run_id,sha) for run_id,sha in previous]
        prerequisites(mode,arm,reports,execution)
        claim_stage(mode,arm)
        report = run(mode,arm,client_factory=client_factory,execution=execution)
        expected = sha256(encoded(report)).hexdigest()
        path = save(report)
        need(read_report(Path(path).parent.name,expected) == report, 'input_rejected')
        return dict(error_code=None, report=report, report_path=path, report_sha256=expected,
                    report_read_verified=True, workflow_exit_code=0 if report['run_status']=='complete' else 2)
    except (Exception,KeyboardInterrupt):
        # Existing in-memory partial evidence survives publication failure. A claim
        # remains consumed; collect never calls run/save a second time.
        return dict(error_code='stage_or_publication_failed', report=report, report_path=path,
                    report_sha256=expected, report_read_verified=False, workflow_exit_code=1)


def compare(a, b):
    """Exact preregistered joint screen, never a structure-validity score."""
    unknown = dict(decision='not_evaluable', checks=None, paired=None, reason='incomplete_or_unknown_evidence')
    try:
        config, _, corpus = setup()
        for arm,r in (('A',a),('B',b)):
            validate_report(r)
            need(r['mode']=='full' and r['arm']==arm and r['run_status']=='complete'
                 and r['identity_verified_at_end'] and r['model_metrics'] is not None
                 and r['total_elapsed_seconds'] <= 600, 'input_rejected')
            need(all(row['chat_response_seconds'] is not None and row['chat_response_seconds'] <= 60 for row in r['cases']), 'input_rejected')
        need(a['execution']==b['execution'], 'input_rejected')
        ma,mb = a['model_metrics'],b['model_metrics']
        keys = ['ambiguous_abstain','ambiguous_overreach','missed_outstanding_cases','missed_date_cases'] + config['harm_counters']
        need(all(type(m[k]) is int for m in (ma,mb) for k in keys), 'input_rejected')
        need(all((m['selected'],m['clear'],m['ambiguous'],m['outstanding_reference_cases'],m['date_reference_cases']) == (24,16,8,8,8) for m in (ma,mb)), 'input_rejected')
        need(type(mb['clear_outcomes']['full']) is int, 'input_rejected')
        def full(row,case):
            ref=case['gold']; got=row['actual']
            return row['status']=='valid' and got['state']==ref['state'] and wording.atoms(got['steps'])==wording.atoms(ref['steps']) and wording.atoms(got['dates'])==wording.atoms(ref['dates'])
        won,lost,groups = [],[],{}
        for ra,rb,case in zip(a['cases'],b['cases'],corpus['full'],strict=True):
            if case['variant']=='ambiguous': continue
            x,y=full(ra,case),full(rb,case)
            if y and not x: won.append(case['id'])
            if x and not y: lost.append(case['id'])
            g=groups.setdefault(case['group'],dict(A_full=0,B_full=0,W=0,L=0))
            g['A_full']+=x; g['B_full']+=y; g['W']+=y and not x; g['L']+=x and not y
        t=config['thresholds']
        checks=dict(clear_full=mb['clear_outcomes']['full']>=t['clear_full_min'], net_full=len(won)-len(lost)>=t['net_full_min'],
            ambiguous_abstain=mb['ambiguous_abstain']>=t['ambiguous_abstain_min'] and mb['ambiguous_abstain']>=ma['ambiguous_abstain'],
            ambiguous_overreach=mb['ambiguous_overreach']<=t['ambiguous_overreach_max'] and mb['ambiguous_overreach']<=ma['ambiguous_overreach'],
            missed_outstanding=mb['missed_outstanding_cases']<=t['missed_outstanding_max'] and mb['missed_outstanding_cases']<=ma['missed_outstanding_cases'],
            missed_date=mb['missed_date_cases']<=t['missed_date_max'] and mb['missed_date_cases']<=ma['missed_date_cases'],
            **{k:mb[k]==0 for k in config['harm_counters']})
        return dict(decision='provisional_signal' if all(checks.values()) else 'stop_candidate', checks=checks,
                    evidence_kind=a['execution']['kind'],
                    paired=dict(W=len(won),L=len(lost),B_only_full=won,A_only_full=lost,by_group=groups), reason=None)
    except (Exception,KeyboardInterrupt):
        return unknown


def main(argv=None):
    parser=argparse.ArgumentParser(description='Offline artifact-control preparation; real launch not yet frozen')
    sub=parser.add_subparsers(dest='mode',required=True)
    sub.add_parser('check')
    sub.add_parser('smoke');sub.add_parser('full')
    recover=sub.add_parser('recover');recover.add_argument('run_id');recover.add_argument('expected_sha256')
    args=parser.parse_args(argv)
    try:
        if args.mode=='check':
            config,_,corpora=setup()
            result=dict(operation='check',config_sha256=CONFIG_SHA,freeze_commit=FREEZE,
                        counts={k:len(v) for k,v in corpora.items()},order=config['order'],real_execution_authorized=False)
        elif args.mode=='recover':
            result=dict(operation='recover',report=read_report(args.run_id,args.expected_sha256))
        else:
            result=dict(error_code='execution_not_frozen_or_authorized')
    except (Exception,KeyboardInterrupt):
        result=dict(error_code='offline_check_or_recovery_failed')
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    return 1 if 'error_code' in result else 0


if __name__=='__main__':
    raise SystemExit(main())
