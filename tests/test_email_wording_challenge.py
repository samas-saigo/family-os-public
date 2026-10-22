"""New wording challenge only; no legacy/split/Calendar case dependencies."""
import ast
import builtins
from dataclasses import replace
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import socket
import subprocess

import pytest

from experiments import email_wording_challenge as run
from family_os import _synthetic_email_evidence as e

CASES = run.load()
BY_TITLE = {c['input']['subject']:c for c in CASES}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kw):pytest.fail('No network, subprocess or models')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)


def reference_output(p):
    """Test-only semantic oracle, not a strategy or the measured interpreter."""
    ref = BY_TITLE[p.fields['subject']]['reference']
    abstain = ref['state'] == 'abstain'
    return e.Evidence(e.State(ref['state']),
        tuple(e.StepEvidence(e.Action(a),e.Status(s)) for a,s in ref['steps']),
        tuple(e.DateEvidence(e.DateRole(r),d,e.Action(a) if a else None) for r,d,a in ref['dates']),
        e.Reason.UNSUPPORTED if abstain else e.Reason.SUPPORTED,
        'abstain-v1' if abstain else 'bill-ready',
        ('subject',) if abstain else ('subject','notice_kind'),p.fingerprint)


def test_frozen_identities_references_and_complete_denominators():
    assert run.FREEZE_COMMIT == '80741385760c87d6c7b0dc1f0d514d8b1be96051'
    assert len(CASES)==36 and len({c['id'] for c in CASES})==36
    assert sha256((run.ROOT/run.FIXTURE).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==run.FIXTURE_SHA256
    assert sha256((run.ROOT/run.ENGINE).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==run.ENGINE_SHA256
    r=run.report();m=r['metrics']
    assert (m['selected'],m['clear'],m['ambiguous'])==(36,24,12)
    assert m['clear_outcomes']==dict(full=0,partial=0,abstain=24,nonabstain_mismatch=0,input_rejected=0,interpreter_error=0,invalid_output=0)
    assert m['ambiguous_abstain']==12 and m['ambiguous_overreach']==0
    assert m['outstanding_reference_cases']==m['missed_outstanding_cases']==m['missed_outstanding_steps']==12
    assert m['date_reference_cases']==m['missed_date_cases']==m['missed_dates']==16
    assert m['unsupported_steps']==m['unsupported_completion_steps']==m['invented_dates']==m['misbound_dates']==m['false_clearance_proxy_cases']==0
    assert m['status_counts']==dict(valid=36,input_rejected=0,interpreter_error=0,invalid_output=0)
    assert r['groups']==dict(selected=12,both_clear_full=0,both_clear_abstain=12)
    assert len(r['by_group'])==12 and all((x['selected'],x['clear'],x['ambiguous'])==(3,2,1) for x in r['by_group'].values())
    assert sum(x['clear_outcomes']['abstain'] for x in r['by_group'].values())==24
    assert all(c['reference']['state']!='abstain' for c in CASES if c['variant']!='ambiguous')
    assert r==run.report()
    empty=run.summarize([])
    assert empty['clear_full_rate'] is empty['clear_abstain_rate'] is empty['ambiguous_overreach_rate'] is None


def test_reference_output_is_only_a_metric_control_not_experimental_result():
    m=run.report(reference_output)['metrics']
    assert m['clear_outcomes']['full']==24 and m['clear_full_rate']==1
    assert m['ambiguous_abstain']==12
    assert all(m[k]==0 for k in run.COUNTERS)


def test_gold_ids_group_and_variant_never_enter_interpreter():
    seen=[]
    def spy(p):
        assert type(p) is e.EmailMetadata
        assert set(p.fields)=={'schema','synthetic_only','provider','record_type','notice_kind','subject'}
        assert not set(p.fields)&{'id','group','reference','variant'}
        seen.append(p.fingerprint)
        return e.interpret(p)
    run.report(spy)
    assert len(seen)==36 and len(set(seen))==36


@pytest.mark.parametrize('fault',('rejected','exception','invalid','projection_exception'))
def test_failures_keep_all_denominators_and_never_count_as_abstain(monkeypatch,fault):
    def rejected(*args):raise e.EmailEvidenceError()
    def failure(*args):raise RuntimeError('private driver detail')
    if fault=='rejected':monkeypatch.setattr(e,'EmailMetadata',rejected)
    if fault=='projection_exception':monkeypatch.setattr(e,'EmailMetadata',failure)
    r=run.report((lambda p:object()) if fault=='invalid' else failure)
    m=r['metrics'];status={'rejected':'input_rejected','invalid':'invalid_output'}.get(fault,'interpreter_error')
    assert m['status_counts'][status]==36 and m['clear_outcomes'][status]==24
    assert (m['selected'],m['clear'],m['ambiguous'])==(36,24,12)
    assert m['clear_outcomes']['abstain']==m['ambiguous_abstain']==m['clear_outcomes']['full']==0
    assert m['missed_outstanding_cases']==12 and m['missed_date_cases']==16
    assert m['false_clearance_proxy_cases']==0 and 'private' not in run.canonical(r)
    assert r['groups']['both_clear_full']==r['groups']['both_clear_abstain']==0


def test_partial_completion_does_not_erase_other_outstanding_step():
    def wrong(p):
        result=reference_output(p)
        if BY_TITLE[p.fields['subject']]['group']=='payment_plus_form' and result.state is not e.State.ABSTAIN:
            return replace(result,state=e.State.COMPLETION,steps=(result.steps[0],))
        return result
    m=run.report(wrong)['metrics']
    assert m['clear_outcomes']['full']==22 and m['clear_outcomes']['partial']==2
    assert m['missed_outstanding_cases']==m['missed_outstanding_steps']==2
    assert m['false_clearance_proxy_cases']==2 and m['unsupported_completion_cases']==0


@pytest.mark.parametrize('status',('reported_outstanding','reported_completed','reported_failed','reported_cancelled'))
def test_unsupported_steps_and_completions_are_measured(status):
    def wrong(p):
        result=reference_output(p)
        if BY_TITLE[p.fields['subject']]['group']=='bill_notice' and result.state is not e.State.ABSTAIN:
            state={'reported_outstanding':e.State.OUTSTANDING,'reported_completed':e.State.COMPLETION}.get(status,e.State.INFORMATION)
            return replace(result,state=state,steps=(e.StepEvidence(e.Action.FORM,e.Status(status)),))
        return result
    m=run.report(wrong)['metrics']
    assert m['unsupported_step_cases']==m['unsupported_steps']==2
    assert m['unsupported_outstanding_cases']==(2 if status=='reported_outstanding' else 0)
    assert m['unsupported_completion_cases']==(2 if status=='reported_completed' else 0)
    assert m['clear_outcomes']['nonabstain_mismatch']==2 and m['clear_outcomes']['partial']==0


@pytest.mark.parametrize('state',(e.State.INFORMATION,e.State.OUTSTANDING,e.State.COMPLETION,e.State.PROMOTION))
def test_ambiguous_concrete_output_overreach_even_without_steps(state):
    def wrong(p):
        result=reference_output(p)
        if result.state is e.State.ABSTAIN:
            steps=() if state in (e.State.INFORMATION,e.State.PROMOTION) else (e.StepEvidence(e.Action.PAYMENT,e.Status.COMPLETED if state is e.State.COMPLETION else e.Status.OUTSTANDING),)
            return replace(result,state=state,steps=steps,reason=e.Reason.SUPPORTED,rule_id='bill-ready',evidence_refs=('subject','notice_kind'))
        return result
    m=run.report(wrong)['metrics']
    assert m['ambiguous_overreach']==12 and m['ambiguous_overreach_rate']==1
    assert m['ambiguous_abstain']==0 and m['clear_outcomes']['full']==24


@pytest.mark.parametrize('fault',('omit','invent','role','scope'))
def test_dates_are_exact_values_roles_and_scopes(fault):
    def wrong(p):
        result=reference_output(p)
        group=BY_TITLE[p.fields['subject']]['group']
        target='visit_notice' if fault=='role' else 'payment_due'
        if group==target and result.state is not e.State.ABSTAIN:
            if fault=='omit':return replace(result,dates=())
            if fault=='invent':return replace(result,dates=(replace(result.dates[0],value='2030-11-23'),))
            if fault=='role':return replace(result,dates=(replace(result.dates[0],role=e.DateRole.AVAILABLE),))
            return replace(result,steps=(e.StepEvidence(e.Action.RENEW,e.Status.OUTSTANDING),),dates=(replace(result.dates[0],action=e.Action.RENEW),))
        return result
    m=run.report(wrong)['metrics']
    assert m['missed_date_cases']==m['missed_dates']==2
    assert m['invented_date_cases']==(2 if fault=='invent' else 0)
    assert m['misbound_date_cases']==(2 if fault in ('role','scope') else 0)
    assert m['status_counts']['invalid_output']==0 and m['clear_outcomes']['full']==22


def test_safe_abstention_is_never_false_clearance():
    r=run.report();assert r['metrics']['false_clearance_proxy_cases']==0
    assert r['metrics']['missed_outstanding_cases']==12


def test_structurally_forged_or_wrong_provenance_output_is_invalid():
    def wrong(p):
        result=reference_output(p)
        object.__setattr__(result,'input_fingerprint','0'*64)
        return result
    m=run.report(wrong)['metrics']
    assert m['status_counts']['invalid_output']==36 and m['clear_outcomes']['full']==0
    assert m['missed_outstanding_cases']==12 and m['unsupported_steps']==0


def clone(tmp_path,monkeypatch):
    for relative in (run.FIXTURE,run.ENGINE):
        p=tmp_path/relative;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes((run.ROOT/relative).read_bytes())
    monkeypatch.setattr(run,'ROOT',tmp_path)
    monkeypatch.setattr(e,'__file__',str(tmp_path/run.ENGINE))
    return tmp_path/run.FIXTURE


@pytest.mark.parametrize('target',('fixture','engine','version','rules','module_path'))
def test_changed_frozen_identity_fails_before_interpretation(tmp_path,monkeypatch,target):
    path=clone(tmp_path,monkeypatch)
    if target=='fixture':path.write_bytes(path.read_bytes()+b' ')
    elif target=='engine':(tmp_path/run.ENGINE).write_bytes(b'changed interpreter')
    elif target=='version':monkeypatch.setattr(e,'VERSION','unapproved')
    elif target=='rules':monkeypatch.setattr(e,'RULE_FINGERPRINT','0'*64)
    else:monkeypatch.setattr(e,'__file__',str(tmp_path/'other.py'))
    with pytest.raises(run.ChallengeError):run.report(lambda p:pytest.fail('Executed before identity check'))


@pytest.mark.parametrize('damage',('extra_field','duplicate_id','label','invalid_input','missing_case','extra_json_key'))
def test_fixture_content_changes_fail_closed(tmp_path,monkeypatch,damage):
    path=clone(tmp_path,monkeypatch);data=json.loads(path.read_text())
    if damage=='extra_field':data['cases'][0]['extra']='not allowed'
    elif damage=='duplicate_id':data['cases'][1]['id']=data['cases'][0]['id']
    elif damage=='label':data['cases'][0]['reference']['state']='abstain'
    elif damage=='invalid_input':data['cases'][0]['input']['body']='not allowed'
    elif damage=='missing_case':data['cases'].pop()
    raw=json.dumps(data).encode() if damage!='extra_json_key' else b'{"schema":1,"schema":2}'
    path.write_bytes(raw)
    with pytest.raises(run.ChallengeError):run.load()


def test_duplicate_json_keys_are_rejected():
    with pytest.raises(run.ChallengeError):run.unique([('same',1),('same',2)])


@pytest.mark.parametrize('damage',('symlink','hardlink','oversize','reparse','directory'))
def test_input_file_boundary(tmp_path,monkeypatch,damage):
    path=clone(tmp_path,monkeypatch);other=tmp_path/'other.json';other.write_text('{}')
    if damage=='symlink':path.unlink();path.symlink_to(other)
    elif damage=='hardlink':path.unlink();os.link(other,path)
    elif damage=='oversize':path.write_bytes(b' '*(run.FILE_BYTES+1))
    elif damage=='directory':path.unlink();path.mkdir()
    else:
        original=Path.lstat
        def reparsed(p):
            s=original(p)
            if p==path:
                class Reparse:st_mode=s.st_mode;st_file_attributes=0x400
                return Reparse()
            return s
        monkeypatch.setattr(Path,'lstat',reparsed)
    with pytest.raises(run.ChallengeError):run.load()


def test_windows_crlf_preserves_both_frozen_identities(tmp_path,monkeypatch):
    clone(tmp_path,monkeypatch)
    for relative in (run.FIXTURE,run.ENGINE):
        p=tmp_path/relative;p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
    assert len(run.load())==36


@pytest.mark.parametrize('path',('fixtures/action-evaluation-v1/holdout.json','fixtures/action-evaluation-v1/development.json','fixtures/metadata-reasoning.synthetic.json','fixtures/synthetic-email-evidence-v1.json','../outside.json'))
def test_disallowed_paths_rejected_before_open(path,monkeypatch):
    monkeypatch.setattr(os,'open',lambda *a,**kw:pytest.fail('Forbidden file open'))
    with pytest.raises(run.ChallengeError):run.read_pinned(Path(path))


def test_cli_call_chain_only_reads_new_fixture_and_fixed_engine(monkeypatch,capsys):
    inputs={os.path.abspath(run.ROOT/p) for p in (run.FIXTURE,run.ENGINE)};seen=set()
    def guard(original):
        def checked(path,*args,**kw):
            if not isinstance(path,int):
                name=os.path.abspath(os.fspath(path))
                if name in inputs:seen.add(name)
                else:
                    assert args and args[0]=='x','Forbidden data read'
                    rel=Path(name).relative_to(run.ROOT/run.LOCAL)
                    assert len(rel.parts)==2 and rel.name=='report.json.tmp'
                    assert len(rel.parts[0])==32 and set(rel.parts[0])<=set('0123456789abcdef')
            return original(path,*args,**kw)
        return checked
    for obj,key in ((builtins,'open'),(io,'open'),(os,'open')):monkeypatch.setattr(obj,key,guard(getattr(obj,key)))
    assert run.main(['--synthetic-only'])==0 and seen==inputs
    text=capsys.readouterr().out
    assert '36 条，清晰 24，歧义 12' in text and '非盲测' in text and '0/0/24' in text
    assert 'invoice' not in text.casefold() and len(text.splitlines())==5
    for relative in ('fixtures/action-evaluation-v1/holdout.json','fixtures/synthetic-email-evidence-v1.json'):
        with pytest.raises(AssertionError):(run.ROOT/relative).open()


def test_evaluator_dependencies_have_no_old_loader_or_model_imports():
    source=Path(run.__file__).read_text(encoding='utf-8');tree=ast.parse(source)
    modules={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    modules|={alias.name for n in ast.walk(tree) if isinstance(n,ast.Import) for alias in n.names}
    assert modules<={'argparse','collections','hashlib','json','os','pathlib','stat','sys','uuid','family_os'}
    assert all(n.module!='experiments' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom))
    assert 'action_evaluation' not in source
    assert {a.name for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module=='family_os' for a in n.names}=={'_synthetic_email_evidence'}


def test_report_has_only_minimized_fixed_evidence():
    r=run.report();raw=run.canonical(r)
    assert all(c['input']['subject'] not in raw for c in CASES)
    def inspect(v):
        if isinstance(v,dict):
            assert not set(v)&{'input','subject','sender','body','url','input_fingerprint','fields','output'}
            for x in v.values():inspect(x)
        elif isinstance(v,list):
            for x in v:inspect(x)
    inspect(r)


def test_atomic_publish_closes_complete_file_and_repeated_runs_never_overwrite(tmp_path,monkeypatch):
    monkeypatch.setattr(run,'ROOT',tmp_path)
    real_open=Path.open;real_replace=os.replace;writers=[];published=[]
    def opening(path,*args,**kw):
        f=real_open(path,*args,**kw)
        if path.name=='report.json.tmp':writers.append(f)
        return f
    def replacing(source,destination):
        assert writers[-1].closed and source.parent==destination.parent
        assert not destination.exists() and source.name=='report.json.tmp'
        assert json.loads(source.read_text())=={'fixed':'synthetic'}
        published.append(destination)
        real_replace(source,destination)
    monkeypatch.setattr(Path,'open',opening);monkeypatch.setattr(os,'replace',replacing)
    a=tmp_path/run.save({'fixed':'synthetic'});prior=a.read_bytes()
    b=tmp_path/run.save({'fixed':'synthetic'})
    assert a!=b and a.read_bytes()==prior==b.read_bytes()
    assert published==[a,b] and not list((tmp_path/run.LOCAL).rglob('*.tmp'))


@pytest.mark.parametrize('fault',('write','flush','fsync','close','replace','interrupt'))
def test_partial_write_or_publish_failure_cleans_only_current_output(tmp_path,monkeypatch,fault):
    monkeypatch.setattr(run,'ROOT',tmp_path)
    old=tmp_path/run.save({'old':'synthetic'});original=old.read_bytes();real_open=Path.open
    class BrokenWriter:
        def __init__(self,f):self.f=f
        def __enter__(self):return self
        def __exit__(self,*args):
            self.f.close()
            if fault=='close' and not args[0]:raise OSError('private close detail')
        def write(self,s):
            self.f.write(s[:8])
            if fault=='interrupt':raise KeyboardInterrupt()
            if fault=='write':raise OSError('private source detail')
            self.f.write(s[8:])
        def flush(self):
            if fault=='flush':raise OSError('private source detail')
            self.f.flush()
        def fileno(self):return self.f.fileno()
    def opening(path,*args,**kw):
        f=real_open(path,*args,**kw)
        return BrokenWriter(f) if path.name=='report.json.tmp' else f
    def failed(*args):raise OSError('private source detail')
    monkeypatch.setattr(Path,'open',opening)
    if fault=='fsync':monkeypatch.setattr(os,'fsync',failed)
    if fault=='replace':monkeypatch.setattr(os,'replace',failed)
    with pytest.raises(KeyboardInterrupt if fault=='interrupt' else OSError):run.save({'new':'synthetic'})
    assert old.read_bytes()==original and list((tmp_path/run.LOCAL).iterdir())==[old.parent]


def test_serialization_failure_leaves_no_partial_directory(tmp_path,monkeypatch):
    monkeypatch.setattr(run,'ROOT',tmp_path)
    with pytest.raises(TypeError):run.save({'bad':object()})
    assert not (tmp_path/'.local').exists()


def test_cli_mid_write_failure_has_no_success_or_content_leak(tmp_path,monkeypatch,capsys):
    clone(tmp_path,monkeypatch);original=Path.open
    class Broken:
        def __init__(self,f):self.f=f
        def __enter__(self):return self
        def __exit__(self,*args):self.f.close()
        def write(self,s):
            self.f.write(s[:10]);raise OSError('secret title or credentials')
    def opening(path,*args,**kw):
        f=original(path,*args,**kw)
        return Broken(f) if path.name=='report.json.tmp' else f
    monkeypatch.setattr(Path,'open',opening)
    assert run.main(['--synthetic-only'])==1
    text=capsys.readouterr().out
    assert '失败' in text and 'secret' not in text and '报告：' not in text and '0/0/24' not in text
    assert not list((tmp_path/run.LOCAL).iterdir())


def test_identity_error_never_saves_report(tmp_path,monkeypatch,capsys):
    path=clone(tmp_path,monkeypatch);path.write_bytes(b'corrupt')
    monkeypatch.setattr(run,'save',lambda result:pytest.fail('No partial report'))
    assert run.main(['--synthetic-only'])==1 and '失败' in capsys.readouterr().out


@pytest.mark.parametrize('args',([],['--synthetic-only','--path','other'],['--synthetic-only','--dataset','holdout'],['--synthetic-only','--model','anything']))
def test_opt_in_and_no_arbitrary_inputs_or_models(args,monkeypatch):
    monkeypatch.setattr(run,'report',lambda:pytest.fail('No data read without opt in'))
    with pytest.raises(SystemExit):run.main(args)


def test_report_parent_symlink_cannot_escape(tmp_path,monkeypatch):
    monkeypatch.setattr(run,'ROOT',tmp_path)
    other=tmp_path/'outside';other.mkdir();(tmp_path/'.local').symlink_to(other,target_is_directory=True)
    with pytest.raises(run.ChallengeError):run.save({'fixed':'synthetic'})
    assert not list(other.iterdir())


@pytest.mark.parametrize('relative',(run.ENGINE,run.FIXTURE))
def test_both_real_fixed_files_pass_native_read_checks(relative):
    raw=run.read_pinned(relative)
    assert raw and len(raw)<=run.FILE_BYTES


@pytest.mark.parametrize('relative',(run.ENGINE,run.FIXTURE))
def test_replacement_before_open_is_rejected_even_with_identical_bytes(tmp_path,monkeypatch,relative):
    clone(tmp_path,monkeypatch);path=tmp_path/relative;original=os.open
    replacement=path.with_name('replacement.tmp');replacement.write_bytes(path.read_bytes())
    def opening(name,*args,**kw):
        if Path(name)==path:
            path.unlink();replacement.replace(path)
        return original(name,*args,**kw)
    monkeypatch.setattr(os,'open',opening)
    with pytest.raises(run.ChallengeError):run.read_pinned(relative)


@pytest.mark.parametrize('relative',(run.ENGINE,run.FIXTURE))
def test_changes_during_read_are_rejected_even_when_hash_matches(tmp_path,monkeypatch,relative):
    clone(tmp_path,monkeypatch);path=tmp_path/relative;before=path.stat();original=os.fdopen
    class ChangedDuringRead:
        def __init__(self,stream):self.stream=stream
        def __enter__(self):return self
        def __exit__(self,*args):self.stream.close()
        def fileno(self):return self.stream.fileno()
        def read(self,*args):
            value=self.stream.read(*args)
            os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns+1_000_000_000))
            return value
    monkeypatch.setattr(os,'fdopen',lambda *args,**kw:ChangedDuringRead(original(*args,**kw)))
    with pytest.raises(run.ChallengeError):run.read_pinned(relative)


