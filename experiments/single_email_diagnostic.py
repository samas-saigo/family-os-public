"""Manual one-chat synthetic runtime diagnostic. No scoring or production integration."""
import argparse
from contextlib import contextmanager
from hashlib import sha256
import http.client
import os
from pathlib import Path
import re
import socket
import time
from uuid import uuid4

from experiments import email_model_evidence as parent

wording, engine = parent.wording, parent.engine
ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path('experiments/configs/single-email-runtime-diagnostic-v1.json')
CONFIG_SHA = 'fced8bb829337db363ba3bb738beac4034df66bb662468f23420817fe2b80544'
PARENT_SHA = 'b0b1dc39f974af8c6f3c74cefeee4950663e83f8bc7bacff006a9c05aa035fd8'
FREEZE = '09916e959bda2a719a5ef962017a1f56cb3f7b72'
LOCAL = Path('.local/single-email-runtime-diagnostic')
need, Error = parent.need, parent.ExperimentError


def read_pin(relative, expected):
    need(relative in (CONFIG, Path('experiments/email_model_evidence.py')), 'input_rejected')
    path = ROOT / relative
    wording.parents(path)
    before = wording.regular(path)
    need(before.st_size <= 65536, 'resource_limit')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        handle = os.fstat(stream.fileno())
        need(wording.cross_api_identity(handle) == wording.cross_api_identity(before), 'input_rejected')
        raw = stream.read(65537)
        need(wording.identity(handle) == wording.identity(os.fstat(stream.fileno())), 'input_rejected')
    need(wording.identity(before) == wording.identity(wording.regular(path)) and len(raw) <= 65536, 'input_rejected')
    raw = raw.replace(b'\r\n', b'\n')
    need(sha256(raw).hexdigest() == expected, 'input_rejected')
    return raw


def setup():
    need(ROOT == parent.ROOT and Path(parent.__file__).absolute() == ROOT / 'experiments/email_model_evidence.py', 'input_rejected')
    read_pin(Path('experiments/email_model_evidence.py'), PARENT_SHA)
    config = parent.strict_json(read_pin(CONFIG, CONFIG_SHA).decode('utf-8'))
    original, cases = parent.setup()  # Fixed wording-only loader; no scorer invocation.
    need(all(config[k] == original[k] for k in ('model', 'prompt', 'output_schema', 'generation')), 'input_rejected')
    selected = [c for c in cases if c['id'] == 'WC01-1']
    need(len(selected) == 1, 'input_rejected')
    return config, original, engine.EmailMetadata(selected[0]['input'])


