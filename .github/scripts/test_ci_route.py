import importlib.util
from pathlib import Path
import subprocess
import unittest
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('ci_route', Path(__file__).with_name('ci_route.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class RoutingTests(unittest.TestCase):
    def test_audited_offline_only(self):
        result = r.choose([('M', 'experiments/rule_ai_complementarity.py')])
        self.assertFalse(result['postgres'])
        self.assertFalse(result['windows_compat'])
        mixed = r.choose([('M', p) for p in r.OFFLINE])
        self.assertFalse(mixed['postgres'])
        self.assertTrue(mixed['windows_compat'])
        self.assertTrue(r.choose([('M', 'tests/test_rule_ai_complementarity.py')])['windows_compat'])

    def test_email_and_executable_docs_keep_compat(self):
        for path in r.EMAIL:
            with self.subTest(path=path):
                result = r.choose([('M', path)])
                self.assertFalse(result['postgres'])
                self.assertTrue(result['windows_compat'])

    def test_unknown_protected_and_mixed(self):
        for path in ['src/family_os/db.py', 'migrations/new.py', 'tests/conftest.py',
                     'requirements-dev.lock', 'pyproject.toml', '.github/workflows/tests.yml',
                     '.github/scripts/ci_route.py', 'docs/new.md', 'README.md',
                     'experiments/new.py', 'experiments/_fixed_report_io.py',
                     'experiments/configs/single-email-runtime-diagnostic-v2.json',
                     'fixtures/synthetic-email-evidence-v1.json']:
            with self.subTest(path=path):
                self.assertTrue(r.choose([('M', next(iter(r.OFFLINE))), ('M', path)])['postgres'])
                self.assertTrue(r.choose([('M', path)])['windows_compat'])

    def test_status_empty_and_explicit_full(self):
        for status in ['R100', 'C100', 'D', 'X']:
            self.assertTrue(r.choose([(status, next(iter(r.EMAIL)))])['postgres'])
        self.assertTrue(r.choose([])['postgres'])
        for event in ['push', 'workflow_dispatch', 'unknown']:
            self.assertTrue(r.route(event)['postgres'])
        self.assertTrue(r.route('pull_request', force=True)['postgres'])

    def test_collection_failure(self):
        def fail(*args):
            raise subprocess.CalledProcessError(1, 'git')
        self.assertTrue(r.route('pull_request', collect=fail)['postgres'])
        self.assertTrue(r.route('pull_request', collect=lambda *_: None)['postgres'])

    def test_diff_parser(self):
        def parse(raw):
            return r.changed_files('a' * 40, 'b' * 40,
                                   run=lambda *a, **k: SimpleNamespace(stdout=raw))
        self.assertEqual(parse(b'M\0docs/a file.md\0A\0new.py\0'),
                         [('M', 'docs/a file.md'), ('A', 'new.py')])
        for raw in [b'R100\0old\0new\0', b'M\0missing-terminator', b'M\0',
                    b'M\0../bad\0', b'M\0\xff\0']:
            with self.subTest(raw=raw), self.assertRaises((ValueError, IndexError, UnicodeError)):
                parse(raw)
        with self.assertRaises(ValueError):
            r.changed_files('main', 'b' * 40)

    def test_real_git_rename(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            def git(*args):
                return subprocess.run(['git', '-C', temp, *args], check=True,
                                      capture_output=True).stdout.decode().strip()
            git('init'); git('config', 'user.email', 'ci@example.invalid')
            git('config', 'user.name', 'CI test')
            Path(temp, 'old.py').write_text('fixed contents\n')
            git('add', '.'); git('commit', '-m', 'base'); base = git('rev-parse', 'HEAD')
            git('mv', 'old.py', 'new.py'); git('commit', '-m', 'rename'); head = git('rev-parse', 'HEAD')
            def run(args, **kwargs):
                return subprocess.run(args, cwd=temp, **kwargs)
            self.assertTrue(r.route('pull_request', base, head,
                                   collect=lambda a, b: r.changed_files(a, b, run))['postgres'])


class ResultTests(unittest.TestCase):
    def test_gate_rejects_missing_failed_cancelled_or_unexpected_skips(self):
        import copy
        result_spec = importlib.util.spec_from_file_location('ci_result', Path(__file__).with_name('ci_result.py'))
        result = importlib.util.module_from_spec(result_spec)
        result_spec.loader.exec_module(result)
        jobs = {name: {'result': 'success'} for name in
                ('selection', 'sqlite', 'postgres', 'windows-wording', 'windows-compat')}
        jobs['selection']['outputs'] = {}
        self.assertTrue(result.report(jobs)[1])
        for job in jobs:
            for state in ('failure', 'cancelled', 'skipped'):
                changed = copy.deepcopy(jobs)
                changed[job]['result'] = state
                self.assertFalse(result.report(changed)[1], (job, state))
        jobs['selection']['outputs'] = {'postgres': 'false', 'windows_compat': 'false'}
        jobs['postgres']['result'] = jobs['windows-compat']['result'] = 'skipped'
        summary, valid = result.report(jobs)
        self.assertTrue(valid)
        self.assertIn('NOT RUN by audited rule (not a test pass)', summary)
        jobs['postgres']['result'] = 'success'
        self.assertFalse(result.report(jobs)[1])


if __name__ == '__main__':
    unittest.main()