def changed_stat(s,**changes):
    from types import SimpleNamespace
    fields={k:getattr(s,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')}
    return SimpleNamespace(**(fields|changes))


@pytest.mark.parametrize('relative',(run.ENGINE,run.FIXTURE))
@pytest.mark.parametrize('windows',(True,False))
def test_confirmed_ctime_cross_api_difference_is_platform_scoped(monkeypatch,relative,windows):
    monkeypatch.setattr(run,'WINDOWS',windows)
    original=os.fstat
    monkeypatch.setattr(os,'fstat',lambda fd:changed_stat(original(fd),st_ctime_ns=original(fd).st_ctime_ns+1_000_000))
    if windows:
        assert run.read_pinned(relative)
    else:
        with pytest.raises(run.ChallengeError):run.read_pinned(relative)


@pytest.mark.parametrize('field',('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns'))
def test_windows_still_rejects_every_other_cross_api_mismatch(monkeypatch,field):
    monkeypatch.setattr(run,'WINDOWS',True);original=os.fstat
    def different(fd):
        s=original(fd)
        return changed_stat(s,**{field:getattr(s,field)+1})
    monkeypatch.setattr(os,'fstat',different)
    with pytest.raises(run.ChallengeError):run.read_pinned(run.FIXTURE)


@pytest.mark.parametrize('api',('path','handle'))
def test_windows_ctime_changes_within_same_api_are_never_ignored(monkeypatch,api):
    monkeypatch.setattr(run,'WINDOWS',True)
    calls=0
    if api=='path':
        original=run.regular
        def querying(path,directory=False):
            nonlocal calls
            s=original(path,directory)
            if path==run.ROOT/run.FIXTURE:
                calls+=1
                if calls==2:return changed_stat(s,st_ctime_ns=s.st_ctime_ns+1)
            return s
        monkeypatch.setattr(run,'regular',querying)
    else:
        original=os.fstat
        def querying(fd):
            nonlocal calls
            s=original(fd);calls+=1
            return changed_stat(s,st_ctime_ns=s.st_ctime_ns+calls)
        monkeypatch.setattr(os,'fstat',querying)
    with pytest.raises(run.ChallengeError):run.read_pinned(run.FIXTURE)
    assert calls==2


@pytest.mark.skipif(os.name!='nt',reason='Native Windows FILETIME semantics; run on Windows Python 3.12 CI')
@pytest.mark.parametrize('relative',(run.ENGINE,run.FIXTURE))
def test_native_windows_distinct_birth_and_change_times_pass_real_reads(tmp_path,monkeypatch,relative):
    import ctypes
    from ctypes import wintypes
    import msvcrt
    clone(tmp_path,monkeypatch);path=tmp_path/relative
    # Force the observed native API distinction instead of relying on coincident
    # checkout timestamps or using CRLF conversion as a Windows surrogate.
    ticks=(11_644_473_600+1_546_300_800)*10_000_000  # 2019-01-01, synthetic copy metadata only.
    birth=wintypes.FILETIME(ticks&0xffffffff,ticks>>32)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    set_time=kernel.SetFileTime
    set_time.argtypes=(wintypes.HANDLE,ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME))
    set_time.restype=wintypes.BOOL
    fd=os.open(path,os.O_RDWR|os.O_BINARY)
    try:
        assert set_time(msvcrt.get_osfhandle(fd),ctypes.byref(birth),None,None), 'Synthetic file birthtime setup failed'
    finally:os.close(fd)
    from experiments import diagnose_wording_stats as diag
    monkeypatch.setattr(diag,'ROOT',tmp_path)
    result=diag.inspect(relative.as_posix(),dict(diag.FILES)[relative.as_posix()])
    assert result['different_fields']==['st_ctime_ns']
    assert result['path_stable'] and result['handle_stable'] and result['lf_hash_matches']
    assert run.read_pinned(relative)
    print('Native Windows distinct birth/ChangeTime verified:',relative.as_posix())
