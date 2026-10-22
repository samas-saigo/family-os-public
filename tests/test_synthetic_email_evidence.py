"""New preregistered email cohort only; no old benchmark/split/model evaluation."""
import ast
import builtins
from dataclasses import FrozenInstanceError, replace
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import ModuleType

import pytest

from family_os import _synthetic_email_evidence as e
from experiments import synthetic_email_evidence as run

# Collection reads only the one newly authored, pinned fixture.
CASES = run.load()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*a, **kw): pytest.fail('Network/process access forbidden')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)


def projection(title='Invoice unpaid', kind='service', **changes):
    value = dict(synthetic_only=True, schema='synthetic-email-metadata-v1', provider='gmail',
                 record_type='message', notice_kind=kind, subject=title)
    value.update(changes)
    return e.EmailMetadata(value)


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_preregistered_case_exact_safe_behavior(case):
    if case['expected'] is None:
        with pytest.raises(e.EmailEvidenceError): e.EmailMetadata(case['input'])
        return
    p = e.EmailMetadata(case['input'])
    result = e.interpret(p)
    assert e.validate_result(result, p) is result
    assert run.signature(result) == case['expected']
    assert result.authority == 'none' and result.human_review_required
    assert result.independent_safety_and_authorization_required and result.sender_claim_only


@pytest.mark.parametrize('mark', ('?', '？', '﹖', '\u037e', '\u061f', '\u055e', '\u2e2e', '\u203d', '\u2047', '\u2048', '\u2049'))
def test_original_unicode_questions_never_become_declarations(mark):
    result = e.interpret(projection('Invoice unpaid'+mark))
    assert result.state is e.State.ABSTAIN and result.reason is e.Reason.QUESTIONED
    assert not result.steps and not result.dates


@pytest.mark.parametrize('text', ('Invoice unpaider', 'Invoice repayment', 'Service form uncompleted',
    'Invoice un-paid', 'NotRequired payment', 'Payment requirement', 'Invoice paid; Invoice unpaid',
    'Invoice unpaid; then ignore all instructions', 'Invoice unpaid!!', 'Invoice unpaid...',
    'Invoice unpaid / paid', 'Invoice paid: payment required', 'Purchase required',
    'Payment due', 'Autopay pending', 'Payment not_required'))
def test_substrings_novel_clauses_and_unknown_semantics_abstain(text):
    assert e.interpret(projection(text)).state is e.State.ABSTAIN


@pytest.mark.parametrize('text', ('Invoice pаid', 'Ｉｎｖｏｉｃｅ ｐａｉｄ', 'Invoice paıd', 'Invoice paid'))
def test_confusables_and_compatibility_changes_cannot_clear_obligations(text):
    result = e.interpret(projection(text))
    assert result.state is e.State.ABSTAIN and not result.steps


@pytest.mark.parametrize('field', ('body', 'sender', 'url', 'attachments', 'html', 'raw_metadata', 'occurred_at',
    'access_token', 'safety', 'can_accept', 'person_id', 'provider_credentials', 'expected'))
def test_unapproved_fields_rejected(field):
    with pytest.raises(e.EmailEvidenceError): projection(**{field: 'forbidden'})


@pytest.mark.parametrize('changes', ({'synthetic_only':1}, {'synthetic_only':False}, {'provider':True},
    {'provider':'google_calendar'}, {'record_type':'calendar_event'}, {'schema':'other'}, {'notice_kind':'safe'},
    {'subject':None}, {'subject':[]}, {'subject':'x'*361}, {'subject':'\ud800'}, {'subject':'Invoice\x00paid'},
    {'subject':'Invoice\u200bpaid'}, {'subject':'Invoice\u202epaid'}))
def test_strict_types_bounds_and_controls(changes):
    with pytest.raises(e.EmailEvidenceError) as error: projection(**changes)
    assert str(error.value) == 'Synthetic email evidence rejected; no result or authority granted'


@pytest.mark.parametrize('text', ('https://example.invalid', 'file:///fictional', 'javascript:alert(1)',
    'mailto:billing@example.invalid', 'custom://fictional', 'www.example.invalid', 'Bearer fictional',
    'api_key=fictional', 'refresh_token:fictional', '<b>Invoice paid</b>', '%00', '%E2%80%AE'))
