"""New six-case structure annotation: frozen acceptance authority, Mock HTTP only."""
from copy import deepcopy
from hashlib import sha256
import itertools
import json
import os
from pathlib import Path
import re
import socket
import sys

import pytest
from experiments import email_structure_diagnostic as d
from test_email_model_evidence import mocked, envelope, output

CONFIG, WIRE, CASES = d.setup()
ALL = d.prior.setup()[2]
BY_INPUT = {d.wording.canonical(c['input']): c for c in ALL}
SERVICE = next(d.engine.EmailMetadata(c['input']) for c in CASES if c['input']['notice_kind'] == 'service')
PROMO = next(d.engine.EmailMetadata(c['input']) for c in CASES if c['input']['notice_kind'] == 'promotional')
ABSTAIN = dict(state='abstain', steps=[], dates=[])


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*a, **k): pytest.fail('Real sockets/model forbidden')
    monkeypatch.setattr(socket, 'create_connection', denied)
    monkeypatch.setattr(socket.socket, 'connect', denied)


def test_freeze_and_unchanged_wire_and_parser():
    assert d.FREEZE == '0d1a2c80c1c4e1feababca56e2697b4bfe1124a2'
    assert sha256((d.ROOT / d.CONFIG).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == d.CONFIG_SHA
    assert [c['id'] for c in CASES] == ['WC01-1','WC01-3','WC05-1','WC10-1','WC11-1','WC12-1']
    assert all(CONFIG[k] == d.prior.setup()[0][k] for k in ('model','prompt','output_schema','generation','limits'))
    assert d.Transport.request is d.compat.old.Transport.request
    for path, expected in d.SOURCE_PINS.items():
        assert sha256((d.ROOT/path).read_bytes().replace(b'\r\n',b'\n')).hexdigest() == expected


def branch_values():
    good = dict(state='explicit_outstanding',steps=[dict(action='invoice_payment',status='reported_outstanding')],dates=[])
    yield {}, 'field_set'
    yield [], 'field_set'
    yield dict(ABSTAIN, private_name='private_value'), 'field_set'
    for key in ('state','steps','dates'):
        for value in (None,True,1,{},'private_value'):
            v=deepcopy(ABSTAIN);v[key]=value
            if key == 'state' and type(value) is str: continue
            if key in ('steps','dates') and type(value) is list: continue
            yield v,'field_type'
    yield dict(good,steps=good['steps']*3),'cardinality'
    yield dict(good,dates=[{}]*2),'cardinality'
    for key, item in [('steps',{}),('steps',None),('dates',{}),('dates',None)]:
        yield dict(good,**{key:[item]}),'field_set'
    yield dict(good,steps=[dict(action='invoice_payment',status=True)]),'field_type'
    yield dict(good,dates=[dict(role='due_date',value=True,action=None)]),'field_type'
    yield dict(good,state='private_state'),'enum'
    yield dict(good,steps=[dict(action='private_action',status='reported_outstanding')]),'enum'
    yield dict(good,steps=[dict(action='invoice_payment',status='private_status')]),'enum'
    yield dict(good,dates=[dict(role='private_role',value='2028-03-01',action=None)]),'enum'
    yield dict(good,dates=[dict(role='due_date',value='2028-03-01',action='private_action')]),'enum'
    for date in ('2028-02-30','2014-01-01','2036-01-01','2028-1-01','private_date'):
        yield dict(good,dates=[dict(role='due_date',value=date,action='invoice_payment')]),'date_value'
    yield dict(good,dates=[dict(role='due_date',value='2028-03-01',action=None)]),'date_action_binding'
    yield dict(good,dates=[dict(role='event_date',value='2028-03-01',action='invoice_payment')]),'date_action_binding'
    yield dict(good,steps=good['steps']*2),'duplicate_action'
    yield dict(ABSTAIN,steps=good['steps']),'state_steps'
    yield dict(good,steps=[]),'state_steps'
    yield dict(good,state='explicit_completion'),'state_steps'
    yield dict(good,state='informational'),'state_steps'
    yield dict(good,dates=[dict(role='due_date',value='2028-03-01',action='return_form')]),'date_action_binding'
    yield dict(good,dates=[dict(role='event_date',value='2028-03-01',action=None)]),'date_state_relation'
    yield dict(ABSTAIN,state='informational',dates=[dict(role='due_date',value='2028-03-01',action='invoice_payment')]),'date_state_relation'
    yield dict(ABSTAIN,state='promotional'),'notice_kind_relation'


@pytest.mark.parametrize('value,reason',list(branch_values()))
def test_major_rejection_branches_and_exact_authority(value,reason):
    reply=envelope(value)
    old=d.compat.response_result(reply,SERVICE,CONFIG['limits'])
    new=d.response_result(reply,SERVICE,CONFIG['limits'])
    assert new.pop('structure_reason') == reason
    assert new == old and old['status'] == 'invalid_structure'


def test_differential_accept_reject_corpus_and_mutations():
    checked=0
    # Valid/invalid cross-state, step/date/null binding combinations, two notice
    # contexts and malformed JSON. Reference values are test-only, never runner data.
    steps=[[]]
    steps += [[dict(action='invoice_payment',status=s.value)] for s in d.engine.Status]
    dates=[None]+[dict(role=r.value,value=v,action=a) for r,v,a in itertools.product(d.engine.DateRole,('2015-01-01','2035-12-31','2036-01-01','2028-02-30'),(None,'invoice_payment','return_form'))]
    values=[output(c['reference']) for c in ALL]
    values += [dict(state=s.value,steps=t,dates=[] if day is None else [day]) for s,t,day in itertools.product(d.engine.State,steps,dates)]
    for projection in (SERVICE,PROMO):
        for value in values:
            raw=json.dumps(value)
            try:
                original=d.parent.parse_prediction(raw,projection).signature()
                accepted=True
            except d.Error:
                accepted=False
            old=d.compat.response_result(envelope(value),projection,CONFIG['limits'])
            new=d.response_result(envelope(value),projection,CONFIG['limits'])
            assert new.pop('structure_reason') in d.REASONS
            assert old == new
            assert (new['status']=='valid') == accepted
            if accepted: assert new['prediction']==original
            checked+=1
    assert checked > 3000
    for raw in ('prefix {}','{"state":NaN}','{"state":"abstain","state":"abstain","steps":[],"dates":[]}', '\ud800'):
        reply=envelope();reply['message']['content']=raw
        old=d.compat.response_result(reply,SERVICE,CONFIG['limits'])
        new=d.response_result(reply,SERVICE,CONFIG['limits'])
        assert new.pop('structure_reason') in ('not_applicable','content_encoding')
        assert new == old


def test_unknown_classifier_failure_cannot_change_decision(monkeypatch):
    old=d.compat.response_result(envelope({}),SERVICE,CONFIG['limits'])
    def fail(*a): raise RuntimeError('private_string')
    monkeypatch.setattr(d,'_constraint',fail)
    new=d.response_result(envelope({}),SERVICE,CONFIG['limits'])
    assert new.pop('structure_reason')=='unknown' and new==old
    accepted=d.response_result(envelope(),SERVICE,CONFIG['limits'])
    assert accepted['status']=='valid' and accepted['structure_reason']=='none'
    for invented in ('private_arbitrary_reason','none','not_applicable','not_obtained'):
        monkeypatch.setattr(d,'_constraint',lambda *a:invented)
        new=d.response_result(envelope({}),SERVICE,CONFIG['limits'])
        assert new.pop('structure_reason')=='unknown' and new==old


def test_six_wire_requests_privacy_and_no_scoring(monkeypatch):
    def deny(*a,**k): pytest.fail('Scoring or old runner execution forbidden')
    for module,name in [(d.parent,'score'),(d.parent,'compare'),(d.wording,'summarize'),(d.engine,'interpret'),(d.prior,'run')]:
        monkeypatch.setattr(module,name,deny)
    def reply(m,p,payload,value):
        if p=='/api/chat':
            return envelope(dict(ABSTAIN,private_marker='private_invalid_value'))
        return value
    http=mocked(monkeypatch,reply);r=d.run()
    assert r['run_status']=='complete' and r['attempted']==6
    assert r['status_counts']=={'invalid_structure':6}
    assert r['attributed_constraint_counts']=={'field_set':6}
    sent=[v for _,p,v,_ in http.calls if p=='/api/chat']
    assert [BY_INPUT[v['messages'][1]['content']]['id'] for v in sent]==list(d.SELECTED)
    for v in sent:
        assert v==dict(model=CONFIG['model']['tag'],messages=[dict(role='system',content=CONFIG['prompt']),v['messages'][1]],format=CONFIG['output_schema'],**CONFIG['generation'])
    text=d.wording.canonical(r)
    assert all(c['input']['subject'] not in text for c in ALL)
    for banned in ('private_marker','private_invalid_value',CONFIG['prompt'],'input_fingerprint','input_fixture_lf_sha256','model_metrics','rule_cases','reference','prediction"'):
        assert banned not in text
    assert all('prediction' not in row and 'actual' not in row for row in r['cases'])


@pytest.mark.parametrize('fault',['reply_identity','metadata','final_identity','identity_interrupt','timeout','budget','json','thinking','truncated'])
def test_boundaries_identity_latch_timeouts_failures_no_retry(monkeypatch,fault):
    count=tags=0;clock=[100.0]
    monkeypatch.setattr(d.time,'monotonic',lambda:clock[0])
    def reply(m,p,v,r):
        nonlocal count,tags
        if p=='/api/tags':
            tags+=1
            if fault=='identity_interrupt' and tags==3: raise KeyboardInterrupt()
            if fault=='metadata' and tags==3 or fault=='final_identity' and tags==8:r['models'][0]['digest']='0'*64
        if p=='/api/chat':
            count+=1
            if count==1:
                if fault=='reply_identity': r['model']='private_model'
                if fault=='timeout':clock[0]+=60.01
                if fault=='budget':clock[0]+=601
                if fault=='json':r['message']['content']='private-invalid-json'
                if fault=='thinking':r['message']['thinking']='private-thinking'
                if fault=='truncated':r['done_reason']='length'
        return r
    http=mocked(monkeypatch,reply);r=d.run()
    assert len(r['cases'])==6 and r['selected']=={'cases':6}
    if fault in ('json','truncated','final_identity'):
        assert r['attempted']==6
    else:assert r['attempted']==1
    if fault in ('reply_identity','metadata','final_identity','identity_interrupt','budget'):
        assert not r['identity_verified_at_end'] and r['observed_identity'] is None and r['attributed_constraint_counts'] is None
        assert r['prediction_attribution']=='unattributed_diagnostic'
    if fault in ('json','truncated'):
        assert r['run_status']=='complete' and r['cases'][0]['status'] in ('invalid_json','truncated')
    else:assert r['run_status']=='partial'
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==r['attempted']
    assert all(private not in d.encoded(r).decode() for private in ('private-thinking','private_model','private-invalid-json'))


def test_transport_one_chat_fixed_selection_and_no_full(monkeypatch):
    http=mocked(monkeypatch)
    c=d.Transport(CONFIG,'WC01-1',d.time.monotonic()+600)
    payload=c.payload(d.engine.EmailMetadata(CASES[0]['input']))
    c.request('POST','/api/chat',payload)
    with pytest.raises(d.Error):c.request('POST','/api/chat',payload)
    with pytest.raises(d.Error):c.payload(d.engine.EmailMetadata(ALL[1]['input']))
    with pytest.raises(d.Error):d.Transport(CONFIG,'WC02-1',d.time.monotonic()+600)
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==1


def test_cli_publication_readback_and_readonly_recovery(monkeypatch,tmp_path,capsys):
    http=mocked(monkeypatch)
    monkeypatch.setattr(d,'version',lambda:(3,12,10))
    real_save,real_read=d.save,d.read_report
    def saving(report):
        with monkeypatch.context() as m:
            m.setattr(d,'ROOT',tmp_path);return real_save(report)
    def reading(run_id,expected):
        with monkeypatch.context() as m:
            m.setattr(d,'ROOT',tmp_path);return real_read(run_id,expected)
    monkeypatch.setattr(d,'save',saving);monkeypatch.setattr(d,'read_report',reading)
    assert d.main(['--synthetic-only','diagnose'])==0
    value=json.loads(capsys.readouterr().out)
    assert value['report_read_verified'] and value['report']['selected']['cases']==6
    calls=len(http.calls)
    assert d.main(['--synthetic-only','recover',Path(value['report_path']).parent.name,value['report_sha256']])==0
    recovered=json.loads(capsys.readouterr().out)
    assert recovered['report']==value['report'] and recovered['operation']=='recover'
    assert len(http.calls)==calls
    assert d.main(['--synthetic-only','recover',Path(value['report_path']).parent.name,'0'*64])==1
    assert len(http.calls)==calls
    capsys.readouterr()


@pytest.mark.parametrize('fault',['read','replace','fsync','write'])
def test_report_failure_retains_memory_no_retry_or_old_overwrite(monkeypatch,tmp_path,capsys,fault):
    http=mocked(monkeypatch)
    monkeypatch.setattr(d,'version',lambda:(3,12,10))
    real_save=d.save;real_open=Path.open
    prior=tmp_path/'old.json';prior.write_text('prior',encoding='utf-8')
    def saving(report):
        with monkeypatch.context() as m:
            m.setattr(d,'ROOT',tmp_path)
            def fail(*a,**k):raise OSError('private fs message')
            if fault in ('replace','fsync'):m.setattr(os,fault,fail)
            if fault=='write':
                class Broken:
                    def __init__(self,f):self.f=f
                    def __enter__(self):return self
                    def __exit__(self,*a):self.f.close()
                    def write(self,data):self.f.write(data[:12]);fail()
                def opening(p,*a,**k):
                    f=real_open(p,*a,**k);return Broken(f) if p.name.endswith('.tmp') else f
                m.setattr(Path,'open',opening)
            return real_save(report)
    monkeypatch.setattr(d,'save',saving)
    def fail_read(*a,**k):raise OSError('private report')
    monkeypatch.setattr(d,'read_report',fail_read)
    assert d.main(['--synthetic-only','diagnose'])==1
    text=capsys.readouterr().out;v=json.loads(text)
    assert v['report'] and not v['report_read_verified'] and v['report_source']=='retained_in_memory'
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==6
    assert 'private fs message' not in text and 'private report' not in text
    assert prior.read_text(encoding='utf-8')=='prior' and not list(tmp_path.rglob('*.tmp'))
    assert len(list((tmp_path/d.LOCAL).glob('*'))) == (1 if fault=='read' else 0)


def test_report_unique_namespace_and_recovery_path_bounds(monkeypatch,tmp_path):
    mocked(monkeypatch);r=d.run();monkeypatch.setattr(d,'ROOT',tmp_path)
    a=tmp_path/d.save(r);old=a.read_bytes();b=tmp_path/d.save(r)
    assert a!=b and a.read_bytes()==old and b.read_bytes()==old
    digest=sha256(old).hexdigest()
    assert d.read_report(a.parent.name,digest)==r
    for invalid in ('../'+a.parent.name,'',a.as_posix(),'g'*32):
        with pytest.raises(d.Error):d.read_report(invalid,digest)
    with pytest.raises(d.Error):d.read_report(a.parent.name,'0'*64)
    a.write_bytes(old+b' ')
    with pytest.raises(d.Error):d.read_report(a.parent.name,digest)
    a.unlink()
    os.link(b,a)
    with pytest.raises(Exception):d.read_report(a.parent.name,digest)


def test_entry_rejects_wrong_python_and_unsupported_modes_without_requests(monkeypatch,capsys):
    http=mocked(monkeypatch);monkeypatch.setattr(d,'version',lambda:(3,12,0))
    assert d.main(['--synthetic-only','diagnose'])==1
    assert json.loads(capsys.readouterr().out)['error_code']=='python_version_mismatch'
    for args in (['diagnose'],['--synthetic-only','smoke'],['--synthetic-only','full'],['--synthetic-only','inventory'],['--synthetic-only','diagnose','--host','x']):
        with pytest.raises(SystemExit):d.main(args)
    assert not http.calls


def test_exact_allowed_files_no_old_experiment_execution(monkeypatch):
    allowed={str(d.ROOT/p) for p in (*d.SOURCE_PINS,d.CONFIG.as_posix(),d.parent.CONFIG.as_posix(),d.compat.old.CONFIG.as_posix(),d.compat.CONFIG.as_posix(),'experiments/email_wording_challenge.py','src/family_os/_synthetic_email_evidence.py','fixtures/synthetic-email-wording-challenge-v1.json')}
    real=os.open;seen=[]
    def opening(path,*a,**k):
        assert str(path) in allowed, 'Unexpected input file access'
        seen.append(str(path));return real(path,*a,**k)
    monkeypatch.setattr(os,'open',opening)
    for owner in (d.prior,d.parent,d.compat,d.compat.old):
        monkeypatch.setattr(owner,'run',lambda *a,**k:pytest.fail('Frozen runners must not execute'))
    mocked(monkeypatch);r=d.run()
    assert r['attempted']==6 and seen and all('holdout' not in p.lower() for p in seen)




@pytest.mark.parametrize('shell_name',['powershell','pwsh'])
@pytest.mark.parametrize('scenario',['success','partial','read_error','clipboard_error','version_bad','bad_commit','bad_tree','dirty','recover','recover_failed'])
@pytest.mark.skipif(sys.platform!='win32',reason='Native Restricted interactive stdin workflow; mocked boundaries only')
def test_native_restricted_diagnose_and_readonly_recovery(shell_name,scenario):
    import shutil
    import subprocess
    shell=shutil.which(shell_name)
    assert shell, 'Native CI must execute both PowerShell shells'
    text=(d.ROOT/'docs/synthetic-email-structure-diagnostic-v1.md').read_text(encoding='utf-8')
    block=re.search(r'```powershell\n(.*?)\n```',text,re.S).group(1)
    assert '.ps1' not in block and 'Set-ExecutionPolicy' not in block and 'Bypass' not in block
    block=block.replace('APPROVED_RUNTIME_COMMIT','a'*40).replace('APPROVED_RUNTIME_TREE','b'*40)
    mocks=r'''
    function Read-Host { param($Prompt) $global:Answers.Dequeue() }
    function Get-ExistingPython { 'fake-python' }
    function git {
        $global:LASTEXITCODE=0
        if ($args[0] -eq 'init') {
            $null=New-Item -ItemType Directory -Path $diagRoot
            $global:Owned=$diagRoot
        }
        if ($args -contains 'fetch') {$global:Fetches++}
        if ($args -contains 'rev-parse') {
            if ($args[-1] -eq 'HEAD') {
                if ($global:Scenario -eq 'bad_commit') {'0'*40} else {$diagCommit}
            } else {
                if ($global:Scenario -eq 'bad_tree') {'0'*40} else {$diagTree}
            }
        }
        if ($args -contains 'status') {
            $global:Gate=$true
            if ($global:Scenario -eq 'dirty') {' M unapproved.py'}
        }
    }
    function Invoke-ApprovedPython {
        param($Python,$Purpose)
        if (-not $global:Gate) {throw 'python_before_approval'}
        if ($Purpose -eq 'version') {
            $global:Probes++
            $v=if($global:Scenario -eq 'version_bad'){'[3,12,0]'}else{'[3,12,10]'}
            return [pscustomobject]@{Output=$v;Code=0}
        }
        if ($diagMode -eq 'recover') {
            $global:Reads++
            if ($diagRunId -cne ('e'*32) -or $diagExpectedSha -cne ('f'*64)) {throw 'wrong_recovery_identity'}
        } else {
            $global:Runs++
            if ($diagMode -cnotin @('diagnose')) {throw 'wrong_mode'}
            $global:Chosen=$diagMode
        }
        $status=if($global:Scenario -eq 'partial'){'partial'}else{'complete'}
        $code=if($global:Scenario -eq 'partial'){2}elseif($global:Scenario -in @('read_error','recover_failed')){1}else{0}
        $n=6
        $value=@{workflow_exit_code=$code;report_read_verified=($code -ne 1);report_sha256=('f'*64);report=@{run_status=$status;selected=@{cases=$n};cases=@(@{telemetry=@{load_duration=80000000000;prompt_eval_cached_count=64};subreason='prediction_structure';structure_reason='field_set';telemetry_validation=@{load_duration='validated'}});requests=@(@{phases=@{connect=@{completed=$true;elapsed_seconds=0.1}}})}} | ConvertTo-Json -Depth 15
        [pscustomobject]@{Output=$value;Code=$code}
    }
    function Set-Clipboard {
        param($Value,$ErrorAction)
        $global:Copies++
        if($global:Scenario -eq 'clipboard_error'){throw 'mock_clipboard_failure'}
        $global:Copied=$Value
    }
'''
    block=block.replace('    # MOCK_BOUNDARY: native CI substitutes only process/Git/clipboard boundaries here.',mocks)
    prelude=r'''
[Console]::InputEncoding=New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$global:Runs=0; $global:Reads=0; $global:Probes=0; $global:Copies=0; $global:Copied=''; $global:Chosen=''; $global:Gate=$false; $global:Owned=$null; $global:Fetches=0
$original=(Get-Location).Path
$encoding=$OutputEncoding.CodePage
$console=[Console]::OutputEncoding.CodePage
$preference=$ErrorActionPreference
if ($PSVersionTable.PSEdition -eq 'Desktop') {
    $security=[System.Reflection.Assembly]::Load('Microsoft.PowerShell.Security, Version=3.0.0.0, Culture=neutral, PublicKeyToken=31bf3856ad364e35')
    Import-Module -Assembly $security -ErrorAction Stop
} else {
    Import-Module (Join-Path $PSHOME 'Microsoft.PowerShell.Security.dll') -ErrorAction Stop
}
$policy=Get-ExecutionPolicy -ErrorAction Stop
$printed=New-Object System.Collections.Generic.List[string]
$failed=$false
$global:Answers=New-Object System.Collections.Generic.Queue[string]
'''
    program=prelude+"\n$global:Scenario='"+scenario+"'\n"
    program+=r'''
if ($global:Scenario -in @('recover','recover_failed')) {
    $checkoutId=[guid]::NewGuid().ToString('N')
    $global:Owned=Join-Path $env:TEMP ('samas-email-structure-v1-'+$checkoutId)
    $null=New-Item -ItemType Directory -Path $global:Owned
    $global:Answers.Enqueue('recover');$global:Answers.Enqueue($checkoutId);$global:Answers.Enqueue(('e'*32));$global:Answers.Enqueue(('f'*64))
} else {
    $choice='diagnose'
    $global:Answers.Enqueue($choice)
}
'''
    program+='\ntry {\n'+block+'\n | ForEach-Object { $printed.Add("$_") }\n} catch {$failed=$true}\n'
    program=program.replace('}\n | ForEach-Object','} | ForEach-Object')
    program+=r'''
$restored=(Get-Location).Path -eq $original -and $encoding -eq $OutputEncoding.CodePage -and $console -eq [Console]::OutputEncoding.CodePage -and $preference -eq $ErrorActionPreference
if($global:Owned){Remove-Item -LiteralPath $global:Owned -Force}
@{policy="$policy";runs=$global:Runs;reads=$global:Reads;fetches=$global:Fetches;chosen=$global:Chosen;probes=$global:Probes;copies=$global:Copies;copied=$global:Copied;printed=($printed -join "`n");failed=$failed;restored=$restored} | ConvertTo-Json -Depth 15 -Compress
'''
    result=subprocess.run([shell,'-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Restricted','-Command','-'],input=program+'\n\n',text=True,encoding='utf-8',capture_output=True,timeout=40,env=dict(os.environ,TERM='dumb'))
    cleaned=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',result.stdout)
    lines=[s for s in cleaned.splitlines() if s.startswith('{')]
    assert result.returncode==0 and lines,result.stdout+result.stderr
    value=json.loads(lines[-1])
    assert value['policy']=='Restricted' and value['restored'],json.dumps(value)+result.stderr
    blocked=scenario in ('bad_commit','bad_tree','dirty','version_bad')
    recovering=scenario in ('recover','recover_failed')
    assert value['runs']==(0 if blocked or recovering else 1)
    assert value['reads']==int(recovering)
    assert value['fetches']==(0 if recovering else 1)
    assert value['probes']==(0 if scenario in ('bad_commit','bad_tree','dirty') else 1)
    assert value['copies']==1 and value['failed']==(scenario not in ('success','recover'))
    if not blocked:
        assert '80000000000' in value['printed'] and 'phases' in value['printed'] and 'field_set' in value['printed']
        if scenario!='clipboard_error':assert '80000000000' in value['copied']
    if value['runs']:assert value['chosen']=='diagnose'




@pytest.mark.parametrize('fault',['missing','changed','invalid_json','wrong_experiment'])
def test_recovery_failures_never_rerun_or_print_untrusted_content(monkeypatch,tmp_path,capsys,fault):
    http=mocked(monkeypatch);r=d.run();calls=len(http.calls)
    monkeypatch.setattr(d,'ROOT',tmp_path);monkeypatch.setattr(d,'version',lambda:(3,12,10))
    p=tmp_path/d.save(r);digest=sha256(p.read_bytes()).hexdigest()
    if fault=='missing':p.unlink()
    elif fault=='changed':p.write_text('private corrupt report',encoding='utf-8')
    elif fault=='invalid_json':
        raw=b'{broken private json';p.write_bytes(raw);digest=sha256(raw).hexdigest()
    else:
        r['experiment']='unapproved';raw=d.encoded(r);p.write_bytes(raw);digest=sha256(raw).hexdigest()
    assert d.main(['--synthetic-only','recover',p.parent.name,digest])==1
    text=capsys.readouterr().out
    assert json.loads(text)['error_code']=='report_recovery_failed'
    assert 'private' not in text and 'unapproved' not in text
    assert len(http.calls)==calls




@pytest.mark.parametrize('endpoint',['/api/version','/api/tags','/api/show'])
@pytest.mark.parametrize('at,attempted',[(1,0),(2,0),(3,1),(8,6)])
def test_all_identity_observation_interrupts_are_permanent(monkeypatch,endpoint,at,attempted):
    count=0
    def reply(m,p,v,r):
        nonlocal count
        if p==endpoint:
            count+=1
            if count==at:raise KeyboardInterrupt()
        return r
    http=mocked(monkeypatch,reply);r=d.run()
    assert r['attempted']==attempted and r['stop_code']=='interrupted'
    assert not r['identity_verified_at_end'] and r['observed_identity'] is None
    assert r['attributed_constraint_counts'] is None
    assert r['prediction_attribution']=='unattributed_diagnostic'
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==attempted


@pytest.mark.parametrize('path',list(d.SOURCE_PINS)+[d.CONFIG.as_posix()])
def test_changed_source_or_config_rejected_before_network(monkeypatch,path):
    http=mocked(monkeypatch)
    original=d.read_bounded
    def reading(p,maximum):
        raw=original(p,maximum)
        return raw+b' ' if p==d.ROOT/path else raw
    monkeypatch.setattr(d,'read_bounded',reading)
    with pytest.raises(d.Error):d.run()
    assert not http.calls


def test_execute_embedded_python_cli_without_model(monkeypatch,capsys):
    text=(d.ROOT/'docs/synthetic-email-structure-diagnostic-v1.md').read_text(encoding='utf-8')
    block=re.search(r'```powershell\n(.*?)\n```',text,re.S).group(1)
    snippets=re.findall(r"\$code = @'\n(.*?)\n'@",block,re.S)
    assert len(snippets)==2
    for code in snippets:compile(code,'approved_stdin','exec')
    http=mocked(monkeypatch)
    monkeypatch.setattr(d,'main',lambda args:0)
    monkeypatch.setattr(sys,'version_info',(3,12,10))
    monkeypatch.setattr(sys,'argv',['-','--synthetic-only','diagnose'])
    with pytest.raises(SystemExit) as exit:
        exec(snippets[1],{'__name__':'__main__'})
    assert exit.value.code==0 and not http.calls