class Transport(parent.Transport):
    """Reuse unchanged identity/payload policy, with separately pinned budgets.

    Request transport is explicit here: never monkeypatch the frozen runner or
    pass an altered config through its original constructor.
    """
    def __init__(self, config, deadline):
        expected, original, projection = setup()
        need(config == expected, 'input_rejected')
        self.config, self.limits, self.deadline = original, config['limits'], deadline
        self.allowed = {wording.canonical(dict(projection.fields))}
        self.chat_attempts, self.requests = 0, []

    def request(self, method, path, value=None):
        need((method, path) in {('GET', '/api/version'), ('GET', '/api/tags'),
                               ('GET', '/api/ps'), ('POST', '/api/show'), ('POST', '/api/chat')})
        chat = path == '/api/chat'
        if method == 'GET':
            need(value is None)
        elif path == '/api/show':
            need(wording.canonical(value) == wording.canonical({'model': self.config['model']['tag'], 'verbose': False}))
        else:
            need(type(value) is dict and type(value.get('messages')) is list and len(value['messages']) == 2, 'input_rejected')
            try:
                p = engine.EmailMetadata(parent.strict_json(value['messages'][1]['content']))
                need(wording.canonical(value) == wording.canonical(self.payload(p)), 'input_rejected')
            except (KeyError, TypeError, engine.EmailEvidenceError):
                raise Error('input_rejected') from None
            need(self.chat_attempts == 0, 'resource_limit')
        raw = None if value is None else wording.canonical(value).encode('utf-8')
        need(raw is None or len(raw) <= self.limits['request_bytes'], 'resource_limit')
        maximum = self.limits['chat_seconds' if chat else 'metadata_seconds']
        started = time.monotonic()
        end = min(self.deadline, started + maximum)
        self.remaining()  # No connection or extra chat after the total deadline.
        if chat:
            self.chat_attempts += 1  # Consume even if connect/send fails; never retry.
        entry = dict(endpoint=path, elapsed_seconds=None, phases={})
        self.requests.append(entry)
        connection, response = None, None

        @contextmanager
        def phase(name):
            begin = time.monotonic()
            timing = dict(elapsed_seconds=None, completed=False)
            entry['phases'][name] = timing
            try:
                yield
                timing['completed'] = True
            finally:
                timing['elapsed_seconds'] = round(max(0, time.monotonic() - begin), 6)

        try:
            with phase('connect'):
                connection = http.client.HTTPConnection('127.0.0.1', 11434,
                    timeout=min(self.limits['connect_seconds'], self.remaining(), end - time.monotonic()))
                connection.connect()
                connection.sock = parent.DeadlineSocket(connection.sock, end, maximum, self.limits['response_header_bytes'])
            wire = connection.sock

            def bound():
                left = min(end - time.monotonic(), self.remaining())
                need(left > 0, 'timeout')
                wire.settimeout(left)

            with phase('send'):
                bound()
                connection.request(method, path, body=raw, headers={'Accept': 'application/json', 'Content-Type': 'application/json', 'Connection': 'close'})
                bound()
            with phase('response_headers'):
                response = connection.getresponse()
                wire.headers_done = True
                bound()
                need(response.status == 200)
                headers = response.getheaders()
                need(sum(len(k) + len(v) for k, v in headers) <= self.limits['response_header_bytes'], 'resource_limit')
                need(response.getheader('Content-Type', '').lower() in ('application/json', 'application/json; charset=utf-8'))
                need(response.getheader('Content-Encoding') in (None, 'identity'))
                length = response.getheader('Content-Length')
                if length is not None:
                    need(bool(re.fullmatch('[0-9]{1,6}', length)) and int(length) <= self.limits['response_bytes'], 'resource_limit')
            with phase('response_body'):
                chunks, size = [], 0
                while True:
                    bound()
                    data = response.read1(min(4096, self.limits['response_bytes'] + 1 - size))
                    if not data:
                        break
                    size += len(data)
                    need(size <= self.limits['response_bytes'], 'resource_limit')
                    chunks.append(data)
                bound()
                if length is not None:
                    need(size == int(length))
            with phase('parse_envelope'):
                try:
                    result = parent.strict_json(b''.join(chunks).decode('utf-8'))
                except (Error, UnicodeError):
                    raise Error('identity_unverified' if chat else 'protocol_error') from None
                if chat:
                    parent.require_reply_identity(result)
                need(type(result) is dict and 'error' not in result)
                bound()
            return result
        except Error:
            raise
        except (TimeoutError, socket.timeout):
            raise Error('timeout') from None
        except (OSError, http.client.HTTPException, ValueError):
            raise Error('transport_error') from None
        finally:
            entry['elapsed_seconds'] = round(max(0, time.monotonic() - started), 6)
            if response is not None:
                response.close()
            if connection is not None:
                connection.close()