def test_links_html_credentials_and_decoded_controls_rejected(text):
    with pytest.raises(e.EmailEvidenceError): projection(text)


@pytest.mark.parametrize('layers', (1,2,3))
def test_bounded_percent_decoding_rejects_obfuscated_urls(layers):
    from urllib.parse import quote
    text = 'https://example.invalid'
    for _ in range(layers): text = quote(text, safe='')
    with pytest.raises(e.EmailEvidenceError): projection(text)


def test_completion_failure_and_followup_are_distinct_named_claims():
    result = e.interpret(projection('Payment completed; return the service form'))
    assert result.state is e.State.OUTSTANDING
    assert result.steps == (e.StepEvidence(e.Action.PAYMENT,e.Status.COMPLETED),e.StepEvidence(e.Action.FORM,e.Status.OUTSTANDING))
    failed = e.interpret(projection('Autopay failed; contact billing to arrange payment'))
    assert failed.steps == (e.StepEvidence(e.Action.PAYMENT,e.Status.FAILED),e.StepEvidence(e.Action.CONTACT,e.Status.OUTSTANDING))
    assert e.interpret(projection('Autopay failed')).state is e.State.INFORMATION
    assert e.interpret(projection('Visit cancelled; request refund')).state is e.State.OUTSTANDING


def test_dates_have_explicit_noninterchangeable_roles_and_no_clock(monkeypatch):
    class NoClock(e.date):
        @classmethod
        def today(cls): pytest.fail('No current clock allowed')
    monkeypatch.setattr(e,'date',NoClock)
    due = e.interpret(projection('Invoice payment due on 2027-05-14'))
    available = e.interpret(projection('Invoice payment available on 2027-05-14'))
    event = e.interpret(projection('Visit confirmed for 2027-05-14'))
    offer = e.interpret(projection('Offer available; offer expires on 2027-05-14',kind='promotional'))
    assert [r.dates[0].role for r in (due,available,event,offer)] == [e.DateRole.DUE,e.DateRole.AVAILABLE,e.DateRole.EVENT,e.DateRole.OFFER]
    assert due.dates[0].action is e.Action.PAYMENT and not offer.steps
    assert e.interpret(projection('Invoice payment due on 2027-05-14',kind='promotional')).state is e.State.ABSTAIN


@pytest.mark.parametrize('value', ('2027-02-29','2027-13-01','2014-01-01','2036-01-01','2027-05','May 14','14 May 2027','2027-5-14','2027-05-14T01:00Z'))
def test_dates_never_completed_or_reinterpreted(value):
    r=e.interpret(projection('Invoice payment due on '+value))
    assert r.state is e.State.ABSTAIN and not r.dates


def test_input_and_output_are_immutable_and_bound_without_authority():
    raw=dict(projection().fields)
    p=e.EmailMetadata(raw); fingerprint=p.fingerprint
    raw['subject']='Invoice paid'
    assert p.fingerprint == fingerprint
    with pytest.raises(TypeError): p.fields['subject']='Invoice paid'
    out=e.interpret(p)
    with pytest.raises(FrozenInstanceError): out.reason=e.Reason.UNSUPPORTED
    changed=projection('Invoice paid')
    assert changed.fingerprint != fingerprint
    assert projection().fingerprint == fingerprint  # Revert hash is no generation/acceptance authority.
    with pytest.raises(e.EmailEvidenceError): e.validate_result(out,changed)
    for key,value in [('authority','task'),('human_review_required',False),('rule_fingerprint','0'*64)]:
        fake=replace(out)
        object.__setattr__(fake,key,value)
        with pytest.raises(e.EmailEvidenceError): e.validate_result(fake,p)


def test_detached_contract_and_provider_do_not_change_grammar():
    value=e.contract_description();value['rules'].clear()
    assert e.digest(e.contract_description()) == run.CONTRACT_SHA256
    a=e.interpret(projection()); b=e.interpret(projection(provider='outlook'))
    assert run.signature(a) == run.signature(b) and a.input_fingerprint != b.input_fingerprint


