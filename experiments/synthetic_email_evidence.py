"""Only the newly preregistered email fixtures; no legacy/Development/Holdout access."""
import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
from uuid import uuid4

from family_os import _synthetic_email_evidence as engine

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path('fixtures/synthetic-email-evidence-v1.json')
LOCAL = Path('.local/synthetic-email-evidence')
FIXTURE_SHA256 = 'd810937cd5e1b2d0e35f6d1b98d6f85dc05a51cf7b83a135fed8a8bd2c188f13'
CONTRACT_SHA256 = 'cd0c68e4130f3e0c14ee1900688af9aa03f2053d3e7c0b5954a3162cc4e99c63'
FILE_BYTES = 131072
WINDOWS = sys.platform == 'win32'


def regular(path, directory=False):
    s = path.lstat()
    engine.require(not stat.S_ISLNK(s.st_mode) and not getattr(s, 'st_file_attributes', 0) & 0x400)
    engine.require(stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode) and s.st_nlink == 1)
    return s


def identity(s):
    return s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def cross_api_identity(s):
    # Windows path stat may expose birthtime as ctime; fstat uses ChangeTime.
    # Each API still checks its own ctime, along with all six other fields.
    fields = identity(s)
    return fields[:-1] if WINDOWS else fields


def parents(path):
    for p in reversed(path.absolute().parents): regular(p, True)


def read_fixture():
    engine.require(FIXTURE == Path('fixtures/synthetic-email-evidence-v1.json'))
    path = ROOT / FIXTURE
    parents(path)
    before = regular(path)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        handle_before = os.fstat(stream.fileno())
        engine.require(cross_api_identity(handle_before) == cross_api_identity(before))
        raw = stream.read(FILE_BYTES + 1)
        engine.require(identity(os.fstat(stream.fileno())) == identity(handle_before))
    engine.require(identity(regular(path)) == identity(before) and len(raw) <= FILE_BYTES)
    # Canonical LF identity is invariant under Windows checkout line endings.
    raw = raw.replace(b'\r\n', b'\n')
    engine.require(sha256(raw).hexdigest() == FIXTURE_SHA256)
    def unique(pairs):
        value = {}
        for k, v in pairs:
            engine.require(k not in value)
            value[k] = v
        return value
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda _: engine.require(False))


def load():
    data = read_fixture()
    engine.require(type(data) is dict and set(data) == {'synthetic_only', 'dataset_version', 'contract', 'cases'})
    engine.require(data['synthetic_only'] is True and data['dataset_version'] == 'synthetic-email-evidence-fixtures-v1')
    engine.require(engine.digest(data['contract']) == CONTRACT_SHA256 == engine.digest(engine.contract_description()))
    cases = data['cases']
    engine.require(type(cases) is list and len(cases) == 75)
    ids, groups = set(), {}
    for c in cases:
        engine.require(type(c) is dict and set(c) == {'id', 'family', 'pair', 'input', 'expected'})
        engine.require(type(c['id']) is str and c['id'].startswith('email-evidence-v1-') and c['id'] not in ids)
        ids.add(c['id'])
        engine.require(type(c['family']) is str and type(c['input']) is dict)
        if c['pair']:
            engine.require(type(c['pair']) is str)
            groups.setdefault(c['pair'], []).append(c)
        gold = c['expected']
        if gold is None: continue
        engine.require(type(gold) is dict and set(gold) == {'state', 'steps', 'dates', 'reason'})
        engine.State(gold['state']); engine.Reason(gold['reason'])
        engine.require(type(gold['steps']) is list and type(gold['dates']) is list)
        for a, s in gold['steps']: engine.StepEvidence(engine.Action(a), engine.Status(s))
        for role, value, a in gold['dates']: engine.DateEvidence(engine.DateRole(role), value, engine.Action(a) if a else None)
    engine.require(sum(c['expected'] is not None for c in cases) == 59 and len(groups) == 8)
    for members in groups.values():
        engine.require(len(members) == 2 and all(c['expected'] is not None for c in members))
        a, b = (c['input'] for c in members)
        engine.require(set(a) == set(b) and {k for k in a if a[k] != b[k]} in ({'subject'}, {'notice_kind'}))
    return cases


