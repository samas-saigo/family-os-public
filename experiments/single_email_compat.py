"""Frozen v2 single-case runtime diagnostic: Ollama0.40.6 cache metric compatibility."""
from hashlib import sha256
import os
from pathlib import Path
import re
import time
from uuid import uuid4

from experiments import single_email_diagnostic as old

parent, wording, engine = old.parent, old.wording, old.engine
ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path('experiments/configs/single-email-runtime-diagnostic-v2.json')
CONFIG_SHA = '461b7e83eb51798aa261446c440c20a0908963b40fd4902bd14cd61ac1332aa7'
FREEZE = 'c6f8c7c65611b1a8e7d78578f92dc16a55734cad'
LOCAL = Path('.local/single-email-runtime-diagnostic-v2')
BASE_SHA = 'b5451e7b0c971602d234b0c137a0eb8f9e96b90fb9a666bdb643707c26f95ca3'
METRICS = parent.TELEMETRY + ('prompt_eval_cached_count',)
TOP = ('model', 'created_at', 'done', 'done_reason', 'message', 'context')
MESSAGE = ('role', 'content', 'thinking', 'tool_calls')


def read_pin(relative, expected):
    parent.need(relative in (CONFIG, Path('experiments/single_email_diagnostic.py')), 'input_rejected')
    path = ROOT / relative
    wording.parents(path)
    before = wording.regular(path)
    parent.need(before.st_size <= 65536, 'resource_limit')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        handle = os.fstat(stream.fileno())
        parent.need(wording.cross_api_identity(handle) == wording.cross_api_identity(before), 'input_rejected')
        raw = stream.read(65537)
        parent.need(wording.identity(handle) == wording.identity(os.fstat(stream.fileno())), 'input_rejected')
    parent.need(len(raw) <= 65536 and wording.identity(before) == wording.identity(wording.regular(path)), 'input_rejected')
    raw = raw.replace(b'\r\n', b'\n')
    parent.need(sha256(raw).hexdigest() == expected, 'input_rejected')
    return raw


def setup():
    parent.need(ROOT == old.ROOT and Path(old.__file__).absolute() == ROOT / 'experiments/single_email_diagnostic.py', 'input_rejected')
    read_pin(Path('experiments/single_email_diagnostic.py'), BASE_SHA)
    config = parent.strict_json(read_pin(CONFIG, CONFIG_SHA).decode('utf-8'))
    prior, wire_config, projection = old.setup()
    parent.need(all(config[k] == prior[k] for k in ('model', 'prompt', 'output_schema', 'generation', 'limits', 'input')), 'input_rejected')
    return config, wire_config, projection


class Transport(old.Transport):
    # Inherit unchanged numeric-loopback request/deadline/identity-taint boundary;
    # explicitly construct a separately pinned v2 instance, no monkeypatching.
    def __init__(self, config, deadline):
        expected, wire_config, projection = setup()
        parent.need(config == expected, 'input_rejected')
        self.config, self.limits, self.deadline = wire_config, config['limits'], deadline
        self.allowed = {wording.canonical(dict(projection.fields))}
        self.chat_attempts, self.requests = 0, []


def empty_observation():
    return dict(status='not_attempted', subreason='not_obtained', prediction=None,
                telemetry={k: None for k in METRICS},
                telemetry_validation={k: 'not_obtained' for k in METRICS},
                presence_top={k: None for k in TOP}, presence_message={k: None for k in MESSAGE},
                unknown_top_level_count=None, unknown_message_field_count=None)


def response_result(value, projection, limits):
    """Dedicated v2 validator. Never remove an extension and call the v1 validator."""
    out = empty_observation()

    def reject(status, reason):
        out.update(status=status, subreason=reason)
        return out

    try:
        parent.require_reply_identity(value)
    except parent.ExperimentError:
        return reject('identity_unverified', 'reply_identity')
    out['presence_top'] = {k: k in value for k in TOP}
    allowed = {'model', 'created_at', 'done', 'done_reason', 'message'} | set(METRICS)
    out['unknown_top_level_count'] = len(set(value) - allowed)
    message = value.get('message')
    if type(message) is dict:
        out['presence_message'] = {k: k in message for k in MESSAGE}
        out['unknown_message_field_count'] = len(set(message) - set(MESSAGE))

    # Telemetry is validated independently, before accepting or rejecting prediction.
    # A typed server claim is not proof of a true server measurement or model use.
    metric_error = None
    for key in METRICS:
        v = value.get(key)
        state = 'validated'
        if key not in value:
            state = 'absent'
        elif v is None and key != 'prompt_eval_cached_count':
            state = 'unavailable'  # Existing optional-null contract unchanged.
        elif type(v) is not int:
            state = 'invalid_type'
        elif not 0 <= v <= 2**63 - 1:
            state = 'out_of_bounds'
        elif (key == 'eval_count' and v > 512 or key == 'prompt_eval_count' and v > 4096 or key == 'thinking_count' and v != 0):
            state = 'out_of_bounds'
        out['telemetry_validation'][key] = state
        if state == 'validated':
            out['telemetry'][key] = v
        if state in ('invalid_type', 'out_of_bounds') and metric_error is None:
            metric_error = ('protocol_error', 'telemetry_type') if state == 'invalid_type' else ('thinking_leakage', 'thinking_present') if key == 'thinking_count' and type(v) is int and v > 0 else ('resource_limit', 'telemetry_bounds')
    if out['unknown_top_level_count']:
        return reject('protocol_error', 'top_level_fields')
    if value.get('done') is not True:
        return reject('protocol_error', 'done_not_true')
    if type(message) is not dict or out['unknown_message_field_count']:
        return reject('protocol_error', 'message_shape')
    if message.get('role') != 'assistant':
        return reject('protocol_error', 'message_role')
    if 'tool_calls' in message and (type(message['tool_calls']) is not list or message['tool_calls']):
        return reject('protocol_error', 'tool_calls')
    if message.get('thinking') not in (None, ''):
        return reject('thinking_leakage', 'thinking_present')
    content = message.get('content')
    if type(content) is not str:
        return reject('protocol_error', 'content_type')
    if re.search(r'<\s*/?\s*(?:think|thinking|analysis)\b', content, re.I):
        return reject('thinking_leakage', 'inline_thinking')
    if metric_error:
        return reject(*metric_error)
    try:
        parent.need(len(content.encode('utf-8')) <= limits['content_bytes'], 'resource_limit')
    except UnicodeError:
        return reject('invalid_structure', 'prediction_structure')
    except parent.ExperimentError:
        return reject('resource_limit', 'content_limit')
    try:
        body = parent.strict_json(content)
    except parent.ExperimentError:
        body = None
    if type(body) is dict and any(body.get(k) for k in ('thinking', 'reasoning', 'analysis')):
        return reject('thinking_leakage', 'thinking_present')
    if value.get('done_reason') not in ('stop', 'length'):
        return reject('protocol_error', 'end_reason')
    if value['done_reason'] == 'length':
        return reject('truncated', 'truncated')
    if not content.strip():
        return reject('refused', 'refused')
    try:
        prediction = parent.parse_prediction(content, projection)
    except parent.ExperimentError as exc:
        return reject(exc.code, 'prediction_json' if exc.code == 'invalid_json' else 'prediction_structure')
    out.update(status='valid', subreason='none', prediction=prediction.signature())
    return out