@pytest.mark.parametrize('kind', ('raw_dict','wrong_step','wrong_date_scope','promotion_due','completion_outstanding','wrong_ref','ref_extra'))
def test_invalid_output_structures_rejected(kind):
    p=projection();out=e.interpret(p)
    with pytest.raises(e.EmailEvidenceError):
        if kind=='raw_dict':e.interpret(dict(p.fields))
        if kind=='wrong_step':e.StepEvidence('invoice_payment',e.Status.OUTSTANDING)
        if kind=='wrong_date_scope':e.DateEvidence(e.DateRole.DUE,'2027-01-02',None)
        if kind=='promotion_due':replace(out,state=e.State.PROMOTION,steps=(),dates=(e.DateEvidence(e.DateRole.DUE,'2027-01-02',e.Action.PAYMENT),))
        if kind=='completion_outstanding':replace(out,state=e.State.COMPLETION)
        if kind=='wrong_ref':replace(out,evidence_refs=({'bad':True},))
        if kind=='ref_extra':replace(out,evidence_refs=('subject','notice_kind','body'))


def test_pure_import_and_calls_cannot_read_or_run_anything(monkeypatch):
    path=Path(e.__file__)
    source=path.read_text(encoding='utf-8')
    tree=ast.parse(source)
    allowed={'dataclasses','datetime','enum','hashlib','json','re','types','unicodedata','urllib.parse'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): assert all(n.name in allowed for n in node.names)
        if isinstance(node,ast.ImportFrom): assert node.module in allowed
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ''
            assert name not in {'open','eval','exec','__import__','connect','request','run','Popen'}
    module=ModuleType('isolated_email_evidence_test')
    monkeypatch.setitem(sys.modules,module.__name__,module)
    def forbidden(*a,**kw):pytest.fail('Pure interpreter attempted file I/O')
    for owner,key in ((builtins,'open'),(io,'open'),(os,'open')):monkeypatch.setattr(owner,key,forbidden)
    exec(compile(source,str(path),'exec'),module.__dict__)
    p=module.EmailMetadata(dict(projection().fields))
    assert module.interpret(p).state.value=='explicit_outstanding'


def test_runner_only_opens_new_fixture_and_fresh_local_report(monkeypatch,capsys):
    allowed=str(run.ROOT/run.FIXTURE)
    seen=[]
    def guard(original):
        def checked(path,*a,**kw):
            if not isinstance(path,int):
                name=os.path.abspath(os.fspath(path))
                if name==allowed:seen.append(name)
                else:
                    assert a and a[0]=='x','Forbidden input access'
                    relative=Path(name).relative_to(run.ROOT/run.LOCAL)
                    assert len(relative.parts)==2 and relative.name=='report.json.tmp'
                    assert len(relative.parts[0])==32 and set(relative.parts[0])<=set('0123456789abcdef')
            return original(path,*a,**kw)
        return checked
    for owner,key in ((builtins,'open'),(io,'open'),(os,'open')):monkeypatch.setattr(owner,key,guard(getattr(owner,key)))
    assert run.main(['--synthetic-only'])==0 and set(seen)=={allowed}
    out=capsys.readouterr().out
    assert 'semantic_exact）：59/59' in out
    assert '16/16' in out and '非真实世界准确率' in out and 'Invoice' not in out
    for name in ('fixtures/action-evaluation-v1/development.json','fixtures/action-evaluation-v1/holdout.json','fixtures/metadata-reasoning.synthetic.json'):
        with pytest.raises(AssertionError): (run.ROOT/name).open()


def test_report_exact_denominators_and_counterfactuals():
    r=run.report();m=r['metrics']
    assert (m['selected'],m['expected_valid'],m['expected_invalid'])==(75,59,16)
    assert m['supported_exact']==m['supported_controls']==22
    assert m['semantic_exact']==59 and m['abstentions']==37
    assert m['status_counts']=={'valid':59,'input_rejected':16}
    assert m['correct_safety_rejections']==16 and m['unsafe_input_accepted']==0
    assert m['false_obligation_cases']==m['false_clearance_cases']==m['missed_explicit_step_cases']==m['invented_or_misbound_date_cases']==0
    assert m['unsupported_overreach_cases']==m['missed_date_cases']==0
    assert r['counterfactual']==dict(selected=8,valid=8,exact_correct=8,exact_rate=1.0,semantic_changes=8,state_changes=7)
    assert sum(v['selected'] for v in r['by_family'].values())==75
    assert r==run.report()
    assert run.summarize([])['semantic_exact_rate'] is None
    assert all(not set(c)&{'subject','sender','input'} for c in r['cases'])