def signature(result):
    return dict(state=result.state, steps=[[s.action, s.status] for s in result.steps],
                dates=[[d.role, d.value, d.action] for d in result.dates], reason=result.reason)


def ratio(a, b): return a / b if b else None


def summarize(rows):
    selected = [r for r in rows if r['expected'] is not None]
    controls = [r for r in selected if r['expected']['state'] != 'abstain']
    valid = [r for r in selected if r['status'] == 'valid']
    false_obligation = false_clearance = missed_steps = wrong_dates = 0
    for row in valid:
        gold, actual = row['expected'], row['actual']
        want_out = {a for a, s in gold['steps'] if s == 'reported_outstanding'}
        got_out = {a for a, s in actual['steps'] if s == 'reported_outstanding'}
        invented_completion = any([a, s] not in gold['steps'] for a, s in actual['steps'] if s == 'reported_completed')
        false_obligation += bool(got_out - want_out)
        missed_steps += bool(want_out - got_out)
        false_clearance += bool(invented_completion or (want_out - got_out and actual['state'] not in ('abstain', 'explicit_outstanding')))
        wrong_dates += any(d not in gold['dates'] for d in actual['dates'])
    correct = sum(r['status'] == 'valid' and r['actual'] == r['expected'] for r in selected)
    return dict(selected=len(rows), expected_valid=len(selected), expected_invalid=len(rows)-len(selected),
        status_counts=dict(Counter(r['status'] for r in rows)),
        by_expected_state={state:dict(selected=sum(r['expected']['state']==state for r in selected),
            exact_correct=sum(r['expected']['state']==state and r['status']=='valid' and r['actual']==r['expected'] for r in selected)) for state in engine.State},
        supported_controls=len(controls), supported_exact=sum(r['status'] == 'valid' and r['actual'] == r['expected'] for r in controls),
        semantic_exact=correct, semantic_exact_rate=ratio(correct, len(selected)),
        expected_state_counts=dict(Counter(r['expected']['state'] for r in selected)),
        actual_state_counts=dict(Counter(r['actual']['state'] for r in valid)),
        correct_safety_rejections=sum(r['expected'] is None and r['status'] == 'input_rejected' for r in rows),
        unsafe_input_accepted=sum(r['expected'] is None and r['status'] != 'input_rejected' for r in rows),
        unexpected_input_rejections=sum(r['expected'] is not None and r['status'] == 'input_rejected' for r in rows),
        false_obligation_cases=false_obligation, false_clearance_cases=false_clearance,
        missed_explicit_step_cases=missed_steps + sum(r['status'] != 'valid' and any(s == 'reported_outstanding' for _, s in r['expected']['steps']) for r in selected),
        invented_or_misbound_date_cases=wrong_dates,
        unsupported_overreach_cases=sum(r['expected']['state'] == 'abstain' and r['actual']['state'] != 'abstain' for r in valid),
        missed_date_cases=sum(bool(r['expected']['dates']) and (r['status'] != 'valid' or any(d not in r['actual']['dates'] for d in r['expected']['dates'])) for r in selected),
        abstentions=sum(r['actual']['state'] == 'abstain' for r in valid),
        abstention_reasons=dict(Counter(r['actual']['reason'] for r in valid if r['actual']['state'] == 'abstain')),
        invalid_or_failed_outputs=sum(r['status'] in ('interpreter_error', 'invalid_output') for r in rows))


