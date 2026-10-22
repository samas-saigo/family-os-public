"""One invocation and report readback for the reviewed Windows workflow.

No inference policy changes: delegate exactly once to the unchanged diagnostic.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys


def version():
    return sys.version_info[:3]


def read_published(runtime, relative):
    if type(relative) is not str or not re.fullmatch(r'\.local/single-email-runtime-diagnostic/[0-9a-f]{32}/report\.json', relative):
        raise ValueError('report_read_failed')
    path = runtime.ROOT / relative
    runtime.wording.parents(path)
    before = runtime.wording.regular(path)
    if before.st_size > 65536:
        raise ValueError('report_read_failed')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        handle = os.fstat(stream.fileno())
        if runtime.wording.cross_api_identity(handle) != runtime.wording.cross_api_identity(before):
            raise ValueError('report_read_failed')
        raw = stream.read(65537)
        if runtime.wording.identity(handle) != runtime.wording.identity(os.fstat(stream.fileno())):
            raise ValueError('report_read_failed')
    if len(raw) > 65536 or runtime.wording.identity(before) != runtime.wording.identity(runtime.wording.regular(path)):
        raise ValueError('report_read_failed')
    return runtime.parent.strict_json(raw.decode('utf-8'))


def collect():
    # Imported only after the caller's version check; the PowerShell gate checks
    # the approved checkout before invoking any Python, including version probes.
    from experiments import single_email_diagnostic as runtime
    report, path, verified, error, diagnostic_code = None, None, False, None, None
    try:
        report = runtime.run()  # Exactly once. Never invoke smoke/full or retry.
        diagnostic_code = 0 if report['run_status'] == 'complete' else 2
        path = runtime.save(report)
        try:
            loaded = read_published(runtime, path)
            if loaded != report:
                raise ValueError('report_read_failed')
            verified = True
        except (Exception, KeyboardInterrupt):
            error = 'report_read_failed'
    except (Exception, KeyboardInterrupt):
        error = 'diagnostic_or_publication_failed'
    # On a readback failure retain the already-validated in-memory diagnostic,
    # explicitly without asserting that persisted bytes have been verified.
    return dict(workflow='single-email-diagnostic-windows-v1',
                diagnostic_exit_code=diagnostic_code,
                workflow_exit_code=1 if error else diagnostic_code,
                report_path=path, report_read_verified=verified,
                report_source='published_readback' if verified else 'retained_in_memory',
                error_code=error, report=report)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Single diagnostic with full minimized report; no retry')
    parser.add_argument('--synthetic-only', action='store_true', required=True)
    parser.add_argument('mode', choices=('single',))
    parser.parse_args(argv)
    if version() != (3, 12, 10):
        value = dict(workflow='single-email-diagnostic-windows-v1', workflow_exit_code=1,
                     error_code='python_version_mismatch', diagnostic_exit_code=None,
                     report_path=None, report_read_verified=False, report=None)
    else:
        value = collect()
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
    return value['workflow_exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