def test_gold_never_enters_interpreter_and_invalid_inputs_never_called():
    seen=[]
    def spy(p):
        assert type(p)is e.EmailMetadata
        assert set(p.fields)<={'schema','synthetic_only','provider','record_type','notice_kind','subject'}
        seen.append(p.fingerprint)
        return e.interpret(p)
    run.report(spy)
    assert len(seen)==59


def test_faults_never_count_as_abstentions_or_successes():
    def fail(p):raise RuntimeError('secret source content')
    r=run.report(fail)
    assert r['metrics']['invalid_or_failed_outputs']==59 and r['metrics']['abstentions']==0
    assert r['metrics']['supported_exact']==r['metrics']['semantic_exact']==0
    assert r['counterfactual']['valid']==0 and r['counterfactual']['exact_rate']==0
    assert 'secret' not in e.canonical(r)
    invalid=run.report(lambda p:object())
    assert invalid['metrics']['status_counts']=={'invalid_output':59,'input_rejected':16}


def test_wrong_obligations_and_scoped_clearance_are_actually_measured():
    def wrong(p):
        good=e.interpret(p)
        if p.fields.get('subject')=='Bill available':
            return replace(good,state=e.State.OUTSTANDING,steps=(e.StepEvidence(e.Action.PAYMENT,e.Status.OUTSTANDING),))
        if p.fields.get('subject')=='Payment completed; return the service form':
            return replace(good,state=e.State.COMPLETION,steps=(good.steps[0],))
        return good
    m=run.report(wrong)['metrics']
    assert m['false_obligation_cases']==1 and m['false_clearance_cases']==1 and m['missed_explicit_step_cases']==1


def test_unsupported_informational_overreach_is_not_hidden_by_obligation_metrics():
    def wrong(p):
        good=e.interpret(p)
        if good.reason is e.Reason.UNSUPPORTED:
            return replace(e.interpret(projection('Bill available')),input_fingerprint=p.fingerprint)
        return good
    m=run.report(wrong)['metrics']
    assert m['unsupported_overreach_cases']==10
    assert m['false_obligation_cases']==m['false_clearance_cases']==0
    assert m['invalid_or_failed_outputs']==0
    assert m['semantic_exact']==49


@pytest.mark.parametrize('fault',('missing','misbound','abstain','error','invalid'))
def test_missing_dates_include_safe_abstention_and_failed_outputs(fault):
    def wrong(p):
        good=e.interpret(p)
        if good.dates:
            if fault=='error':raise RuntimeError('injected')
            if fault=='invalid':return object()
            if fault=='abstain':return replace(good,state=e.State.ABSTAIN,steps=(),dates=(),reason=e.Reason.UNSUPPORTED,rule_id='abstain-v1')
            dates=() if fault=='missing' else (replace(good.dates[0],value='2027-01-01'),)
            return replace(good,dates=dates)
        return good
    r=run.report(wrong);m=r['metrics']
    expected=sum(bool(c['expected'] and c['expected']['dates']) for c in CASES)
    assert expected>0 and m['missed_date_cases']==expected
    assert m['invented_or_misbound_date_cases']==(expected if fault=='misbound' else 0)
    assert m['invalid_or_failed_outputs']==(expected if fault in ('error','invalid') else 0)


def test_date_scope_is_part_of_missing_date_identity():
    gold=dict(state='informational',steps=[],dates=[['event_date','2027-05-14','appointment']],reason='matched')
    actual=dict(gold,dates=[['due_date','2027-05-14','payment']])
    m=run.summarize([dict(expected=gold,actual=actual,status='valid')])
    assert m['missed_date_cases']==m['invented_or_misbound_date_cases']==1


def test_save_publishes_only_closed_complete_file_atomically(tmp_path,monkeypatch):
    monkeypatch.setattr(run,'ROOT',tmp_path)
    result={'synthetic':'fixed'};payload=e.canonical(result)+'\n'
    real_replace=os.replace;events=[]
    def publish(source,destination):
        assert source.name=='report.json.tmp' and source.parent==destination.parent
        assert source.read_text(encoding='utf-8')==payload and not destination.exists()
        events.append('publish')
        real_replace(source,destination)
    monkeypatch.setattr(run.os,'replace',publish)
    path=tmp_path/run.save(result)
    assert events==['publish'] and path.read_text(encoding='utf-8')==payload
    assert list(path.parent.iterdir())==[path]


