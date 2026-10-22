"""Manual, fixed-wording-only model comparison. No production or legacy transport."""
import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import http.client
import io
import json
import os
from pathlib import Path
import re
import socket
import time
from uuid import uuid4

from experiments import email_wording_challenge as wording
from family_os import _synthetic_email_evidence as engine

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path('experiments/configs/synthetic-email-model-evidence-v1.json')
CONFIG_SHA = 'c4e774ce7a8a81b2bb80f77588126cd515fe3dd0496eecb09836b3330729d17f'
SCORER_SHA = '7be67835c559a4d9e0fd6b92af03fe01357504adc72cb35fcd57afbc0d08afbd'
FREEZE = 'ffe329ce55bd7a148d0b849503299cdd818e138a'
LOCAL = Path('.local/email-model-evidence')
CODES = ('valid', 'input_rejected', 'invalid_json', 'invalid_structure', 'refused',
         'truncated', 'thinking_leakage', 'timeout', 'protocol_error', 'transport_error',
         'identity_unverified', 'resource_limit', 'interrupted', 'not_attempted')
TELEMETRY = ('total_duration', 'load_duration', 'prompt_eval_count', 'prompt_eval_duration',
             'eval_count', 'eval_duration', 'thinking_count')


class ExperimentError(ValueError):
    def __init__(self, code='protocol_error'):
        self.code = code if code in CODES else 'protocol_error'
        super().__init__(self.code)


def need(ok, code='protocol_error'):
    if not ok:
        raise ExperimentError(code)


def read_pin(relative, expected):
    need(relative in (Path('experiments/configs/synthetic-email-model-evidence-v1.json'), Path('experiments/email_wording_challenge.py')))
    path = ROOT / relative
    wording.parents(path)
    before = wording.regular(path)
    need(before.st_size <= 65536)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        handle = os.fstat(stream.fileno())
        need(wording.cross_api_identity(handle) == wording.cross_api_identity(before))
        raw = stream.read(65537)
        need(wording.identity(handle) == wording.identity(os.fstat(stream.fileno())))
    need(wording.identity(before) == wording.identity(wording.regular(path)) and len(raw) <= 65536)
    raw = raw.replace(b'\r\n', b'\n')
    need(sha256(raw).hexdigest() == expected)
    return raw


def strict_json(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'invalid_json')
            out[k] = v
        return out
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: need(False, 'invalid_json'))
    except ExperimentError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ExperimentError('invalid_json') from None


def setup():
    need(CONFIG == Path('experiments/configs/synthetic-email-model-evidence-v1.json'))
    need(wording.ROOT == ROOT and Path(wording.__file__).absolute() == ROOT / 'experiments/email_wording_challenge.py')
    read_pin(Path('experiments/email_wording_challenge.py'), SCORER_SHA)
    config = strict_json(read_pin(CONFIG, CONFIG_SHA).decode('utf-8'))
    cases = wording.load()  # Only its fixed wording fixture + pinned interpreter; never PR104.
    for c in cases:
        engine.EmailMetadata(c['input'])
    return config, cases


@dataclass(frozen=True)
class ModelEvidence:
    """No rule ID, rule Evidence provenance or model-supplied authority fields."""
    state: engine.State
    steps: tuple
    dates: tuple

    def signature(self):
        return dict(state=self.state.value, steps=[[s.action.value, s.status.value] for s in self.steps],
                    dates=[[d.role.value, d.value, d.action.value if d.action else None] for d in self.dates])


