"""Offline regressions for bounded machine evidence and unchanged CI protection."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('ci_evidence', Path(__file__).with_name('ci_evidence.py'))
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)
A, B, M, T = 'a' * 40, 'b' * 40, 'c' * 40, 'd' * 40
PAIR = ('Samas Maintainer', e.EMAIL)


def xml(status='', tests=1, failures=0, errors=0, skipped=0, name='test_frozen_configuration_inputs_and_original_results'):
    return (f'<testsuites><testsuite tests="{tests}" failures="{failures}" errors="{errors}" skipped="{skipped}">'
            f'<testcase file="tests/test_email_model_evidence.py" line="87" name="{name}">{status}</testcase>'
            '</testsuite></testsuites>').encode()


class EvidenceTests(unittest.TestCase):
    def test_exact_approved_pairs_web_committer_and_no_metadata_leak(self):
        for p in (PAIR, ('samas-saigo', e.EMAIL)):
            self.assertEqual(e.identity_errors(A, p, ('GitHub', 'noreply@github.com'), 'Co-authored-by: Samas Maintainer <' + e.EMAIL + '>'), [])
        errors = e.identity_errors(A, ('private_name', 'private_mail'), ('GitHub', 'private_mail'),
                                   'Co-authored-by: private_name <private_mail>\nSecret: private_value')
        self.assertEqual(len(errors), 4)
        self.assertNotIn('private', json.dumps(errors))
        self.assertTrue(all(s == A and f in ('author', 'committer', 'trailer') for s, f, _ in errors))
        self.assertTrue(e.identity_errors(A, ('GitHub', 'noreply@github.com'), PAIR, ''))

    def test_trailer_allowlist_malformed_multiline_and_spoofing(self):
        for trailer in ('Reviewed-by: Bad <' + e.EMAIL + '>', 'Signed-off-by: Samas Maintainer <other@users.noreply.github.com>',
                        'Co-authored-by: broken', 'Private-field: private_value', 'continuation'):
            self.assertTrue(e.identity_errors(A, PAIR, PAIR, trailer))
        self.assertEqual(e.identity_errors(A, PAIR, PAIR, ''), [])

    def test_actual_git_trailer_parser_and_branch_only_commit_range(self):
        with tempfile.TemporaryDirectory() as temp:
            def git(*args, input=None):
                return subprocess.run(['git', '-C', temp, *args], input=input, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, check=True).stdout.decode()
            git('init', '-q');git('config', 'user.name', PAIR[0]);git('config', 'user.email', PAIR[1])
            git('commit', '--allow-empty', '-qm', 'base');base = git('rev-parse', 'HEAD').strip()
            git('commit', '--allow-empty', '-qm', 'change\n\nCo-authored-by: private_name <private_mail>')
            head = git('rev-parse', 'HEAD').strip()
            text, valid = e.changes(dict(base=base, source=head, comparison=f'{base}...{head}'), git)
            self.assertFalse(valid);self.assertIn(head, text);self.assertNotIn('private_', text)
            self.assertIn('New commits inspected: 1', text)

    def test_event_head_is_not_tested_merge_sha_and_checkout_mismatch(self):
        env = dict(GITHUB_SHA=M, GITHUB_REPOSITORY='owner/repo', GITHUB_RUN_ID='123',
                   GITHUB_RUN_ATTEMPT='2', GITHUB_EVENT_NAME='pull_request')
        event = {'pull_request': {'head': {'sha': B}, 'base': {'sha': A}}}
        rev = lambda *a: M if a[-1] == 'HEAD' else T
        c = e.context(env, event, rev)
        self.assertEqual((c['source'], c['base'], c['checkout'], c['tree']), (B, A, M, T))
        self.assertIn('attempts/2', c['url']);self.assertIn('separate identities', e.header(c))
        with self.assertRaises(e.Unknown):e.context(dict(env, GITHUB_SHA=B), event, rev)
        with self.assertRaises(e.Unknown):e.context(env, {}, rev)

    def test_dispatch_missing_push_range_are_not_checked(self):
        env = dict(GITHUB_SHA=M, GITHUB_REPOSITORY='owner/repo', GITHUB_RUN_ID='123',
                   GITHUB_RUN_ATTEMPT='1', GITHUB_EVENT_NAME='workflow_dispatch')
        c = e.context(env, {}, lambda *a: M if a[-1] == 'HEAD' else T)
        text, valid = e.changes(c)
        self.assertTrue(valid);self.assertIn('NOT CHECKED', text)
        env['GITHUB_EVENT_NAME'] = 'push'
        c = e.context(env, {'before': '0' * 40, 'after': M}, lambda *a: M if a[-1] == 'HEAD' else T)
        self.assertIsNone(c['comparison'])

    def test_change_list_limit_incomplete_rename_delete_and_safe_rendering(self):
        def read(value):
            def revision(*args, **kwargs):return value if args[0] == 'diff' else ''
            return revision
        c = dict(comparison=f'{A}...{B}', base=A, source=B)
        for raw in ('M\0path', 'M\0x\0' * 51, 'R100\0a\0b\0'):
            with self.assertRaises(e.Unknown):e.changes(c, read(raw))
        text, _ = e.changes(c, read('D\0old.py\0A\0evil|`<tag>\n.py\0'))
        self.assertIn('| D |', text);self.assertNotIn('<tag>', text);self.assertNotIn('evil|`', text)

    def test_junit_success_and_existing_contract_observation(self):
        text, valid = e.test_summary(xml(), 0)
        self.assertTrue(valid);self.assertIn('passed: 1', text)
        self.assertIn('existing frozen configuration/input regression: passed', text)
        self.assertIn('existing pin/namespace regression: NOT CHECKED', text)

    def test_failure_location_without_messages_parameter_values_or_xml_text(self):
        text, valid = e.test_summary(xml('<failure message="private_mail">private_model_reply</failure>', failures=1,
                                         name='test_x[private_name]'), 1)
        self.assertTrue(valid);self.assertIn('tests/test_email_model_evidence.py:88', text)
        self.assertIn('failures: 1', text);self.assertNotIn('private', text)
        self.assertFalse(e.test_summary(xml('<failure/>', failures=1), 0)[1])

    def test_only_utf8_xml_reaches_parser(self):
        for bom in (b'', b'\xef\xbb\xbf'):
            raw = bom + b'<?xml version="1.0" encoding="utf-8"?>' + xml(name='test_caf\u00e9')
            with self.subTest(bom=bom):
                text, valid = e.test_summary(raw, 0)
                self.assertTrue(valid);self.assertIn('passed: 1', text)
        for raw in (xml().replace(b'testcase', b'test\0case'),
                    xml(name='test_caf\u00e9').decode().encode('latin-1'),
                    b'<?xml version="1.0" encoding="ISO-8859-1"?>' + xml(),
                    b'<?xml version="1.0" encoding="UTF-16"?>' + xml()):
            with self.subTest(prefix=raw[:60]), patch.object(e.ET, 'fromstring') as parse:
                text, valid = e.test_summary(raw, 0)
                self.assertFalse(valid);self.assertIn('UNKNOWN', text)
                self.assertNotIn('passed:', text);parse.assert_not_called()

    def test_wide_encoded_xml_and_internal_entities_are_unknown_before_parsing(self):
        plain = xml(name='test_entity').decode()
        entity = ('<!DOCTYPE testsuites [<!ENTITY hidden "private_value">]>'
                  + plain.replace('test_entity', '&hidden;'))
        encodings = (('utf-16-le', b'\xff\xfe'), ('utf-16-be', b'\xfe\xff'),
                     ('utf-32-le', b'\xff\xfe\0\0'), ('utf-32-be', b'\0\0\xfe\xff'))
        for encoding, bom in encodings:
            for prefix in (b'', bom):
                for document in (plain, entity):
                    raw = prefix + document.encode(encoding)
                    with self.subTest(encoding=encoding, bom=bool(prefix), entity=document is entity), \
                            patch.object(e.ET, 'fromstring') as parse:
                        text, valid = e.test_summary(raw, 0)
                        self.assertFalse(valid);self.assertIn('UNKNOWN', text)
                        self.assertNotIn('passed:', text);self.assertNotIn('private_value', text)
                        parse.assert_not_called()
        for raw in (entity.encode(), b'\xef\xbb\xbf' + entity.encode(),
                    b'<!ENTITY hidden "private_value">' + xml()):
            with patch.object(e.ET, 'fromstring') as parse:
                text, valid = e.test_summary(raw, 0)
                self.assertFalse(valid);self.assertIn('UNKNOWN', text)
                self.assertNotIn('private_value', text);parse.assert_not_called()

    def test_missing_truncated_oversized_inconsistent_dtd_and_partial_are_unknown(self):
        for raw, code in ((b'', 0), (xml()[:-5], 0), (b'x' * (e.XML_LIMIT + 1), 0),
                          (xml(tests=2), 0), (xml(skipped=1), 0), (xml(), 1), (xml(), 2),
                          (b'<!DOCTYPE x [<!ENTITY leak "secret">]>' + xml(), 0)):
            text, valid = e.test_summary(raw, code)
            self.assertFalse(valid);self.assertIn('UNKNOWN', text);self.assertNotIn('passed:', text)
        text, valid = e.test_summary(xml('<skipped/>', skipped=1), 0)
        self.assertTrue(valid);self.assertIn('skipped: 1', text)

    def test_existing_large_parameter_ids_fit_bounded_xml_without_being_published(self):
        # The existing 8328-item collection alone has ~18.8MB of testcase metadata.
        raw = xml(name='test_value[' + 'private_value' * 800000 + ']')
        self.assertGreater(len(raw), 8 * 1024 * 1024)
        self.assertLess(len(raw), e.XML_LIMIT)
        text, valid = e.test_summary(raw, 0)
        self.assertTrue(valid);self.assertIn('passed: 1', text);self.assertNotIn('private_value', text)

    def test_wrapper_runs_pytest_once_and_preserves_failure_on_missing_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            event, summary = Path(temp) / 'event.json', Path(temp) / 'summary'
            event.write_text('{}')
            env = dict(GITHUB_EVENT_PATH=str(event), GITHUB_STEP_SUMMARY=str(summary), RUNNER_TEMP=temp)
            c = dict(source=B, base=A, checkout=M, tree=T, run='123', attempt='1', url='https://github.com/o/r/actions/runs/123/attempts/1')
            for code in (0, 1, 2, 5):
                with patch.dict(os.environ, env), patch.object(e, 'context', return_value=c), \
                        patch.object(e.subprocess, 'run', return_value=subprocess.CompletedProcess([], code)) as invoke, \
                        contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(e.main(['pytest', '-q']), code or 1)
                    self.assertEqual(invoke.call_count, 1)
                    self.assertEqual(invoke.call_args.args[0][:3], [e.sys.executable, '-m', 'pytest'])
            self.assertIn('UNKNOWN', summary.read_text())

    def test_temp_creation_and_interrupt_failures_are_finite_unknown(self):
        c = dict(source=B, base=A, checkout=M, tree=T, run='1', attempt='1', url='https://github.com/o/r')
        with patch.object(e.tempfile, 'TemporaryDirectory', side_effect=OSError('private_value')), \
                patch.object(e, 'bounded', return_value=b'{}'), patch.object(e, 'context', return_value=c), \
                patch.object(e, 'publish') as publish, patch.object(e.subprocess, 'run') as invoke, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(e.main(['pytest', '-q']), 1)
            invoke.assert_not_called()
            self.assertIn('UNKNOWN', publish.call_args.args[0]);self.assertNotIn('private', out.getvalue())
        with patch.object(e, 'bounded', return_value=b'{}'), patch.object(e, 'context', return_value=c), \
                patch.object(e, 'publish') as publish, patch.object(e.subprocess, 'run', side_effect=KeyboardInterrupt()), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(e.main(['pytest', '-q']), 130)
            self.assertIn('UNKNOWN', publish.call_args.args[0])

    def test_summary_publication_failure_never_turns_tests_green(self):
        with patch.object(e, 'bounded', side_effect=OSError('private_name')), \
                patch.object(e, 'publish', side_effect=OSError('private_mail')), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(e.main(['checkout']), 1)
        self.assertNotIn('private', out.getvalue());self.assertIn('UNKNOWN', out.getvalue())
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, GITHUB_STEP_SUMMARY=str(Path(temp)/'s')):
            with self.assertRaises(e.Unknown):e.publish('x' * (e.LIMIT + 1))

    def test_identity_evidence_failure_after_false_route_outputs_still_falls_back(self):
        path = Path(__file__).with_name('test_ci_selection_failure.py')
        spec = importlib.util.spec_from_file_location('existing_failure_contract', path)
        contract = importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, GITHUB_STEP_SUMMARY=str(Path(temp)/'s')), \
                patch.object(e, 'bounded', return_value=b'{}'), \
                patch.object(e, 'context', return_value=dict(source=B, base=A, checkout=M, tree=T, run='1', attempt='1', url='https://github.com/o/r')), \
                patch.object(e, 'changes', return_value=('Finite identity violation\n', False)), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(e.main(['inspect']), 1)
        selection = dict(result='failure', outputs=dict(postgres='false', windows_compat='false'))
        for job in ('postgres', 'windows-compat'):
            self.assertTrue(contract.enabled(job, selection))
            self.assertFalse(contract.enabled(job, selection, cancelled=True))
        _, valid = contract.result.report(contract.jobs(selection))
        self.assertFalse(valid)

    def test_workflow_keeps_required_gate_and_fail_closed_conditions(self):
        text = Path(__file__).parents[1].joinpath('workflows/tests.yml').read_text()
        self.assertEqual(text.count('python .github/scripts/ci_evidence.py pytest'), 3)  # shared Windows anchor
        self.assertNotIn('continue-on-error', text);self.assertNotIn('upload-artifact', text)
        self.assertIn('needs: [selection, sqlite, postgres, windows-wording, windows-compat]', text)
        self.assertIn('run: python .github/scripts/ci_result.py', text)
        self.assertIn('needs.selection.result != \'success\' || needs.selection.outputs.postgres != \'false\'', text)
        self.assertIn('needs.selection.result != \'success\' || needs.selection.outputs.windows_compat != \'false\'', text)


if __name__ == '__main__':
    unittest.main()