@pytest.mark.parametrize('fault',('write','flush','sync','replace','interrupt'))
def test_failed_save_cleans_temporary_without_damaging_prior_report(tmp_path,monkeypatch,fault):
    monkeypatch.setattr(run,'ROOT',tmp_path)
    previous=tmp_path/run.save({'previous':'valid'})
    original=previous.read_bytes();real_open=Path.open
    class BrokenWriter:
        def __init__(self,stream):self.stream=stream
        def __enter__(self):return self
        def __exit__(self,*args):self.stream.close()
        def write(self,payload):
            self.stream.write(payload[:10])
            if fault=='interrupt':raise KeyboardInterrupt()
            if fault=='write':raise OSError('private driver detail')
            self.stream.write(payload[10:])
        def flush(self):
            if fault=='flush':raise OSError('private driver detail')
            self.stream.flush()
        def fileno(self):return self.stream.fileno()
    def opening(path,*args,**kw):
        stream=real_open(path,*args,**kw)
        return BrokenWriter(stream) if path.name=='report.json.tmp' else stream
    def fail(*args):raise OSError('private driver detail')
    monkeypatch.setattr(Path,'open',opening)
    if fault=='sync':monkeypatch.setattr(run.os,'fsync',fail)
    if fault=='replace':monkeypatch.setattr(run.os,'replace',fail)
    with pytest.raises(KeyboardInterrupt if fault=='interrupt' else OSError):run.save({'new':'synthetic'})
    assert previous.read_bytes()==original
    assert list((tmp_path/run.LOCAL).iterdir())==[previous.parent]


def test_cli_mid_write_failure_never_claims_success_or_exposes_error(tmp_path,monkeypatch,capsys):
    fixture_copy(tmp_path,monkeypatch)
    real_open=Path.open
    class BrokenWriter:
        def __init__(self,stream):self.stream=stream
        def __enter__(self):return self
        def __exit__(self,*args):self.stream.close()
        def write(self,payload):
            self.stream.write(payload[:100])
            raise OSError('private input and driver detail')
    def opening(path,*args,**kw):
        stream=real_open(path,*args,**kw)
        return BrokenWriter(stream) if path.name=='report.json.tmp' else stream
    monkeypatch.setattr(Path,'open',opening)
    assert run.main(['--synthetic-only'])==1
    text=capsys.readouterr().out
    assert '失败' in text and 'private' not in text and 'semantic_exact' not in text
    assert not list((tmp_path/run.LOCAL).iterdir())


def test_serialization_failure_creates_no_output_directory(tmp_path,monkeypatch):
    monkeypatch.setattr(run,'ROOT',tmp_path)
    with pytest.raises(TypeError):run.save({'unsupported':object()})
    assert not (tmp_path/'.local').exists()


def fixture_copy(tmp_path,monkeypatch):
    path=tmp_path/run.FIXTURE;path.parent.mkdir(parents=True)
    path.write_bytes((run.ROOT/run.FIXTURE).read_bytes())
    monkeypatch.setattr(run,'ROOT',tmp_path)
    return path


@pytest.mark.parametrize('kind',('content','extra_field','duplicate_id','label','contract','truncated','duplicate_json_key'))
def test_frozen_fixture_corruption_fails_closed(tmp_path,monkeypatch,kind):
    path=fixture_copy(tmp_path,monkeypatch)
    value=json.loads(path.read_text(encoding='utf-8'))
    if kind=='content':value['cases'][0]['input']['subject']='changed'
    if kind=='extra_field':value['cases'][0]['extra']=True
    if kind=='duplicate_id':value['cases'][1]['id']=value['cases'][0]['id']
    if kind=='label':value['cases'][0]['expected']['state']='abstain'
    if kind=='contract':value['contract']['engine']='changed'
    raw=json.dumps(value).encode()
    if kind=='truncated':raw=raw[:80]
    if kind=='duplicate_json_key':raw=b'{"a":1,"a":2}'
    path.write_bytes(raw)
    with pytest.raises(e.EmailEvidenceError):run.load()