def run():
    started = time.monotonic()
    config, _, projection = setup()
    client = Transport(config, started + config['limits']['run_seconds'])
    initial, final, resident, stopped = None, None, None, None
    tainted = False
    result = dict(empty_observation(), id='WC01-1', attempted=False,
                  chat_response_seconds=None, validation_seconds=None)

    def observe():
        nonlocal tainted
        try:
            value = client.identity()
            parent.need(value['runtime_version'] == config['runtime_version'] and (initial is None or value == initial), 'identity_unverified')
            return value
        except parent.ExperimentError:
            tainted = True
            raise
    try:
        initial = observe()
        resident = client.residency()
        observe()
        payload = client.payload(projection)
        result['attempted'] = True
        chat_start = time.monotonic()
        response = client.request('POST', '/api/chat', payload)
        result['chat_response_seconds'] = round(max(0, time.monotonic() - chat_start), 6)
        validation_start = time.monotonic()
        try:
            result.update(response_result(response, projection, config['limits']))
            tainted |= result['status'] == 'identity_unverified'
            client.remaining()
            if result['status'] != 'valid': stopped = result['status']
        finally:
            result['validation_seconds'] = round(max(0, time.monotonic() - validation_start), 6)
    except parent.ExperimentError as exc:
        stopped = exc.code
        tainted |= exc.code == 'identity_unverified'
        if result['attempted']:
            result.update(status=exc.code, subreason='reply_identity' if exc.code == 'identity_unverified' else 'transport_boundary')
    except KeyboardInterrupt:
        stopped = 'interrupted'
        if result['attempted']: result.update(status='interrupted', subreason='transport_boundary')
    finally:
        try:
            final = observe()
            if initial is None or final != initial: tainted = True
        except parent.ExperimentError as exc:
            final = None
            if stopped is None: stopped = exc.code
        except KeyboardInterrupt:
            tainted = True
            if stopped is None: stopped = 'interrupted'
    verified = initial is not None and final == initial and not tainted
    return dict(diagnostic=config['diagnostic'], freeze_commit=FREEZE, config_lf_sha256=CONFIG_SHA,
                parent_v1_lf_sha256=BASE_SHA, parent_config_lf_sha256=parent.CONFIG_SHA,
                input_fixture_lf_sha256=wording.FIXTURE_SHA256,
                prompt_sha256=sha256(config['prompt'].encode()).hexdigest(),
                schema_sha256=sha256(wording.canonical(config['output_schema']).encode()).hexdigest(),
                configured_candidate=config['model'], generation=config['generation'], limits=config['limits'],
                run_status='complete' if verified and stopped is None and result['status'] == 'valid' else 'partial',
                stop_code=stopped, root_cause='unknown', selected=1, attempted=int(result['attempted']),
                identity_verified_at_end=verified, observed_identity=final if verified else None,
                prediction_attribution='observed_candidate' if verified else 'unattributed_diagnostic',
                telemetry_scope='validated_shape_and_budget_only; server_claim_not_ground_truth',
                initial_residency=resident, total_elapsed_seconds=round(max(0, time.monotonic() - started), 6),
                requests=client.requests, result=result,
                restrictions=dict(authority='none', sender_claim_only=True, human_review_required=True,
                                  independent_safety_and_authorization_required=True),
                notice='V2 RUNTIME DIAGNOSTIC ONLY; NO SCORE/COMPARISON; OLD RESULTS UNCHANGED; HISTORICAL FAILURE CAUSE UNKNOWN')


def save(report):
    payload = wording.canonical(report) + '\n'
    target = ROOT / LOCAL
    for p in (ROOT / '.local', target):
        wording.parents(p); p.mkdir(mode=0o700, exist_ok=True); wording.regular(p, True)
    directory = target / uuid4().hex
    directory.mkdir(mode=0o700)
    temporary, path = directory / 'report.json.tmp', directory / 'report.json'
    created = False
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            created = True; stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if created:
            try: temporary.unlink(missing_ok=True)
            except OSError: pass
        try: directory.rmdir()
        except OSError: pass
        raise
    return path.relative_to(ROOT).as_posix()
