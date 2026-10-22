"""Fail-closed CI selection. Exact paths only; no directory-level exemptions."""
import json
import os
from pathlib import Path
import re
import subprocess

# Audited at ec201687: standalone fixed synthetic email runners -> pure
# _synthetic_email_evidence; no product reverse imports or database fixtures.
# Every entry keeps SQLite full + native Windows tests. Configs/fixtures/shared
# helpers intentionally excluded. See docs/ci-cost-phase1.md for dependency audit.
EMAIL = frozenset({
    'experiments/synthetic_email_evidence.py',
    'experiments/email_wording_challenge.py',
    'experiments/email_model_evidence.py',
    'experiments/single_email_diagnostic.py',
    'experiments/single_email_compat.py',
    'experiments/email_model_compat.py',
    'tests/test_synthetic_email_evidence.py',
    'tests/test_email_wording_challenge.py',
    'tests/test_email_model_evidence.py',
    'tests/test_single_email_diagnostic.py',
    'tests/test_single_email_windows_workflow.py',
    'tests/test_single_email_compat.py',
    'tests/test_email_model_compat.py',
    'docs/single-email-runtime-diagnostic-v1.md',
    'docs/single-email-runtime-diagnostic-v2.md',
    'docs/synthetic-email-model-evidence-v2.md',
})
# Offline fixed-report analysis -> local_thinking_benchmark + _fixed_report_io;
# its own tests mock inputs and use tmp_path, never engine/DB fixtures.
OFFLINE = frozenset({
    'experiments/rule_ai_complementarity.py',
    'tests/test_rule_ai_complementarity.py',
})


def full(reason):
    return dict(postgres=True, windows_compat=True, reason=reason)


def choose(changes, event='pull_request', force=False):
    if force or event != 'pull_request':
        return full('explicit full validation or non-PR event')
    if not changes:
        return full('empty or unavailable change list')
    for status, path in changes:
        if status not in ('A', 'M'):
            return full('rename, deletion, or unsupported change status')
        if path not in EMAIL | OFFLINE:
            return full('path outside audited exact allowlist')
    compat = any(p != 'experiments/rule_ai_complementarity.py' for _, p in changes)
    reason = 'only audited standalone experiment paths; PostgreSQL duplicate omitted'
    if compat:
        reason += '; Windows 3.12.0 retained for native instructions, compatibility, or Win32 tests'
    else:
        reason += '; Windows 3.12.0 omitted for pure report-analysis module only; platform I/O helper unchanged'
    return dict(postgres=False, windows_compat=compat, reason=reason)


def changed_files(base, head, run=subprocess.run):
    if not all(re.fullmatch(r'[0-9a-f]{40}', ref or '') for ref in (base, head)):
        raise ValueError('invalid commit identity')
    # Full checkout, explicit immutable event SHAs, no API pagination/truncation.
    # -z preserves all legal filenames; rename/copy status stays visible.
    result = run(['git', 'diff', '--name-status', '-z', '--find-renames',
                  f'{base}...{head}', '--'], check=True, capture_output=True, timeout=60)
    fields = result.stdout.decode('utf-8', errors='strict').split('\0')
    if fields.pop() != '':
        raise ValueError('incomplete diff')
    changes = []
    while fields:
        status = fields.pop(0)
        if status not in ('A', 'M', 'D'):
            raise ValueError('rename/copy or unsupported diff record')
        path = fields.pop(0)
        if not path or path.startswith('/') or '..' in path.split('/'):
            raise ValueError('invalid path')
        changes.append((status, path))
    return changes


def route(event, base=None, head=None, force=False, collect=changed_files):
    if force or event != 'pull_request':
        return choose([], event, force)
    try:
        return choose(collect(base, head))
    except Exception:
        return full('change-list acquisition or classification failed; full fallback')


def main():
    selected = route(os.environ.get('GITHUB_EVENT_NAME', ''),
                     os.environ.get('PR_BASE'), os.environ.get('PR_HEAD'),
                     os.environ.get('FULL_VALIDATION') == 'true')
    output = ''.join(f'{key}={str(selected[key]).lower()}\n'
                     for key in ('postgres', 'windows_compat'))
    with Path(os.environ['GITHUB_OUTPUT']).open('a') as stream:
        stream.write(output)
    with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as stream:
        stream.write('## CI selection\n\nSQLite full and Windows 3.12.10: selected.\n\n')
        stream.write(f"PostgreSQL full: {'selected' if selected['postgres'] else 'NOT RUN by rule'}.\n\n")
        stream.write(f"Windows 3.12.0: {'selected' if selected['windows_compat'] else 'NOT RUN by rule'}.\n\n")
        stream.write(selected['reason'] + '\n\nSelection is not a test pass; see CI result for execution outcomes.\n')
    print(json.dumps(selected, sort_keys=True))


if __name__ == '__main__':
    main()
