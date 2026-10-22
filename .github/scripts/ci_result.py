"""Report intentional skips separately and enforce every selected check."""
import json
import os


def report(jobs):
    selection = jobs['selection']
    outputs = selection.get('outputs', {}) if selection['result'] == 'success' else {}
    required = {'selection', 'sqlite', 'windows-wording'}
    omitted = set()
    for job, flag in [('postgres', 'postgres'), ('windows-compat', 'windows_compat')]:
        (omitted if outputs.get(flag) == 'false' else required).add(job)
    rows = ['## CI execution results', '', '| Check | Outcome |', '| --- | --- |']
    for job in jobs:
        actual = jobs[job]['result']
        outcome = 'NOT RUN by audited rule (not a test pass)' if job in omitted and actual == 'skipped' else actual
        rows.append(f'| {job} | {outcome} |')
    valid = (all(jobs[j]['result'] == 'success' for j in required)
             and all(jobs[j]['result'] == 'skipped' for j in omitted))
    return '\n'.join(rows) + '\n', valid


def main():
    summary, valid = report(json.loads(os.environ['RESULTS']))
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
        stream.write(summary)
    if not valid:
        raise SystemExit('Selected check failed, cancelled, missing, or unexpected skip state')


if __name__ == '__main__':
    main()