def run():
    started = time.monotonic()
    config, _, projection = setup()
    client = Transport(config, started + config['limits']['run_seconds'])
    initial, final, resident, stopped = None, None, None, None
    tainted = False
    result = dict(id='WC01-1', attempted=False, status='not_attempted', prediction=None,
                  telemetry={k: None for k in parent.TELEMETRY},
                  chat_response_seconds=None, validation_seconds=None)

    def observe():
        nonlocal tainted
        try:
            value = client.identity()
            need(initial is None or value == initial, 'identity_unverified')
            return value
        except Error:
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
            result['prediction'], result['telemetry'], result['status'] = parent.response_result(response, projection, config['limits'])
            client.remaining()
        finally:
            result['validation_seconds'] = round(max(0, time.monotonic() - validation_start), 6)
    except Error as exc:
        stopped = exc.code
        tainted |= exc.code == 'identity_unverified'
        if result['attempted']:
            result['status'] = exc.code
    except KeyboardInterrupt:
        stopped = 'interrupted'
        if result['attempted']:
            result['status'] = stopped
    finally:
        try:
            final = observe()
            if initial is None or final != initial:
                tainted = True
        except Error as exc:
            final = None
            if stopped is None:
                stopped = exc.code
        except KeyboardInterrupt:
            tainted = True
            if stopped is None:
                stopped = 'interrupted'
    verified = initial is not None and final == initial and not tainted
    return dict(diagnostic=config['diagnostic'], freeze_commit=FREEZE,
                config_lf_sha256=CONFIG_SHA, parent_config_lf_sha256=parent.CONFIG_SHA,
                parent_runner_lf_sha256=PARENT_SHA,
                input_fixture_lf_sha256=wording.FIXTURE_SHA256,
                prompt_sha256=sha256(config['prompt'].encode()).hexdigest(),
                schema_sha256=sha256(wording.canonical(config['output_schema']).encode()).hexdigest(),
                configured_candidate=config['model'], generation=config['generation'], limits=config['limits'],
                run_status='complete' if verified and stopped is None and result['status'] == 'valid' else 'partial',
                stop_code=stopped, selected=1, attempted=int(result['attempted']),
                identity_verified_at_end=verified, observed_identity=final if verified else None,
                prediction_attribution='observed_candidate' if verified else 'unattributed_diagnostic',
                initial_residency=resident, total_elapsed_seconds=round(max(0, time.monotonic() - started), 6),
                requests=client.requests, result=result,
                restrictions=dict(authority='none', sender_claim_only=True, human_review_required=True,
                                  independent_safety_and_authorization_required=True),
                notice='RUNTIME DIAGNOSTIC ONLY; NO ACCURACY, SEMANTIC SCORE OR MODEL COMPARISON; PR107 60-SECOND RESULT UNCHANGED')


def save(report):
    payload = wording.canonical(report) + '\n'
    target = ROOT / LOCAL
    for p in (ROOT / '.local', target):
        wording.parents(p)
        p.mkdir(mode=0o700, exist_ok=True)
        wording.regular(p, True)
    directory = target / uuid4().hex
    directory.mkdir(mode=0o700)
    temporary, path = directory / 'report.json.tmp', directory / 'report.json'
    created = False
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            created = True
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if created:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            directory.rmdir()
        except OSError:
            pass
        raise
    return path.relative_to(ROOT).as_posix()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Independent single-case runtime diagnostic; manual synthetic-only, not PR107 evaluation')
    parser.add_argument('--synthetic-only', action='store_true', required=True)
    parser.add_argument('mode', choices=('single',))
    parser.parse_args(argv)
    try:
        report = run()
        path = save(report)
        r = report['result']
        print(f"独立单条运行诊断（非准确率评估；不替代 PR107 的60秒结果）：{report['run_status']}；尝试 {report['attempted']}/1")
        print(f"结果：{r['status']}；总耗时：{report['total_elapsed_seconds']}秒；完整响应耗时：{r['chat_response_seconds']}；结束身份核验：{report['identity_verified_at_end']}；停止码：{report['stop_code'] or 'none'}")
        print(f'报告：{path}')
        return 0 if report['run_status'] == 'complete' else 2
    except (Exception, KeyboardInterrupt):
        print('诊断未能发布完整报告；错误码：diagnostic_failed。未输出模型或驱动原文。')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