def parse_prediction(raw, projection):
    try:
        need(type(raw) is str and len(raw.encode('utf-8')) <= 8192, 'invalid_structure')
        # Never strip a preamble, thinking, markdown or salvage a JSON substring.
        v = strict_json(raw)
        need(type(v) is dict and set(v) == {'state', 'steps', 'dates'}, 'invalid_structure')
        need(type(v['state']) is str and type(v['steps']) is list and type(v['dates']) is list, 'invalid_structure')
        need(len(v['steps']) <= 2 and len(v['dates']) <= 1, 'invalid_structure')
        for s in v['steps']:
            need(type(s) is dict and set(s) == {'action', 'status'} and all(type(x) is str for x in s.values()), 'invalid_structure')
        for d in v['dates']:
            need(type(d) is dict and set(d) == {'role', 'value', 'action'} and type(d['role']) is str and type(d['value']) is str and (d['action'] is None or type(d['action']) is str), 'invalid_structure')
        state = engine.State(v['state'])
        steps = tuple(engine.StepEvidence(engine.Action(s['action']), engine.Status(s['status'])) for s in v['steps'])
        dates = tuple(engine.DateEvidence(engine.DateRole(d['role']), d['value'], engine.Action(d['action']) if d['action'] is not None else None) for d in v['dates'])
        need(len({s.action for s in steps}) == len(steps), 'invalid_structure')
        if state is engine.State.ABSTAIN:
            need(not steps and not dates, 'invalid_structure')
        else:
            need(projection.fields['notice_kind'] == ('promotional' if state is engine.State.PROMOTION else 'service'), 'invalid_structure')
            if state is engine.State.OUTSTANDING:
                need(any(s.status is engine.Status.OUTSTANDING for s in steps), 'invalid_structure')
            elif state is engine.State.COMPLETION:
                need(bool(steps) and all(s.status is engine.Status.COMPLETED for s in steps), 'invalid_structure')
            elif state is engine.State.INFORMATION:
                need(all(s.status in (engine.Status.FAILED, engine.Status.CANCELLED) for s in steps), 'invalid_structure')
            else:
                need(not steps, 'invalid_structure')
            for d in dates:
                if d.role is engine.DateRole.DUE:
                    need(state is engine.State.OUTSTANDING and any(s.action is d.action and s.status is engine.Status.OUTSTANDING for s in steps), 'invalid_structure')
                elif d.role is engine.DateRole.COMPLETION:
                    need(state is engine.State.COMPLETION and any(s.action is d.action and s.status is engine.Status.COMPLETED for s in steps), 'invalid_structure')
                elif d.role is engine.DateRole.OFFER:
                    need(state is engine.State.PROMOTION, 'invalid_structure')
                else:
                    need(state is engine.State.INFORMATION, 'invalid_structure')
        return ModelEvidence(state, steps, dates)
    except ExperimentError:
        raise
    except (ValueError, TypeError, KeyError):
        raise ExperimentError('invalid_structure') from None


class DeadlineSocket:
    def __init__(self, sock, end, maximum=60, header_limit=8192):
        self.sock, self.end, self.maximum = sock, end, maximum
        self.readers, self.closed = 0, False
        self.header_limit, self.header_bytes, self.headers_done = header_limit, 0, False

    def settimeout(self, seconds):
        remaining = self.end - time.monotonic()
        need(remaining > 0, 'timeout')
        # HTTPResponse may close its reader immediately after the final body byte.
        # Deadline checks still run at EOF; no socket operation remains then.
        if not (self.closed and not self.readers):
            self.sock.settimeout(min(seconds, remaining, self.maximum))

    def sendall(self, data):
        self.settimeout(self.end - time.monotonic())
        self.sock.sendall(data)

    def makefile(self, mode):
        need(mode == 'rb')
        owner = self
        owner.readers += 1
        class Reader(io.RawIOBase):
            def readable(self):return True
            def readinto(self, buffer):
                owner.settimeout(owner.end - time.monotonic())
                return owner.sock.recv_into(buffer)
            def close(self):
                if not self.closed:
                    owner.readers -= 1
                    if owner.closed and not owner.readers:owner.sock.close()
                super().close()
        class HeaderReader(io.BufferedReader):
            def readline(self, size=-1):
                if owner.headers_done:return super().readline(size)
                remaining = owner.header_limit - owner.header_bytes
                need(remaining >= 0, 'resource_limit')
                line = super().readline(remaining + 1 if size < 0 else min(size, remaining + 1))
                owner.header_bytes += len(line)
                need(owner.header_bytes <= owner.header_limit, 'resource_limit')
                return line
        return HeaderReader(Reader())

    def close(self):
        self.closed = True
        if not self.readers:self.sock.close()