def report(interpreter=engine.interpret):
    cases = load()  # All labels/schema/pins validated before any interpretation.
    rows = []
    for c in cases:
        row = dict(id=c['id'], family=c['family'], pair=c['pair'], expected=c['expected'],
                   status='input_rejected', actual=None, output=None)
        try:
            projection = engine.EmailMetadata(c['input'])
        except engine.EmailEvidenceError:
            rows.append(row); continue
        try:
            output = interpreter(projection)  # Only projection, never ID/gold/family.
        except Exception:
            row['status'] = 'interpreter_error'
        else:
            try:
                engine.validate_result(output, projection)
                row.update(status='valid', actual=signature(output), output=asdict(output))
            except Exception:
                row['status'] = 'invalid_output'
        rows.append(row)
    pairs = {}
    for r in rows:
        if r['pair']: pairs.setdefault(r['pair'], []).append(r)
    complete = [members for members in pairs.values() if all(r['status'] == 'valid' for r in members)]
    correct_pairs = sum(all(r['actual'] == r['expected'] for r in members) for members in complete)
    return dict(contract='synthetic-email-evidence-evaluation-v1',
        notice='SYNTHETIC CONTRACT PROBES ONLY — NOT REAL-WORLD ACCURACY',
        fixture_lf_sha256=FIXTURE_SHA256, contract_sha256=CONTRACT_SHA256,
        interpreter_version=engine.VERSION, rule_fingerprint=engine.RULE_FINGERPRINT,
        metrics=summarize(rows), by_family={family:summarize([r for r in rows if r['family'] == family]) for family in sorted({r['family'] for r in rows})},
        counterfactual=dict(selected=len(pairs), valid=len(complete), exact_correct=correct_pairs,
            exact_rate=ratio(correct_pairs, len(pairs)),
            semantic_changes=sum(a['actual'] != b['actual'] for a, b in complete),
            state_changes=sum(a['actual']['state'] != b['actual']['state'] for a, b in complete)), cases=rows)


def save(result):
    payload = engine.canonical(result) + '\n'
    target = ROOT / LOCAL
    for p in (ROOT / '.local', target):
        parents(p); p.mkdir(mode=0o700, exist_ok=True); regular(p, True)
    run = target / uuid4().hex
    run.mkdir(mode=0o700)
    path = run / 'report.json'
    temporary = run / 'report.json.tmp'
    created = False
    try:
        with temporary.open('x', encoding='utf-8') as f:
            created = True
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    except BaseException:
        # Remove only our own temporary file; never recursively remove a run.
        if created:
            try: temporary.unlink(missing_ok=True)
            except OSError: pass
        try: run.rmdir()
        except OSError: pass
        raise
    return path.relative_to(ROOT).as_posix()


def main(argv=None):
    parser = argparse.ArgumentParser(description='New synthetic email evidence contract probes only; no models')
    parser.add_argument('--synthetic-only', required=True, action='store_true')
    parser.parse_args(argv)
    try:
        result = report(); m = result['metrics']; path = save(result)
        print(f"语义精确符合（semantic_exact）：{m['semantic_exact']}/{m['expected_valid']}；不支持表达的越界解释：{m['unsupported_overreach_cases']}；遗漏显式日期：{m['missed_date_cases']}")
        print(f"合成邮件行动证据 v1（非真实世界准确率）\n有效样本：{m['expected_valid']}；安全拒绝：{m['correct_safety_rejections']}/{m['expected_invalid']}\n支持正控：{m['supported_exact']}/{m['supported_controls']}；误提义务：{m['false_obligation_cases']}；错误清除：{m['false_clearance_cases']}\nabstain：{m['abstentions']}；错误/无效输出：{m['invalid_or_failed_outputs']}；反事实成对全对：{result['counterfactual']['exact_correct']}/{result['counterfactual']['selected']}\n仅文字证据，无 Task/Pending 或行动权限；详细诊断：{path}")
        return 0
    except Exception:
        print('合成邮件证据评估失败；未输出部分结果或案例内容。')
        return 1


if __name__ == '__main__': raise SystemExit(main())