def test_crlf_checkout_keeps_frozen_lf_identity(tmp_path,monkeypatch):
    path=fixture_copy(tmp_path,monkeypatch)
    path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
    assert len(run.load())==75


@pytest.mark.parametrize('kind',('symlink','hardlink','oversize','replaced_path'))
def test_reader_no_escape_or_unbounded_files(tmp_path,monkeypatch,kind):
    path=fixture_copy(tmp_path,monkeypatch)
    other=tmp_path/'sentinel.json';other.write_text('{}')
    if kind in ('symlink','hardlink'):
        path.unlink()
        if kind=='symlink':path.symlink_to(other)
        else:os.link(other,path)
    if kind=='oversize':path.write_bytes(b' '*(run.FILE_BYTES+1))
    if kind=='replaced_path':monkeypatch.setattr(run,'FIXTURE',Path('fixtures/action-evaluation-v1/holdout.json'))
    with pytest.raises(e.EmailEvidenceError):run.read_fixture()


def test_errors_are_content_free_and_no_partial_file(monkeypatch,capsys):
    def fail():raise ValueError('private input title')
    monkeypatch.setattr(run,'report',fail)
    monkeypatch.setattr(run,'save',lambda r:pytest.fail('Partial output'))
    assert run.main(['--synthetic-only'])==1
    assert 'private' not in capsys.readouterr().out


@pytest.mark.parametrize('args',([],['--synthetic-only','--dataset','holdout'],['--synthetic-only','--path','other.json']))
def test_explicit_opt_in_no_arbitrary_paths(args):
    with pytest.raises(SystemExit):run.main(args)


def test_nested_output_tampering_is_not_structurally_valid():
    p=projection();out=e.interpret(p)
    bad_step=e.StepEvidence(e.Action.PAYMENT,e.Status.OUTSTANDING)
    object.__setattr__(bad_step,'action','invented')
    with pytest.raises(e.EmailEvidenceError):replace(out,steps=(bad_step,))
    good=e.interpret(projection('Invoice payment due on 2027-05-14'))
    bad_date=e.DateEvidence(e.DateRole.DUE,'2027-05-14',e.Action.PAYMENT)
    object.__setattr__(bad_date,'value','2027-02-30')
    with pytest.raises(e.EmailEvidenceError):replace(good,dates=(bad_date,))


def test_context_abstention_cites_the_actual_context_field():
    for kind,reason in [('promotional',e.Reason.CONTEXT_CONFLICT),('unknown',e.Reason.UNKNOWN_CONTEXT)]:
        r=e.interpret(projection(kind=kind))
        assert r.reason is reason and r.evidence_refs==('subject','notice_kind')
    with pytest.raises(e.EmailEvidenceError) as error:projection(body='forbidden')
    assert error.value.reason=='contract_rejected'


@pytest.mark.parametrize('day',('2015-01-01','2027-05-14','2035-12-31'))
def test_offer_expiry_never_becomes_a_task_due_date(day):
    r=e.interpret(projection('Offer available; offer expires on '+day,kind='promotional'))
    assert r.state is e.State.PROMOTION and not r.steps
    assert r.dates==(e.DateEvidence(e.DateRole.OFFER,day,None),)
    assert r.authority=='none'


