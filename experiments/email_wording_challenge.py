"""Manual frozen-interpreter wording challenge. No old loader, models or product state."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
from uuid import uuid4

from family_os import _synthetic_email_evidence as engine

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path('fixtures/synthetic-email-wording-challenge-v1.json')
ENGINE = Path('src/family_os/_synthetic_email_evidence.py')
LOCAL = Path('.local/email-wording-challenge')
FIXTURE_SHA256 = '067b041f142ce9892509f7024ff5d94c6a4a34be2fdd59d4d2e91a408a44b019'
ENGINE_SHA256 = '44e391f3748799c8552703cee92d77fd84166a23e04006f9c3876262c2b0d025'
VERSION = 'synthetic-email-evidence-e1-065517d552adb8de'
RULE_FINGERPRINT = '065517d552adb8dec3fe4ee88ef32158ae8d4b79d90cafaa9c322fbd29a1eb4b'
FREEZE_COMMIT = '80741385760c87d6c7b0dc1f0d514d8b1be96051'
SCHEMA = 'synthetic-email-wording-challenge-v1'
GROUPS = ('payment_due', 'autopay_complete', 'autopay_remedy', 'bill_notice',
          'renewal_due', 'renewal_complete', 'cancel_refund', 'cancel_reschedule',
          'form_complete', 'payment_plus_form', 'promotion_expiry', 'visit_notice')
VARIANTS = ('paraphrase_a', 'paraphrase_b', 'ambiguous')
FILE_BYTES = 65536
WINDOWS = sys.platform == 'win32'


class ChallengeError(ValueError):
    def __init__(self):
        super().__init__('Synthetic wording challenge rejected')


def require(condition):
    if not condition:
        raise ChallengeError()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def regular(path, directory=False):
    s = path.lstat()
    require(not stat.S_ISLNK(s.st_mode) and not getattr(s, 'st_file_attributes', 0) & 0x400)
    require(stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode) and s.st_nlink == 1)
    return s


def parents(path):
    for p in reversed(path.absolute().parents):
        regular(p, True)


def identity(s):
    return s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def cross_api_identity(s):
    # Windows 3.12 path stat preserves birthtime in ctime, whereas fstat can
    # expose ChangeTime. Retain ctime in each API's own before/after check.
    fields = identity(s)
    return fields[:-1] if WINDOWS else fields


def read_pinned(relative):
    # Check the literal path before any filesystem operation; no caller CLI paths.
    allowed = {Path('fixtures/synthetic-email-wording-challenge-v1.json'): FIXTURE_SHA256,
               Path('src/family_os/_synthetic_email_evidence.py'): ENGINE_SHA256}
    require(relative in allowed)
    path = ROOT / relative
    parents(path)
    before = regular(path)
    require(before.st_size <= FILE_BYTES)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        handle_before = os.fstat(stream.fileno())
        require(cross_api_identity(handle_before) == cross_api_identity(before))
        raw = stream.read(FILE_BYTES + 1)
        require(identity(os.fstat(stream.fileno())) == identity(handle_before))
    require(identity(regular(path)) == identity(before) and len(raw) <= FILE_BYTES)
    raw = raw.replace(b'\r\n', b'\n')
    require(sha256(raw).hexdigest() == allowed[relative])
    return raw


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def validate_reference(ref):
    require(type(ref) is dict and set(ref) == {'state', 'steps', 'dates'})
    state = engine.State(ref['state'])
    require(type(ref['steps']) is list and len(ref['steps']) <= 2)
    require(type(ref['dates']) is list and len(ref['dates']) <= 1)
    for step in ref['steps']:
        require(type(step) is list and len(step) == 2)
        engine.StepEvidence(engine.Action(step[0]), engine.Status(step[1]))
    require(len({a for a, _ in ref['steps']}) == len(ref['steps']))
    for d in ref['dates']:
        require(type(d) is list and len(d) == 3)
        engine.DateEvidence(engine.DateRole(d[0]), d[1], engine.Action(d[2]) if d[2] is not None else None)
    if state is engine.State.ABSTAIN:
        require(not ref['steps'] and not ref['dates'])
    elif state is engine.State.OUTSTANDING:
        require(any(s == 'reported_outstanding' for _, s in ref['steps']))
    elif state is engine.State.COMPLETION:
        require(bool(ref['steps']) and all(s == 'reported_completed' for _, s in ref['steps']))
    elif state is engine.State.INFORMATION:
        require(all(s in ('reported_failed', 'reported_cancelled') for _, s in ref['steps']))
    else:
        require(not ref['steps'])


def load():
    require(FIXTURE == Path('fixtures/synthetic-email-wording-challenge-v1.json'))
    require(ENGINE == Path('src/family_os/_synthetic_email_evidence.py'))
    require(Path(engine.__file__).absolute() == (ROOT / ENGINE).absolute())
    read_pinned(ENGINE)
    require(engine.VERSION == VERSION and engine.RULE_FINGERPRINT == RULE_FINGERPRINT)
    data = json.loads(read_pinned(FIXTURE).decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda _: require(False))
    require(type(data) is dict and set(data) == {'schema', 'synthetic_only', 'cases'})
    require(data['schema'] == SCHEMA and data['synthetic_only'] is True)
    cases = data['cases']
    require(type(cases) is list and len(cases) == 36)
    for index, c in enumerate(cases):
        require(type(c) is dict and set(c) == {'id', 'group', 'variant', 'input', 'reference'})
        group, variant = divmod(index, 3)
        require(c['id'] == f'WC{group+1:02}-{variant+1}')
        require(c['group'] == GROUPS[group] and c['variant'] == VARIANTS[variant])
        v = c['input']
        require(type(v) is dict and set(v) == {'schema', 'synthetic_only', 'provider', 'record_type', 'notice_kind', 'subject'})
        require(v['schema'] == 'synthetic-email-metadata-v1' and v['synthetic_only'] is True)
        require(v['provider'] in ('gmail', 'outlook') and v['record_type'] == 'message')
        require(v['notice_kind'] == ('promotional' if c['group'] == 'promotion_expiry' else 'service'))
        require(type(v['subject']) is str and 0 < len(v['subject']) <= 360)
        require(len(canonical(v).encode('utf-8')) <= 2048)
        validate_reference(c['reference'])
        require((c['reference']['state'] == 'abstain') == (variant == 2))
        if variant == 1:
            require(c['reference'] == cases[index-1]['reference'])
    require(sum(any(s == 'reported_outstanding' for _, s in c['reference']['steps']) for c in cases) == 12)
    require(sum(bool(c['reference']['dates']) for c in cases) == 16)
    require(sum(any(s == 'reported_completed' for _, s in c['reference']['steps']) for c in cases) == 8)
    return cases


def signature(result):
    # Deliberately omit input fingerprint and all original field values.
    return dict(state=result.state.value, steps=[[s.action.value, s.status.value] for s in result.steps],
                dates=[[d.role.value, d.value, d.action.value if d.action else None] for d in result.dates])


def atoms(values):
    return {tuple(value) for value in values}


def ratio(n, d):
    return n / d if d else None


COUNTERS = ('missed_outstanding_cases', 'missed_outstanding_steps', 'unsupported_step_cases',
            'unsupported_steps', 'unsupported_outstanding_cases', 'unsupported_outstanding_steps',
            'unsupported_completion_cases', 'unsupported_completion_steps', 'ambiguous_overreach',
            'missed_date_cases', 'missed_dates', 'invented_date_cases', 'invented_dates',
            'misbound_date_cases', 'misbound_dates', 'false_clearance_proxy_cases')


def summarize(rows):
    clear = [r for r in rows if r['variant'] != 'ambiguous']
    ambiguous = [r for r in rows if r['variant'] == 'ambiguous']
    counts = Counter({key: 0 for key in COUNTERS})
    outcomes = Counter()
    abstentions = Counter()
    for r in rows:
        ref, got = r['reference'], r['actual']
        valid = r['status'] == 'valid'
        wanted, dates = atoms(ref['steps']), atoms(ref['dates'])
        actual = atoms(got['steps']) if valid else set()
        actual_dates = atoms(got['dates']) if valid else set()
        outstanding = {s for s in wanted if s[1] == 'reported_outstanding'}
        missing = outstanding - actual
        extra = actual - wanted
        extra_outstanding = {s for s in extra if s[1] == 'reported_outstanding'}
        extra_completed = {s for s in extra if s[1] == 'reported_completed'}
        missed_dates = dates - actual_dates
        invented = {d for d in actual_dates if d[1] not in {w[1] for w in dates}}
        misbound = {d for d in actual_dates - dates if d[1] in {w[1] for w in dates}}
        for name, values in (('missed_outstanding', missing), ('unsupported_step', extra),
                             ('unsupported_outstanding', extra_outstanding), ('unsupported_completion', extra_completed)):
            counts[name + '_cases'] += bool(values)
            counts[{'missed_outstanding':'missed_outstanding_steps', 'unsupported_step':'unsupported_steps',
                    'unsupported_outstanding':'unsupported_outstanding_steps', 'unsupported_completion':'unsupported_completion_steps'}[name]] += len(values)
        for name, values in (('missed', missed_dates), ('invented', invented), ('misbound', misbound)):
            counts[name + '_date_cases'] += bool(values)
            counts[name + '_dates'] += len(values)
        if valid:
            if got['state'] == 'abstain':
                abstentions[r['reason']] += 1
            counts['false_clearance_proxy_cases'] += bool(missing and got['state'] in ('explicit_completion', 'informational', 'promotional'))
        if r['variant'] == 'ambiguous':
            counts['ambiguous_overreach'] += bool(valid and got['state'] != 'abstain')
        else:
            if not valid:
                outcome = r['status']
            elif got['state'] == ref['state'] and actual == wanted and actual_dates == dates:
                outcome = 'full'
            elif got['state'] == 'abstain':
                outcome = 'abstain'
            elif actual & wanted or actual_dates & dates:
                outcome = 'partial'
            else:
                outcome = 'nonabstain_mismatch'
            outcomes[outcome] += 1
    return dict(selected=len(rows), clear=len(clear), ambiguous=len(ambiguous),
        status_counts={s:sum(r['status'] == s for r in rows) for s in ('valid', 'input_rejected', 'interpreter_error', 'invalid_output')},
        clear_outcomes={s:outcomes[s] for s in ('full', 'partial', 'abstain', 'nonabstain_mismatch', 'input_rejected', 'interpreter_error', 'invalid_output')},
        clear_full_rate=ratio(outcomes['full'], len(clear)), clear_abstain_rate=ratio(outcomes['abstain'], len(clear)),
        ambiguous_abstain=sum(r['status'] == 'valid' and r['actual']['state'] == 'abstain' for r in ambiguous),
        ambiguous_overreach_rate=ratio(counts['ambiguous_overreach'], len(ambiguous)),
        outstanding_reference_cases=sum(any(s == 'reported_outstanding' for _, s in r['reference']['steps']) for r in rows),
        date_reference_cases=sum(bool(r['reference']['dates']) for r in rows),
        abstention_reasons=dict(abstentions), **counts)


def report(interpreter=None):
    cases = load()  # Complete identity/reference checks before interpretation.
    call = engine.interpret if interpreter is None else interpreter
    rows = []
    for c in cases:
        row = dict(id=c['id'], group=c['group'], variant=c['variant'], reference=c['reference'],
                   status='input_rejected', actual=None, reason=None, rule_id=None)
        try:
            projection = engine.EmailMetadata(c['input'])
        except engine.EmailEvidenceError:
            rows.append(row)
            continue
        except Exception:
            row['status'] = 'interpreter_error'
            rows.append(row)
            continue
        try:
            result = call(projection)  # No ID, group or reference enters the call.
        except Exception:
            row['status'] = 'interpreter_error'
        else:
            try:
                engine.validate_result(result, projection)
                row.update(status='valid', actual=signature(result), reason=result.reason.value, rule_id=result.rule_id)
            except Exception:
                row['status'] = 'invalid_output'
        rows.append(row)
    by_group = {g:summarize([r for r in rows if r['group'] == g]) for g in GROUPS}
    return dict(contract='frozen-email-wording-evaluation-v1',
        notice='CORRELATED SYNTHETIC WORDING CHALLENGE; NOT BLIND OR REAL-WORLD ACCURACY',
        baseline_main='33c2e33ad1345483a0d09bc2a895593e88c8fe28', freeze_commit=FREEZE_COMMIT,
        fixture_lf_sha256=FIXTURE_SHA256, interpreter_lf_sha256=ENGINE_SHA256,
        interpreter_version=VERSION, rule_fingerprint=RULE_FINGERPRINT,
        metrics=summarize(rows), by_group=by_group,
        groups=dict(selected=len(by_group), both_clear_full=sum(m['clear_outcomes']['full'] == 2 for m in by_group.values()),
                    both_clear_abstain=sum(m['clear_outcomes']['abstain'] == 2 for m in by_group.values())), cases=rows)


def save(result):
    payload = canonical(result) + '\n'
    target = ROOT / LOCAL
    for p in (ROOT / '.local', target):
        parents(p)
        p.mkdir(mode=0o700, exist_ok=True)
        regular(p, True)
    run = target / uuid4().hex
    run.mkdir(mode=0o700)
    path, temporary = run / 'report.json', run / 'report.json.tmp'
    created = False
    try:
        with temporary.open('x', encoding='utf-8') as f:
            created = True
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    except BaseException:
        if created:
            try: temporary.unlink(missing_ok=True)
            except OSError: pass
        try: run.rmdir()
        except OSError: pass
        raise
    return path.relative_to(ROOT).as_posix()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Frozen synthetic email wording challenge only')
    parser.add_argument('--synthetic-only', action='store_true', required=True)
    parser.parse_args(argv)
    try:
        result = report()
        path = save(result)  # Never print success before publication.
        m, g = result['metrics'], result['groups']
        print(f"新合成措辞挑战（非盲测，非真实准确率）：{m['selected']} 条，清晰 {m['clear']}，歧义 {m['ambiguous']}\n"
              f"清晰完整/部分/abstain：{m['clear_outcomes']['full']}/{m['clear_outcomes']['partial']}/{m['clear_outcomes']['abstain']}（分母 {m['clear']}）；歧义越界：{m['ambiguous_overreach']}/{m['ambiguous']}\n"
              f"遗漏未履行步骤：{m['missed_outstanding_cases']}/{m['outstanding_reference_cases']}；无依据步骤/完成声称：{m['unsupported_step_cases']}/{m['unsupported_completion_cases']}；日期遗漏/编造/误绑定：{m['missed_date_cases']}/{m['invented_date_cases']}/{m['misbound_date_cases']}\n"
              f"拒绝/异常/无效：{m['status_counts']['input_rejected']}/{m['status_counts']['interpreter_error']}/{m['status_counts']['invalid_output']}；两改写均完整匹配组：{g['both_clear_full']}/{g['selected']}\n报告：{path}")
        return 0
    except Exception:
        print('合成措辞挑战失败；未发布成功摘要。请勿使用部分报告。')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
