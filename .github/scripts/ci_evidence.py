"""Bounded local CI evidence. No API, model, workspace upload or raw error text."""
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

LIMIT = 32768
SHA = re.compile(r'[0-9a-f]{40}')
EMAIL = '337128921+samas-saigo@users.noreply.github.com'
IDENTITIES = {('Samas Maintainer', EMAIL), ('samas-saigo', EMAIL)}
TRAILERS = {'co-authored-by', 'signed-off-by', 'reviewed-by', 'acked-by', 'tested-by'}
CONTRACTS = {
    ('tests/test_email_model_evidence.py', 'test_frozen_configuration_inputs_and_original_results'): 'existing frozen configuration/input regression',
    ('tests/test_email_semantic_prompt.py', 'test_freeze_reuse_and_frozen_namespace_isolation'): 'existing pin/namespace regression',
}


class Unknown(Exception):
    pass


def require(value):
    if not value:
        raise Unknown()


def git(*args, input=None):
    # Never print command stderr, commit metadata/messages or exception details.
    p = subprocess.run(['git', *args], input=input, stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL, timeout=30, check=True)
    require(len(p.stdout) <= 1024 * 1024)
    return p.stdout.decode('utf-8', errors='strict')


def bounded(path, limit):
    with Path(path).open('rb') as stream:
        value = stream.read(limit + 1)
    require(len(value) <= limit)
    return value


def safe(value):
    return html.escape(json.dumps(value, ensure_ascii=True), quote=True).replace('`', '&#96;').replace('|', '&#124;')


def publish(text):
    require(len(text.encode('utf-8')) <= LIMIT)
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
        stream.write(text)
    print('CI evidence written to Step Summary; no raw metadata or test output copied.')


def context(env, event, revision=git):
    head = revision('rev-parse', 'HEAD').strip()
    tree = revision('rev-parse', 'HEAD^{tree}').strip()
    require(SHA.fullmatch(head) and SHA.fullmatch(tree))
    require(head == env['GITHUB_SHA'])
    repo, run, attempt = env['GITHUB_REPOSITORY'], env['GITHUB_RUN_ID'], env['GITHUB_RUN_ATTEMPT']
    require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo))
    require(re.fullmatch('[0-9]+', run) and re.fullmatch('[0-9]+', attempt))
    kind = env['GITHUB_EVENT_NAME']
    if kind == 'pull_request':
        pr = event.get('pull_request', {})
        base, source = pr.get('base', {}).get('sha', ''), pr.get('head', {}).get('sha', '')
        require(SHA.fullmatch(base) and SHA.fullmatch(source))
        comparison = f'{base}...{source}'
    elif kind == 'push':
        base, source = event['before'], event['after']
        require(SHA.fullmatch(base) and SHA.fullmatch(source) and source == head)
        comparison = f'{base}..{source}' if base != '0' * 40 else None
    else:
        base, source, comparison = None, None, None
    job = env.get('GITHUB_JOB', 'UNKNOWN')
    require(job in ('selection', 'sqlite', 'postgres', 'windows-wording', 'windows-compat', 'ci-result', 'UNKNOWN'))
    url = f'https://github.com/{repo}/actions/runs/{run}/attempts/{attempt}'
    return dict(checkout=head, tree=tree, base=base, source=source, comparison=comparison,
                url=url, repo=repo, run=run, attempt=attempt, job=job)


def header(c):
    return ('## Review evidence (local machine sources)\n\n'
            f'Job: {c.get("job", "UNKNOWN")}\n\n'
            f'PR/event head: {c["source"] or "NOT CHECKED (no event head)"}\n\n'
            f'PR/event base: {c["base"] or "NOT CHECKED (no event base)"}\n\n'
            f'Actual checkout SHA: {c["checkout"]}; tree: {c["tree"]}\n\n'
            'PR head and checkout are separate identities; tests belong to the actual checkout above. Each job records its own checkout.\n\n'
            f'Run {c["run"]}, attempt {c["attempt"]}: [detailed logs]({c["url"]}).\n\n')


def identity_errors(sha, author, committer, trailers):
    errors = []
    for field, pair in [('author', author), ('committer', committer)]:
        allowed = pair in IDENTITIES or field == 'committer' and pair == ('GitHub', 'noreply@github.com')
        if not allowed:
            errors.append((sha, field, 'identity_not_allowed'))
    for line in trailers.splitlines():
        key, sep, value = line.partition(':')
        if not sep or key.lower() not in TRAILERS:
            errors.append((sha, 'trailer', 'unsupported_trailer'))
            continue
        match = re.fullmatch(r' ([^<>\r\n]+) <([^<>\r\n]+)>', value)
        if not match or match.groups() not in IDENTITIES:
            errors.append((sha, 'trailer', 'identity_not_allowed'))
    return errors


def changes(c, revision=git):
    if not c['comparison']:
        return 'Changes/commit identities: NOT CHECKED (no immutable comparison range).\n', True
    fields = revision('diff', '--name-status', '-z', '--no-renames', c['comparison'], '--').split('\0')
    require(fields.pop() == '' and len(fields) % 2 == 0 and len(fields) <= 100)
    rows = []
    for status, path in zip(fields[::2], fields[1::2]):
        require(status in ('A', 'M', 'D', 'T') and 0 < len(path.encode()) <= 512)
        rows.append(f'| {status} | {safe(path)} |')
    commits = revision('rev-list', '--reverse', f'{c["base"]}..{c["source"]}').splitlines()
    require(len(commits) <= 100 and all(SHA.fullmatch(s) for s in commits))
    errors = []
    for sha in commits:
        size = revision('cat-file', '-s', sha).strip()
        require(size.isdecimal() and int(size) <= 65536)
        raw = revision('show', '-s', '--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%B', sha)
        values = raw.split('\0')
        require(len(values) == 6 and values[0] == sha)
        parsed = revision('interpret-trailers', '--parse', input=values[5].encode())
        errors.extend(identity_errors(sha, tuple(values[1:3]), tuple(values[3:5]), parsed))
    require(len(errors) <= 100)
    text = ('Changed files (complete; renames shown as delete/add):\n\n| Status | Path |\n| --- | --- |\n'
            + '\n'.join(rows) + f'\n\nNew commits inspected: {len(commits)}. Identity policy: '
            + ('FAIL\n\n' if errors else 'PASS (allowlisted metadata pairs/trailers only).\n\n'))
    if errors:
        text += '| Commit SHA | Field category | Finite error code |\n| --- | --- | --- |\n'
        text += '\n'.join(f'| {s} | {f} | {code} |' for s, f, code in errors) + '\n'
    return text, not errors