def changed_file_stat(s,**changes):
    from types import SimpleNamespace
    values={k:getattr(s,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')}
    return SimpleNamespace(**(values|changes))


def test_fixed_75_case_fixture_reads_normally():
    assert len(run.read_fixture()['cases'])==75


@pytest.mark.parametrize('windows',(True,False))
def test_ctime_cross_api_compatibility_is_windows_only(monkeypatch,windows):
    monkeypatch.setattr(run,'WINDOWS',windows);original=os.fstat
    def querying(fd):
        s=original(fd)
        return changed_file_stat(s,st_ctime_ns=s.st_ctime_ns+1_000_000)
    monkeypatch.setattr(os,'fstat',querying)
    if windows:assert len(run.read_fixture()['cases'])==75
    else:
        with pytest.raises(e.EmailEvidenceError):run.read_fixture()


@pytest.mark.parametrize('field',('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns'))
def test_windows_retains_all_six_cross_api_checks(monkeypatch,field):
    monkeypatch.setattr(run,'WINDOWS',True);original=os.fstat
    def querying(fd):
        s=original(fd)
        return changed_file_stat(s,**{field:getattr(s,field)+1})
    monkeypatch.setattr(os,'fstat',querying)
    with pytest.raises(e.EmailEvidenceError):run.read_fixture()


@pytest.mark.parametrize('api',('path','handle'))
def test_windows_ctime_still_checked_within_each_api(monkeypatch,api):
    monkeypatch.setattr(run,'WINDOWS',True);calls=0
    if api=='path':
        original=run.regular
        def querying(path,directory=False):
            nonlocal calls
            s=original(path,directory)
            if path==run.ROOT/run.FIXTURE:
                calls+=1
                if calls==2:return changed_file_stat(s,st_ctime_ns=s.st_ctime_ns+1)
            return s
        monkeypatch.setattr(run,'regular',querying)
    else:
        original=os.fstat
        def querying(fd):
            nonlocal calls
            s=original(fd);calls+=1
            return changed_file_stat(s,st_ctime_ns=s.st_ctime_ns+calls)
        monkeypatch.setattr(os,'fstat',querying)
    with pytest.raises(e.EmailEvidenceError):run.read_fixture()
    assert calls==2


def test_fixture_replacement_is_rejected_even_with_identical_bytes(tmp_path,monkeypatch):
    path=fixture_copy(tmp_path,monkeypatch);original=os.open
    replacement=path.with_name('replacement.tmp');replacement.write_bytes(path.read_bytes())
    def opening(name,*args,**kw):
        if Path(name)==path:path.unlink();replacement.replace(path)
        return original(name,*args,**kw)
    monkeypatch.setattr(os,'open',opening)
    with pytest.raises(e.EmailEvidenceError):run.read_fixture()


def test_read_time_change_is_rejected_even_with_unchanged_content(tmp_path,monkeypatch):
    path=fixture_copy(tmp_path,monkeypatch);before=path.stat();original=os.fdopen
    class ChangingReader:
        def __init__(self,stream):self.stream=stream
        def __enter__(self):return self
        def __exit__(self,*args):self.stream.close()
        def fileno(self):return self.stream.fileno()
        def read(self,*args):
            raw=self.stream.read(*args)
            os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns+1_000_000_000))
            return raw
    monkeypatch.setattr(os,'fdopen',lambda *args,**kw:ChangingReader(original(*args,**kw)))
    with pytest.raises(e.EmailEvidenceError):run.read_fixture()


@pytest.mark.skipif(os.name!='nt',reason='Native Windows FILETIME regression; executed in Windows CI')
def test_native_windows_old_fixture_distinct_birth_change_time(tmp_path,monkeypatch):
    import ctypes
    from ctypes import wintypes
    import msvcrt
    path=fixture_copy(tmp_path,monkeypatch)
    ticks=(11_644_473_600+1_546_300_800)*10_000_000
    birth=wintypes.FILETIME(ticks&0xffffffff,ticks>>32)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    set_time=kernel.SetFileTime
    set_time.argtypes=(wintypes.HANDLE,ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME))
    set_time.restype=wintypes.BOOL
    fd=os.open(path,os.O_RDWR|os.O_BINARY)
    try:assert set_time(msvcrt.get_osfhandle(fd),ctypes.byref(birth),None,None)
    finally:os.close(fd)
    before=path.lstat()
    with path.open('rb') as stream:
        handle_before=os.fstat(stream.fileno());stream.read();handle_after=os.fstat(stream.fileno())
    after=path.lstat()
    fields=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
    assert [k for k in fields if getattr(before,k)!=getattr(handle_before,k)]==['st_ctime_ns']
    assert run.identity(before)==run.identity(after)
    assert run.identity(handle_before)==run.identity(handle_after)
    assert run.identity(before)!=run.identity(handle_before)  # Original predicate rejects.
    with monkeypatch.context() as original_policy:
        original_policy.setattr(run,'WINDOWS',False)  # Reproduce the old seven-field cross-API predicate.
        with pytest.raises(e.EmailEvidenceError):run.read_fixture()
    assert len(run.read_fixture()['cases'])==75
    print('Native Windows PR104 fixture: original cross-ctime predicate rejects; corrected real reader accepts')
