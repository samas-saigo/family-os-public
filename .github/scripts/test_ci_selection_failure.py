"""Exercise partial output publication against the workflow and result gate."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


route = load('ci_route')
result = load('ci_result')


def enabled(job, selection, cancelled=False):
    # Evaluate the actual workflow's small boolean conditions, rather than a
    # second implementation of the fallback rule. actionlint validates GHA syntax.
    workflow = (ROOT / '.github/workflows/tests.yml').read_text()
    block = re.search(rf'^  {re.escape(job)}:\n(.*?)(?=^  [\w-]+:|\Z)',
                      workflow, re.M | re.S).group(1)
    expression = re.search(r'^    if: \$\{\{ (.*?) \}\}$', block, re.M).group(1)
    expression = expression.replace('!cancelled()', repr(not cancelled))
    expression = expression.replace('needs.selection.result', repr(selection['result']))
    for flag in ('postgres', 'windows_compat'):
        expression = expression.replace('needs.selection.outputs.' + flag,
                                        repr(selection.get('outputs', {}).get(flag, '')))
    expression = expression.replace('&&', ' and ').replace('||', ' or ')
    return eval(expression, {'__builtins__': {}})


def jobs(selection, optional='success'):
    values = {name: {'result': 'success'} for name in
              ('sqlite', 'windows-wording')}
    values['selection'] = selection
    values.update({name: {'result': optional} for name in ('postgres', 'windows-compat')})
    return values


class SelectionPublicationTests(unittest.TestCase):
    def publish(self, directory, fail_summary=False):
        output = directory / 'outputs'
        summary = directory if fail_summary else directory / 'summary'
        selected = route.choose([('M', 'experiments/rule_ai_complementarity.py')])
        with patch.dict(os.environ, GITHUB_OUTPUT=str(output), GITHUB_STEP_SUMMARY=str(summary)), \
                patch.object(route, 'route', return_value=selected), \
                contextlib.redirect_stdout(io.StringIO()):
            if fail_summary:
                with self.assertRaises(OSError):
                    route.main()
            else:
                route.main()
        outputs = dict(line.split('=', 1) for line in output.read_text().splitlines())
        self.assertEqual(outputs, {'postgres': 'false', 'windows_compat': 'false'})
        return outputs

    def test_successful_publication_allows_intentional_skips(self):
        with tempfile.TemporaryDirectory() as temp:
            selection = {'result': 'success', 'outputs': self.publish(Path(temp))}
        for job in ('postgres', 'windows-compat'):
            self.assertFalse(enabled(job, selection))
        summary, valid = result.report(jobs(selection, 'skipped'))
        self.assertTrue(valid)
        self.assertIn('NOT RUN by audited rule', summary)

    def test_summary_failure_after_false_outputs_forces_full_and_failed_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            selection = {'result': 'failure',
                         'outputs': self.publish(Path(temp), fail_summary=True)}
        for job in ('postgres', 'windows-compat'):
            self.assertTrue(enabled(job, selection))
        self.assertTrue(enabled('ci-result', selection))
        for state in ('success', 'skipped'):
            summary, valid = result.report(jobs(selection, state))
            self.assertFalse(valid)  # Selection failure remains a failure even after full tests pass.
            self.assertNotIn('NOT RUN by audited rule', summary)

    def test_missing_outputs_require_full(self):
        for status in ('success', 'failure'):
            for outputs in ({}, None):
                selection = {'result': status}
                if outputs is not None:
                    selection['outputs'] = outputs
                with self.subTest(selection=selection):
                    for job in ('postgres', 'windows-compat'):
                        self.assertTrue(enabled(job, selection))
                    summary, valid = result.report(jobs(selection))
                    self.assertEqual(valid, status == 'success')
                    self.assertNotIn('NOT RUN by audited rule', summary)

    def test_cancelled_workflow_never_starts_optional_jobs_or_gate(self):
        for status in ('success', 'failure', 'cancelled'):
            for outputs in ({}, {'postgres': 'false', 'windows_compat': 'false'}):
                selection = {'result': status, 'outputs': outputs}
                with self.subTest(selection=selection):
                    for job in ('postgres', 'windows-compat', 'ci-result'):
                        self.assertFalse(enabled(job, selection, cancelled=True))
        summary, valid = result.report(jobs({'result': 'cancelled', 'outputs': outputs}, 'skipped'))
        self.assertFalse(valid)
        self.assertNotIn('NOT RUN by audited rule', summary)


if __name__ == '__main__':
    unittest.main()