def junit(raw, exit_code):
    require(len(raw) <= 8 * 1024 * 1024 and b'<!DOCTYPE' not in raw and b'<!ENTITY' not in raw)
    root = ET.fromstring(raw)
    require(root.tag == 'testsuites' and len(root) == 1 and root[0].tag == 'testsuite')
    suite = root[0]
    counts = {}
    for key in ('tests', 'failures', 'errors', 'skipped'):
        v = suite.get(key, '')
        require(re.fullmatch('[0-9]+', v))
        counts[key] = int(v)
    cases = suite.findall('testcase')
    require(0 < len(cases) <= 20000 and counts['tests'] == len(cases))
    observed = dict(failures=0, errors=0, skipped=0)
    locations, contracts = [], {}
    for case in cases:
        states = [k for k, tag in [('failures', 'failure'), ('errors', 'error'), ('skipped', 'skipped')] if case.find(tag) is not None]
        require(len(states) <= 1)
        state = states[0] if states else 'passed'
        if states:
            observed[state] += 1
        if state in ('failures', 'errors'):
            path, line = case.get('file', ''), case.get('line', '')
            if re.fullmatch(r'tests/[A-Za-z0-9_./-]+\.py', path) and '..' not in path.split('/') and line.isdecimal():
                locations.append(f'{path}:{int(line) + 1}')
            else:
                locations.append('UNKNOWN (failure location unavailable)')
        key = (case.get('file'), case.get('name'))
        if key in CONTRACTS:
            label = CONTRACTS[key]
            require(label not in contracts)
            contracts[label] = state
    require(all(observed[k] == counts[k] for k in observed))
    passed = counts['tests'] - sum(observed.values())
    require(exit_code in (0, 1) and (exit_code != 0 or not counts['failures'] and not counts['errors']))
    require(exit_code != 1 or counts['failures'] + counts['errors'] > 0)
    return counts, passed, sorted(set(locations)), contracts


def test_summary(raw, code):
    try:
        counts, passed, locations, contracts = junit(raw, code)
        text = (f'Pytest exit: {code}; observed tests: {counts["tests"]}, passed: {passed}, '
                f'failures: {counts["failures"]}, errors: {counts["errors"]}, skipped: {counts["skipped"]}.\n\n')
        # Do not silently truncate a failure list and imply a complete diagnosis.
        require(len(locations) <= 20)
        text += 'Failure locations: ' + (', '.join(locations) if locations else 'none in this JUnit report') + '.\n\n'
        for label in CONTRACTS.values():
            text += f'{label}: {contracts.get(label, "NOT CHECKED (test not observed)")}.\n\n'
        return text, True
    except (Unknown, ET.ParseError, ValueError, TypeError):
        return f'Pytest exit: {code}; statistics/contracts: UNKNOWN (missing, partial, oversized or inconsistent JUnit). See detailed logs.\n\n', False


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    require(args and args[0] in ('inspect', 'pytest', 'checkout'))
    mode = args.pop(0)
    raw, code, launch_ok = b'', None, True
    if mode == 'pytest':
        # Exactly one invocation; stdout/stderr remain the original detailed log.
        with tempfile.TemporaryDirectory(prefix='ci-evidence-', dir=os.environ.get('RUNNER_TEMP')) as temp:
            path = Path(temp) / 'pytest.xml'
            try:
                code = subprocess.run([sys.executable, '-m', 'pytest', *args,
                                       '-o', 'junit_family=xunit1', '--junitxml=' + str(path)], check=False).returncode
                raw = bounded(path, 8 * 1024 * 1024)
            except (OSError, Unknown):
                launch_ok = False
    valid = launch_ok
    identity_header = '## Review evidence\n\n'
    try:
        event = json.loads(bounded(os.environ['GITHUB_EVENT_PATH'], 1024 * 1024))
        c = context(os.environ, event)
        identity_header = header(c)
        text = identity_header
        if mode == 'inspect':
            more, good = changes(c)
            text += more
            valid &= good
        elif mode == 'pytest':
            more, good = test_summary(raw, code)
            text += more
            valid &= good
        text += ('Semantic/privacy review, changed-test strength, model outcomes and unobserved contracts: NOT CHECKED. '
                 'Existing test observations are not independent attestation.\n')
        publish(text)
    except (Exception, KeyboardInterrupt):
        valid = False
        # No exception value/traceback, identity string, trailer or raw XML emitted.
        try:
            publish(identity_header + 'UNKNOWN (evidence acquisition/validation/publication failed); no pass inferred. See job logs.\n')
        except (Exception, KeyboardInterrupt):
            print('Review evidence UNKNOWN (publication failed).')
    # A failing pytest can never be turned green by missing/successful evidence.
    return code if code else (0 if valid else 1)


if __name__ == '__main__':
    raise SystemExit(main())