class Transport:
    """Direct numeric HTTP only. No urllib/environment proxies, redirects or retries."""
    def __init__(self, config, cases, deadline):
        need(config == strict_json(read_pin(CONFIG, CONFIG_SHA).decode('utf-8')), 'input_rejected')
        need(cases == wording.load(), 'input_rejected')
        self.config, self.deadline = config, deadline
        self.allowed = {wording.canonical(dict(engine.EmailMetadata(c['input']).fields)) for c in cases}

    def remaining(self):
        left = self.deadline - time.monotonic()
        need(left > 0, 'resource_limit')
        return left

    def payload(self, projection):
        need(type(projection) is engine.EmailMetadata, 'input_rejected')
        text = wording.canonical(dict(projection.fields))
        need(text in self.allowed, 'input_rejected')
        return dict(model=self.config['model']['tag'], messages=[{'role':'system', 'content':self.config['prompt']},
                    {'role':'user', 'content':text}], format=self.config['output_schema'], **self.config['generation'])

    def request(self, method, path, value=None):
        need((method, path) in {('GET','/api/version'), ('GET','/api/tags'), ('GET','/api/ps'),
                               ('POST','/api/show'), ('POST','/api/chat')})
        if method == 'GET':
            need(value is None)
        elif path == '/api/show':
            need(wording.canonical(value) == wording.canonical({'model':self.config['model']['tag'], 'verbose':False}))
        else:
            need(type(value) is dict and type(value.get('messages')) is list and len(value['messages']) == 2)
            try:
                projection = engine.EmailMetadata(strict_json(value['messages'][1]['content']))
                need(wording.canonical(value) == wording.canonical(self.payload(projection)), 'input_rejected')
            except (KeyError, TypeError, engine.EmailEvidenceError):
                raise ExperimentError('input_rejected') from None
        raw = None if value is None else wording.canonical(value).encode('utf-8')
        need(raw is None or len(raw) <= self.config['limits']['request_bytes'], 'resource_limit')
        end = min(self.deadline, time.monotonic() + self.config['limits']['request_seconds'])
        connection = http.client.HTTPConnection('127.0.0.1', 11434,
            timeout=min(self.config['limits']['connect_seconds'], self.remaining()))
        response = None
        try:
            connection.connect()
            connection.sock = DeadlineSocket(connection.sock, end, self.config['limits']['request_seconds'], self.config['limits']['response_header_bytes'])
            wire = connection.sock
            def bound():
                left = min(end - time.monotonic(), self.remaining())
                need(left > 0, 'timeout')
                wire.settimeout(left)
            bound()
            connection.request(method, path, body=raw, headers={'Accept':'application/json', 'Content-Type':'application/json', 'Connection':'close'})
            bound()
            response = connection.getresponse()
            wire.headers_done = True
            need(response.status == 200)  # No redirect, fallback, download or alternate request.
            headers = response.getheaders()
            need(sum(len(k)+len(v) for k,v in headers) <= self.config['limits']['response_header_bytes'], 'resource_limit')
            need(response.getheader('Content-Type', '').lower() in ('application/json', 'application/json; charset=utf-8'))
            need(response.getheader('Content-Encoding') in (None, 'identity'))
            length = response.getheader('Content-Length')
            if length is not None:
                need(bool(re.fullmatch('[0-9]{1,6}', length)) and int(length) <= self.config['limits']['response_bytes'], 'resource_limit')
            chunks, size = [], 0
            while True:
                bound()
                data = response.read1(min(4096, self.config['limits']['response_bytes'] + 1 - size))
                if not data:
                    break
                size += len(data)
                need(size <= self.config['limits']['response_bytes'], 'resource_limit')
                chunks.append(data)
            bound()
            if length is not None:
                need(size == int(length))
            try:
                result = strict_json(b''.join(chunks).decode('utf-8'))
            except (ExperimentError, UnicodeError):
                # A received chat envelope without parseable identity cannot be
                # attributed; metadata protocol failures keep their old meaning.
                raise ExperimentError('identity_unverified' if path == '/api/chat' else 'protocol_error') from None
            if path == '/api/chat':require_reply_identity(result)
            need(type(result) is dict and 'error' not in result)
            return result
        except ExperimentError:
            raise
        except (TimeoutError, socket.timeout):
            raise ExperimentError('timeout') from None
        except (OSError, http.client.HTTPException, ValueError):
            raise ExperimentError('transport_error') from None
        finally:
            if response is not None:response.close()
            connection.close()

    def identity(self):
        version = self.request('GET', '/api/version').get('version')
        need(type(version) is str and bool(re.fullmatch(r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}', version)))
        models = self.request('GET', '/api/tags').get('models')
        need(type(models) is list and len(models) <= self.config['limits']['metadata_models'])
        tag = self.config['model']['tag']
        candidates = [m for m in models if type(m) is dict and (m.get('name') == tag or m.get('model') == tag)]
        need(len(candidates) == 1, 'identity_unverified')
        found = candidates[0]
        need(found.get('digest') == self.config['model']['digest'] and all(found.get(k, tag) == tag for k in ('name','model')), 'identity_unverified')
        show = self.request('POST', '/api/show', {'model':tag, 'verbose':False})
        details, info, caps = show.get('details'), show.get('model_info'), show.get('capabilities')
        need(type(details) is dict and type(info) is dict and type(caps) is list, 'identity_unverified')
        need(all(details.get(k) == self.config['model'][k] for k in ('family','parameter_size','quantization_level')) and info.get('general.architecture') == 'qwen35', 'identity_unverified')
        need('completion' in caps and 'thinking' in caps, 'protocol_error')
        return dict(**self.config['model'], runtime_version=version, advertised_capabilities=['completion','thinking'])

    def residency(self):
        models = self.request('GET', '/api/ps').get('models')
        need(type(models) is list and len(models) <= self.config['limits']['metadata_models'])
        found = [m for m in models if type(m) is dict and (m.get('name') == self.config['model']['tag'] or m.get('model') == self.config['model']['tag'])]
        need(len(found) <= 1, 'identity_unverified')
        if not found:
            return None
        item = found[0]
        need(item.get('digest') == self.config['model']['digest'], 'identity_unverified')
        out = {}
        for k in ('size','size_vram','context_length'):
            v = item.get(k)
            need(v is None or type(v) is int and 0 <= v <= 2**63-1)
            out[k] = v
        return out  # Bytes/context only; no GPU-utilization claim.


def require_reply_identity(value):
    need(type(value) is dict and type(value.get('model')) is str and
         value['model'] == 'qwen3.5:4b-q4_K_M', 'identity_unverified')


def response_result(value, projection, limits):
    # Identity takes precedence over ordinary envelope/completion errors.
    require_reply_identity(value)
    need(set(value) <= {'model','created_at','message','done','done_reason'} | set(TELEMETRY))
    need(value.get('done') is True)
    need('context' not in value)  # No returned chat context/history retained or reused.
    message = value.get('message')
    need(type(message) is dict and set(message) <= {'role','content','thinking','tool_calls'} and message.get('role') == 'assistant')
    need('tool_calls' not in message or type(message['tool_calls']) is list and not message['tool_calls'])
    content, thinking = message.get('content'), message.get('thinking')
    need(thinking in (None, ''), 'thinking_leakage')
    need(type(content) is str)
    if re.search(r'<\s*/?\s*(?:think|thinking|analysis)\b', content, re.I):
        raise ExperimentError('thinking_leakage')
    telemetry = {k:value.get(k) for k in TELEMETRY}
    for v in telemetry.values():
        need(v is None or type(v) is int and 0 <= v <= 2**63-1)
    need(telemetry['eval_count'] is None or telemetry['eval_count'] <= 512, 'resource_limit')
    need(telemetry['prompt_eval_count'] is None or telemetry['prompt_eval_count'] <= 4096, 'resource_limit')
    need(telemetry['thinking_count'] in (None, 0), 'thinking_leakage')
    try:
        size = len(content.encode('utf-8'))
    except UnicodeError:
        return None, telemetry, 'invalid_structure'
    need(size <= limits['content_bytes'], 'resource_limit')
    try:
        body = strict_json(content)
    except ExperimentError:
        body = None
    if type(body) is dict:
        need(not any(body.get(k) for k in ('thinking','reasoning','analysis')), 'thinking_leakage')
    reason = value.get('done_reason')
    need(reason in ('stop','length'))
    if reason == 'length':
        return None, telemetry, 'truncated'
    if not content.strip():
        return None, telemetry, 'refused'
    try:
        output = parse_prediction(content, projection)
    except ExperimentError as exc:
        return None, telemetry, exc.code
    return output.signature(), telemetry, 'valid'


def score(rows):
    # Keep the frozen scorer's four status meanings; fine-grained failures remain separate.
    converted = [dict(r, status='valid' if r['status'] == 'valid' else 'invalid_output',
                      reason='model_abstain' if r['status'] == 'valid' and r['actual']['state'] == 'abstain' else None) for r in rows]
    return wording.summarize(converted)


def compare(rule_rows, model_rows):
    new_full, lost_full, added_steps, repaired_steps, added_dates, repaired_dates = [], [], 0, 0, 0, 0
    for rule, model in zip(rule_rows, model_rows, strict=True):
        ref = model['reference']
        correct = lambda r: r['status'] == 'valid' and r['actual']['state'] == ref['state'] and wording.atoms(r['actual']['steps']) == wording.atoms(ref['steps']) and wording.atoms(r['actual']['dates']) == wording.atoms(ref['dates'])
        if correct(model) and not correct(rule):new_full.append(model['id'])
        if correct(rule) and not correct(model):lost_full.append(model['id'])
        if model['status'] != 'valid':continue
        wanted = wording.atoms(ref['steps']); actual = wording.atoms(model['actual']['steps']); baseline = wording.atoms(rule['actual']['steps']) if rule['status'] == 'valid' else set()
        repaired_steps += len((actual & wanted) - baseline)
        added_steps += len((actual - wanted) - (baseline - wanted))
        dates = wording.atoms(ref['dates']); given = wording.atoms(model['actual']['dates']); old = wording.atoms(rule['actual']['dates']) if rule['status'] == 'valid' else set()
        added_dates += len((given - dates) - (old - dates))
        repaired_dates += len((given & dates) - old)
    paired_metrics = [(score([model]),wording.summarize([rule])) for rule,model in zip(rule_rows,model_rows,strict=True)]
    return dict(selected=len(model_rows), new_full_case_ids=new_full, lost_full_case_ids=lost_full,
                additional_correct_step_atoms=repaired_steps, additional_unsupported_step_atoms=added_steps,
                additional_wrong_date_atoms=added_dates, additional_correct_date_atoms=repaired_dates,
                additional_errors={k:sum(max(0,m[k]-r[k]) for m,r in paired_metrics) for k in wording.COUNTERS},
                reduced_errors={k:sum(max(0,r[k]-m[k]) for m,r in paired_metrics) for k in wording.COUNTERS}, routing='none; retrospective same-input comparison only')


def run(mode):
    need(mode in ('inventory','smoke','full'))
    config, corpus = setup()
    selected = corpus if mode == 'full' else [next(c for c in corpus if c['id'] == id_) for id_ in config['smoke']]
    deadline = time.monotonic() + config['limits']['run_seconds']
    client = Transport(config, corpus, deadline)
    rows, rules = [], []
    if mode != 'inventory':
        for c in selected:
            base = dict(id=c['id'], group=c['group'], variant=c['variant'], reference=c['reference'])
            rows.append(dict(base, status='not_attempted', attempted=False, actual=None,
                             telemetry={k:None for k in TELEMETRY}, latency_seconds=None, residency=None))
            try:
                p = engine.EmailMetadata(c['input']); result = engine.interpret(p); engine.validate_result(result,p)
                rules.append(dict(base, status='valid', actual=wording.signature(result), reason=result.reason.value))
            except Exception:
                rules.append(dict(base, status='interpreter_error', actual=None, reason=None))
    initial, final, resident, stopped = None, None, None, None
    identity_tainted = False
    def observe():
        nonlocal identity_tainted
        try:
            identity = client.identity()
            need(initial is None or identity == initial, 'identity_unverified')
            return identity
        except ExperimentError:
            identity_tainted = True
            raise
    try:
        initial = observe()
        resident = client.residency()
        if mode != 'inventory':
            for c, row in zip(selected, rows, strict=True):
                observe()
                try:
                    p = engine.EmailMetadata(c['input'])
                except engine.EmailEvidenceError:
                    row['status'] = 'input_rejected'
                    continue
                payload = client.payload(p)
                row['attempted'] = True
                started = time.monotonic()
                try:
                    response = client.request('POST', '/api/chat', payload)
                    row['latency_seconds'] = round(time.monotonic()-started, 6)
                    row['actual'], row['telemetry'], row['status'] = response_result(response,p,config['limits'])
                    row['residency'] = client.residency()
                except ExperimentError as exc:
                    row['latency_seconds'] = round(time.monotonic()-started, 6)
                    row['status'] = exc.code
                    raise
    except ExperimentError as exc:
        stopped = exc.code
        identity_tainted |= exc.code == 'identity_unverified'
    except KeyboardInterrupt:
        stopped = 'interrupted'
        for row in rows:
            if row['attempted'] and row['status'] == 'not_attempted':row['status'] = 'interrupted'
    finally:
        try:
            final = observe()
            if initial is None or final != initial:stopped = 'identity_unverified'
        except ExperimentError as exc:
            final = None
            if stopped is None:stopped = exc.code
    verified = initial is not None and final == initial and not identity_tainted
    complete = mode == 'inventory' and stopped is None or bool(rows) and all(r['attempted'] for r in rows) and stopped is None
    metrics = score(rows) if verified and mode != 'inventory' else None
    groups = {g:score([r for r in rows if r['group'] == g]) for g in wording.GROUPS if any(r['group'] == g for r in rows)} if metrics else None
    return dict(experiment=config['experiment'], config_lf_sha256=CONFIG_SHA, freeze_commit=FREEZE,
        input_fixture_lf_sha256=wording.FIXTURE_SHA256, prompt_sha256=sha256(config['prompt'].encode()).hexdigest(),
        schema_sha256=sha256(wording.canonical(config['output_schema']).encode()).hexdigest(),
        interpreter_version=wording.VERSION, interpreter_lf_sha256=wording.ENGINE_SHA256,
        rule_fingerprint=wording.RULE_FINGERPRINT, scorer_lf_sha256=SCORER_SHA,
        mode=mode, run_status='complete' if complete and verified else 'partial', stop_code=stopped,
        identity_verified_at_end=verified, observed_identity=final if verified else None,
        configured_candidate=config['model'], initial_residency=resident,
        control_observation=dict(first_attempt_status=next((r['status'] for r in rows if r['attempted']),None),
            structured_reply_observed=bool(rows and rows[0]['status']=='valid'),
            interpretation='schema + think:false requested; observed compliance is not proof of internal computation or constrained decoding'),
        generation=config['generation'], limits=config['limits'],
        restrictions=dict(authority='none', sender_claim_only=True, human_review_required=True,
                          independent_safety_and_authorization_required=True),
        notice='CORRELATED SEEN SYNTHETIC CASES; NOT BLIND, INDEPENDENT OR REAL-WORLD ACCURACY',
        corpus=dict(selected=36,clear=24,ambiguous=12,groups=12),
        selected=dict(cases=len(rows),clear=sum(r['variant']!='ambiguous' for r in rows),ambiguous=sum(r['variant']=='ambiguous' for r in rows),groups=len({r['group'] for r in rows})),
        status_counts=dict(Counter(r['status'] for r in rows)), attempted=sum(r['attempted'] for r in rows),
        model_metrics=metrics, by_group=groups,
        rule_metrics=wording.summarize(rules) if rules else None,
        rule_by_group={g:wording.summarize([r for r in rules if r['group']==g]) for g in wording.GROUPS if any(r['group']==g for r in rules)},
        comparison=compare(rules,rows) if complete and verified and mode != 'inventory' and all(r['status']=='valid' for r in rules) else None,
        cases=rows, rule_cases=rules)


def save(report):
    payload = wording.canonical(report)+'\n'
    target = ROOT / LOCAL
    for p in (ROOT/'.local',target):
        wording.parents(p);p.mkdir(mode=0o700,exist_ok=True);wording.regular(p,True)
    directory = target/uuid4().hex
    directory.mkdir(mode=0o700)
    temporary, path = directory/'report.json.tmp', directory/'report.json'
    created = False
    try:
        with temporary.open('x',encoding='utf-8') as f:
            created = True;f.write(payload);f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
    except BaseException:
        if created:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass
        try:directory.rmdir()
        except OSError:pass
        raise
    return path.relative_to(ROOT).as_posix()


def main(argv=None):
    p = argparse.ArgumentParser(description='Fixed synthetic wording evidence experiment; manual local Ollama only')
    p.add_argument('--synthetic-only',action='store_true',required=True)
    p.add_argument('mode',choices=('inventory','smoke','full'))
    args = p.parse_args(argv)
    try:
        result = run(args.mode)
        path = save(result)
        print(f"合成邮件文字证据对照（非真实准确率）：{args.mode}；{result['run_status']}；尝试 {result['attempted']}/{result['selected']['cases']}\n身份结束核验：{result['identity_verified_at_end']}；停止码：{result['stop_code'] or 'none'}")
        if result['model_metrics'] is not None:
            m = result['model_metrics']
            print(f"清晰完整/部分/abstain：{m['clear_outcomes']['full']}/{m['clear_outcomes']['partial']}/{m['clear_outcomes']['abstain']}（分母 {m['clear']}）；遗漏步骤/日期：{m['missed_outstanding_cases']}/{m['missed_date_cases']}；歧义越界：{m['ambiguous_overreach']}")
        print(f'报告：{path}')
        return 0 if result['run_status'] == 'complete' else 2
    except Exception:
        print('实验失败；没有发布成功摘要。错误码：protocol_error')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
