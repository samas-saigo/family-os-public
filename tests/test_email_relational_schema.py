"""New schema-only candidate: real CLI/transport chain with mocked HTTP only."""
from copy import deepcopy
from hashlib import sha256
import builtins
import json
import os
from pathlib import Path
import re
import runpy
import socket
import sys

import pytest

from experiments import email_relational_schema as d
from test_email_model_evidence import mocked, envelope, output

CONFIG, WIRE, CASES = d.setup()
BY_INPUT = {d.wording.canonical(c['input']): c for c in CASES}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*a, **k): pytest.fail('Real network/model access forbidden')
    monkeypatch.setattr(socket, 'create_connection', deny)
    monkeypatch.setattr(socket.socket, 'connect', deny)


def gold(m, p, payload, reply):
    if p == '/api/chat':
        case = BY_INPUT[payload['messages'][1]['content']]
        return dict(envelope(output(case['reference'])), prompt_eval_cached_count=0)
    return reply


def test_frozen_plan_and_unchanged_dependencies():
    assert d.FREEZE == '3e31bb36df6c8602c5ab3b6bbb95dc2c778dbbe2'
    assert sha256((d.ROOT / d.CONFIG).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == d.CONFIG_SHA
    assert CONFIG['source_pins'] == d.SOURCE_PINS
    for path, expected in d.SOURCE_PINS.items():
        assert sha256((d.ROOT / path).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == expected
    assert all(CONFIG[k] == WIRE[k] for k in ('model', 'prompt', 'output_schema', 'generation', 'input'))
    assert (CONFIG['limits']['connect_seconds'], CONFIG['limits']['metadata_seconds'], CONFIG['limits']['chat_seconds'], CONFIG['limits']['run_seconds']) == (5, 5, 60, 600)
    assert d.compat.setup()[0]['limits']['chat_seconds'] == 180
    assert d.Transport.request is d.compat.old.Transport.request
    assert len(CASES) == 36


@pytest.mark.parametrize('mode,n', [('smoke', 6), ('full', 36)])
def test_selection_denominators_gold_isolation_and_same_input_comparison(monkeypatch, mode, n):
    http = mocked(monkeypatch, gold)
    r = d.run(mode)
    assert r['run_status'] == 'complete' and r['attempted'] == n
    assert r['model_metrics']['selected'] == r['rule_metrics']['selected'] == n
    assert r['comparison']['selected'] == n
    assert sum(m['selected'] for m in r['by_group'].values()) == n
    sent = [v for _, p, v, _ in http.calls if p == '/api/chat']
    ids = []
    for payload in sent:
        assert payload == dict(model=CONFIG['model']['tag'], messages=[dict(role='system', content=CONFIG['prompt']), dict(role='user', content=payload['messages'][1]['content'])], format=CONFIG['output_schema'], **CONFIG['generation'])
        fields = json.loads(payload['messages'][1]['content'])
        assert set(fields) == {'schema','synthetic_only','provider','record_type','notice_kind','subject'}
        ids.append(BY_INPUT[payload['messages'][1]['content']]['id'])
    assert ids == (CONFIG['smoke'] if mode == 'smoke' else [c['id'] for c in CASES])
    assert len(set(ids)) == n
    assert len([q for q in r['requests'] if q['endpoint'] == '/api/chat']) == n
    assert all(q['phases'] for q in r['requests'])
    assert all(c['status'] == 'valid' and c['telemetry_validation']['prompt_eval_cached_count'] == 'validated' for c in r['cases'])
    text = d.wording.canonical(r)
    assert CONFIG['prompt'] not in text and 'input_fingerprint' not in text
    assert all(c['input']['subject'] not in text for c in CASES)
    assert r['restrictions']['authority'] == 'none'
    if mode == 'full':
        assert r['selected'] == dict(cases=36, clear=24, ambiguous=12, groups=12)
        assert r['model_metrics']['clear_outcomes']['full'] == 24
        assert r['model_metrics']['ambiguous_abstain'] == 12
        assert r['rule_metrics']['clear_outcomes']['abstain'] == 24
        assert len(r['comparison']['new_full_case_ids']) == 24
        assert r['model_metrics']['missed_outstanding_cases'] == 0
        assert r['model_metrics']['missed_date_cases'] == 0


def test_scorer_error_injection_not_just_structural_validity(monkeypatch):
    def bad(m,p,payload,reply):
        if p == '/api/chat':
            case = BY_INPUT[payload['messages'][1]['content']]
            # Valid finite evidence, deliberately unsupported by these references.
            if case['input']['notice_kind'] == 'service':
                value = dict(state='explicit_completion', steps=[dict(action='return_form',status='reported_completed')], dates=[dict(role='reported_completion_date',value='2034-03-19',action='return_form')])
            else:
                value = dict(state='promotional',steps=[],dates=[dict(role='offer_expiry',value='2034-03-19',action=None)])
            return envelope(value)
        return reply
    mocked(monkeypatch,bad); r=d.run('full'); m=r['model_metrics']
    assert r['attempted']==36 and r['status_counts']=={'valid':36}
    assert m['unsupported_completion_cases'] > 0 and m['unsupported_step_cases'] > 0
    assert m['invented_date_cases'] > 0 and m['missed_date_cases'] > 0
    assert m['missed_outstanding_cases']==12 and m['ambiguous_overreach']==12
    assert r['comparison']['additional_errors']['unsupported_completion_cases'] > 0
    assert r['comparison']['additional_wrong_date_atoms'] > 0


@pytest.mark.parametrize('fault', ['json','structure','refused','truncated'])
def test_ordinary_failed_output_continues_but_never_abstains(monkeypatch,fault):
    count=0
    def reply(m,p,v,r):
        nonlocal count
        if p=='/api/chat':
            count+=1
            if count==1:
                r['message']['content']={'json':'prefix {}','structure':'{}','refused':'','truncated':'{}'}[fault]
                if fault=='truncated': r['done_reason']='length'
        return r
    http=mocked(monkeypatch,reply); r=d.run('smoke')
    assert r['run_status']=='complete' and r['attempted']==6
    assert r['cases'][0]['status']=={'json':'invalid_json','structure':'invalid_structure','refused':'refused','truncated':'truncated'}[fault]
    assert r['model_metrics']['selected']==6 and r['model_metrics']['clear_outcomes']['invalid_output']==1
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==6
    assert r['comparison'] is not None


@pytest.mark.parametrize('fault,code,subreason', [('extra','protocol_error','top_level_fields'),('done','protocol_error','done_not_true'),('role','protocol_error','message_role'),('cache','protocol_error','telemetry_type'),('thinking','thinking_leakage','thinking_present'),('wrong_model','identity_unverified','reply_identity'),('missing_model','identity_unverified','reply_identity'),('malformed_model','identity_unverified','reply_identity'),('timeout','timeout','transport_boundary')])
@pytest.mark.parametrize('at',[1,2])
def test_fatal_stop_all_denominators_and_permanent_identity_loss(monkeypatch,fault,code,subreason,at):
    count=0
    def reply(m,p,v,r):
        nonlocal count
        if p=='/api/chat':
            count+=1
            if count==at:
                if fault=='extra': r['untrusted_private_name']='untrusted value'
                if fault=='done': r['done']=False
                if fault=='role': r['message']['role']='user'
                if fault=='cache': r['prompt_eval_cached_count']=True
                if fault=='thinking': r['message']['thinking']='untrusted thought'
                if fault=='wrong_model': r['model']='other'
                if fault=='missing_model': r.pop('model')
                if fault=='malformed_model': r['model']=None
                if fault=='timeout': raise TimeoutError('private')
        return r
    http=mocked(monkeypatch,reply);r=d.run('full')
    assert r['run_status']=='partial' and r['attempted']==at
    assert r['cases'][at-1]['status']==code and r['cases'][at-1]['subreason']==subreason
    assert r['status_counts']['not_attempted']==36-at and len(r['cases'])==36
    assert r['comparison'] is None and r['selected']['cases']==36
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==at
    assert http.calls[-1][1]=='/api/show'  # Normal final metadata cannot repair reply identity loss.
    if 'model' in fault:
        assert not r['identity_verified_at_end'] and r['observed_identity'] is None
        assert r['model_metrics'] is r['by_group'] is None
        assert r['prediction_attribution']=='unattributed_diagnostic'
    else:
        assert r['identity_verified_at_end'] and r['model_metrics']['selected']==36
        assert r['model_metrics']['status_counts']['invalid_output']==36-at+1
    if fault in ('extra','done','role','cache','thinking'):
        assert r['cases'][at-1]['telemetry']['total_duration'] is not None
    assert 'untrusted_private_name' not in json.dumps(r) and 'untrusted thought' not in json.dumps(r)


@pytest.mark.parametrize('fault',['version','final_digest','revoked_then_normal'])
def test_metadata_identity_failure_never_recovers(monkeypatch,fault):
    tags=0
    def reply(m,p,v,r):
        nonlocal tags
        if p=='/api/version' and fault=='version': return {'version':'0.40.7'}
        if p=='/api/tags':
            tags+=1
            if tags==(8 if fault=='final_digest' else 3) and fault!='version':r['models'][0]['digest']='0'*64
        return r
    http=mocked(monkeypatch,reply);r=d.run('smoke')
    assert not r['identity_verified_at_end'] and r['model_metrics'] is r['by_group'] is r['comparison'] is None
    assert r['attempted']==(0 if fault=='version' else 6 if fault=='final_digest' else 1)
    assert r['run_status']=='partial'


@pytest.mark.parametrize('seconds,code', [(60.01,'timeout'),(601,'resource_limit')])
def test_actual_absolute_budget_no_retry(monkeypatch,seconds,code):
    clock=[100.0]
    monkeypatch.setattr(d.time,'monotonic',lambda:clock[0])
    def reply(m,p,v,r):
        if p=='/api/chat':clock[0]+=seconds
        return r
    http=mocked(monkeypatch,reply);r=d.run('smoke')
    assert r['attempted']==1 and r['cases'][0]['status']==code
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==1
    assert r['status_counts']['not_attempted']==5 and r['comparison'] is None


def test_transport_no_case_substitution_or_counter_reset(monkeypatch):
    http=mocked(monkeypatch)
    client=d.Transport(CONFIG,'smoke','WC01-1',d.time.monotonic()+600)
    p=d.engine.EmailMetadata(CASES[0]['input'])
    payload=client.payload(p)
    client.request('POST','/api/chat',payload)
    with pytest.raises(d.Error):client.request('POST','/api/chat',payload)
    with pytest.raises(d.Error):client.payload(d.engine.EmailMetadata(CASES[1]['input']))
    with pytest.raises(d.Error):client.request('POST','/api/generate',payload)
    with pytest.raises(d.Error):d.Transport(CONFIG,'smoke','WC01-2',d.time.monotonic()+600)
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==1


def test_cli_publication_readback_and_readonly_recovery(monkeypatch,tmp_path,capsys):
    http=mocked(monkeypatch,gold)
    monkeypatch.setattr(d,'version',lambda:(3,12,10))
    real_save,real_read=d.save,d.read_report
    def saving(report):
        with monkeypatch.context() as m:
            m.setattr(d,'ROOT',tmp_path);return real_save(report)
    def reading(run_id,expected):
        with monkeypatch.context() as m:
            m.setattr(d,'ROOT',tmp_path);return real_read(run_id,expected)
    monkeypatch.setattr(d,'save',saving);monkeypatch.setattr(d,'read_report',reading)
    assert d.main(['--synthetic-only','smoke'])==0
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
    assert d.main(['--synthetic-only','smoke'])==1
    text=capsys.readouterr().out;v=json.loads(text)
    assert v['report'] and not v['report_read_verified'] and v['report_source']=='retained_in_memory'
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==6
    assert 'private fs message' not in text and 'private report' not in text
    assert prior.read_text(encoding='utf-8')=='prior' and not list(tmp_path.rglob('*.tmp'))
    assert len(list((tmp_path/d.LOCAL).glob('*'))) == (1 if fault=='read' else 0)


def test_report_unique_namespace_and_recovery_path_bounds(monkeypatch,tmp_path):
    mocked(monkeypatch);r=d.run('smoke');monkeypatch.setattr(d,'ROOT',tmp_path)
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
    assert d.main(['--synthetic-only','full'])==1
    assert json.loads(capsys.readouterr().out)['error_code']=='python_version_mismatch'
    for args in (['smoke'],['--synthetic-only','inventory'],['--synthetic-only','full','--host','x']):
        with pytest.raises(SystemExit):d.main(args)
    assert not http.calls


def test_exact_allowed_files_no_old_experiment_execution(monkeypatch):
    allowed={str(d.ROOT/p) for p in (*d.SOURCE_PINS,d.CONFIG.as_posix(),d.parent.CONFIG.as_posix(),'experiments/email_relational_schema.py',d.compat.old.CONFIG.as_posix(),d.compat.CONFIG.as_posix(),'experiments/email_wording_challenge.py','src/family_os/_synthetic_email_evidence.py','fixtures/synthetic-email-wording-challenge-v1.json')}
    real=os.open;seen=[]
    def opening(path,*a,**k):
        assert str(path) in allowed, 'Unexpected input file access'
        seen.append(str(path));return real(path,*a,**k)
    monkeypatch.setattr(os,'open',opening)
    for owner in (d.parent,d.compat,d.compat.old):
        monkeypatch.setattr(owner,'run',lambda *a,**k:pytest.fail('Frozen runners must not execute'))
    mocked(monkeypatch);r=d.run('smoke')
    assert r['attempted']==6 and seen and all('holdout' not in p.lower() for p in seen)


@pytest.mark.parametrize('shell_name',['powershell','pwsh'])
@pytest.mark.parametrize('scenario',['success','full','partial','read_error','clipboard_error','version_bad','bad_commit','bad_tree','dirty','recover','recover_failed'])
@pytest.mark.skipif(sys.platform!='win32',reason='Native Restricted interactive stdin workflow; mocked boundaries only')
def test_native_restricted_smoke_full_and_readonly_recovery(shell_name,scenario):
    import shutil
    import subprocess
    shell=shutil.which(shell_name)
    assert shell, 'Native CI must execute both PowerShell shells'
    text=(d.ROOT/'docs/synthetic-email-relational-schema-v1.md').read_text(encoding='utf-8')
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
            if ($diagMode -cnotin @('smoke','full')) {throw 'wrong_mode'}
            $global:Chosen=$diagMode
        }
        $status=if($global:Scenario -eq 'partial'){'partial'}else{'complete'}
        $code=if($global:Scenario -eq 'partial'){2}elseif($global:Scenario -in @('read_error','recover_failed')){1}else{0}
        $n=if($diagMode -eq 'full'){36}else{6}
        $value=@{workflow_exit_code=$code;report_read_verified=($code -ne 1);report_sha256=('f'*64);report=@{run_status=$status;selected=@{cases=$n};cases=@(@{telemetry=@{load_duration=80000000000;prompt_eval_cached_count=64};subreason='none';telemetry_validation=@{load_duration='validated'}});requests=@(@{phases=@{connect=@{completed=$true;elapsed_seconds=0.1}}})}} | ConvertTo-Json -Depth 15
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
    $global:Owned=Join-Path $env:TEMP ('samas-email-relational-schema-v1-'+$checkoutId)
    $null=New-Item -ItemType Directory -Path $global:Owned
    $global:Answers.Enqueue('recover');$global:Answers.Enqueue($checkoutId);$global:Answers.Enqueue(('e'*32));$global:Answers.Enqueue(('f'*64))
} else {
    $choice=if($global:Scenario -eq 'full'){'full'}else{'smoke'}
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
    assert value['copies']==1 and value['failed']==(scenario not in ('success','full','recover'))
    if not blocked:
        assert '80000000000' in value['printed'] and 'phases' in value['printed']
        if scenario!='clipboard_error':assert '80000000000' in value['copied']
    if value['runs']:assert value['chosen']==('full' if scenario=='full' else 'smoke')


def test_safe_abstain_is_omission_not_false_clearance(monkeypatch):
    mocked(monkeypatch);r=d.run('full');m=r['model_metrics']
    assert m['selected']==36 and m['clear_outcomes']['abstain']==24
    assert m['ambiguous_abstain']==12 and m['ambiguous_overreach']==0
    assert m['missed_outstanding_cases']==12 and m['missed_date_cases']==16
    assert m['false_clearance_proxy_cases']==0 and m['unsupported_step_cases']==0
    assert r['comparison']['additional_errors']['unsupported_step_cases']==0


@pytest.mark.parametrize('target',['config','validator','transport','parser'])
def test_changed_source_identity_stops_before_network(monkeypatch,target):
    http=mocked(monkeypatch);real=d.read_bounded
    chosen={'config':d.CONFIG,'validator':Path('experiments/single_email_compat.py'),'transport':Path('experiments/single_email_diagnostic.py'),'parser':Path('experiments/email_model_evidence.py')}[target]
    def reading(p,n):
        raw=real(p,n)
        return raw+b' ' if p==d.ROOT/chosen else raw
    monkeypatch.setattr(d,'read_bounded',reading)
    with pytest.raises(d.Error):d.run('smoke')
    assert not http.calls


def test_real_module_entry_wrong_version_is_zero_generation(monkeypatch,capsys):
    http=mocked(monkeypatch)
    with monkeypatch.context() as m:
        m.setattr(sys,'argv',['email_relational_schema','--synthetic-only','smoke'])
        m.setattr(sys,'version_info',(3,12,0))
        with pytest.raises(SystemExit) as exc:runpy.run_path(d.__file__,run_name='__main__')
        assert exc.value.code==1
    assert json.loads(capsys.readouterr().out)['error_code']=='python_version_mismatch'
    assert not http.calls


@pytest.mark.parametrize('fault',['missing','changed','invalid_json','wrong_experiment'])
def test_recovery_failures_never_rerun_or_print_untrusted_content(monkeypatch,tmp_path,capsys,fault):
    http=mocked(monkeypatch);r=d.run('smoke');calls=len(http.calls)
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
def test_identity_observation_interrupt_permanently_removes_attribution(monkeypatch,endpoint,at,attempted):
    observations=0
    interrupted=False
    later=[]
    def reply(method,path,payload,value):
        nonlocal observations,interrupted
        if path==endpoint:
            observations+=1
            if observations==at:
                interrupted=True
                raise KeyboardInterrupt()
        if interrupted:later.append(path)
        return gold(method,path,payload,value)
    http=mocked(monkeypatch,reply)
    r=d.run('smoke')
    assert interrupted and r['run_status']=='partial' and r['stop_code']=='interrupted'
    assert r['attempted']==attempted and sum(path=='/api/chat' for _,path,_,_ in http.calls)==attempted
    assert r['selected']==dict(cases=6,clear=5,ambiguous=1,groups=5)
    assert len(r['cases'])==6 and r['status_counts'].get('not_attempted',0)==6-attempted
    assert not r['identity_verified_at_end'] and r['observed_identity'] is None
    assert r['prediction_attribution']=='unattributed_diagnostic'
    assert r['model_metrics'] is r['by_group'] is r['comparison'] is r['attributed_constraint_counts'] is None
    assert r['rule_metrics']['selected']==6
    for row in r['cases'][:attempted]:
        assert row['status']=='valid' and row['actual']==row['reference']
        assert row['telemetry_validation']['prompt_eval_cached_count']=='validated'
    if at!=8:
        # The final complete metadata observation succeeds; it cannot clear taint.
        assert later[-3:]==['/api/version','/api/tags','/api/show']


@pytest.mark.parametrize('at',[1,2])
def test_chat_interrupt_does_not_imply_identity_loss(monkeypatch,at):
    chats=0
    def reply(method,path,payload,value):
        nonlocal chats
        if path=='/api/chat':
            chats+=1
            if chats==at:raise KeyboardInterrupt()
        return gold(method,path,payload,value)
    http=mocked(monkeypatch,reply)
    r=d.run('smoke')
    assert r['run_status']=='partial' and r['stop_code']=='interrupted'
    assert r['attempted']==at and chats==at
    assert sum(path=='/api/chat' for _,path,_,_ in http.calls)==at
    assert r['identity_verified_at_end'] and r['observed_identity'] is not None
    assert r['prediction_attribution']=='observed_candidate'
    assert r['model_metrics']['selected']==6 and r['by_group'] is not None
    assert r['comparison'] is None and r['status_counts']['not_attempted']==6-at
    assert r['cases'][at-1]['status']=='interrupted' and r['cases'][at-1]['subreason']=='transport_boundary'
    assert r['cases'][at-1]['actual'] is None
    assert http.calls[-1][1]=='/api/show'


# Independent, deliberately small JSON Schema evaluator for the inspected subset.
# Fails on unrecognized keywords; this is test evidence, never runtime acceptance.
def schema_accepts(value, schema=None):
    schema = CONFIG['output_schema'] if schema is None else schema
    assert set(schema) <= {'anyOf','definitions','$ref','type','enum','required','properties','additionalProperties','items','additionalItems','minItems','maxItems','pattern','maxLength'}
    if '$ref' in schema:
        return schema_accepts(value, CONFIG['output_schema']['definitions'][schema['$ref'].split('/')[-1]])
    if 'anyOf' in schema:
        return any(schema_accepts(value, s) for s in schema['anyOf'])
    typ = schema.get('type')
    if typ and type(value) is not {'object':dict,'array':list,'string':str,'null':type(None)}[typ]:
        return False
    if 'enum' in schema and value not in schema['enum']: return False
    if typ == 'object':
        props = schema['properties']
        return (set(schema['required']) <= set(value) and (schema['additionalProperties'] or set(value) <= set(props))
                and all(schema_accepts(v, props[k]) for k,v in value.items() if k in props))
    if typ == 'array':
        if not schema.get('minItems',0) <= len(value) <= schema.get('maxItems',float('inf')): return False
        items = schema['items']
        if type(items) is list:
            return len(value) == len(items) and all(schema_accepts(v,s) for v,s in zip(value,items,strict=True))
        return all(schema_accepts(v, items) for v in value)
    if typ == 'string':
        return len(value) <= schema.get('maxLength',float('inf')) and ('pattern' not in schema or re.search(schema['pattern'],value) is not None)
    return True


def compiled_gbnf():
    """Expand the actual converter's acyclic, regular GBNF snapshot into Python RE.

    Only literal/class/union/group/repetition/ref syntax appears in this artifact.
    Reject unfamiliar syntax or recursion instead of interpreting it loosely.
    No synthetic reply is produced or passed through a model.
    """
    from functools import cache
    raw=(d.ROOT/'experiments/schema_support/relational-v1.gbnf').read_bytes().replace(b'\r\n',b'\n')
    assert sha256(raw).hexdigest()=='fc620e5fd1d625b24ed9e79470cb2853752e64ce422ccc6c8f67b7b9e54ddaf0'
    rules=dict(line.split(' ::= ',1) for line in raw.decode().splitlines())
    token=re.compile(r'\s*("(?:[^"\\]|\\.)*"|\[(?:[^\]\\]|\\.)*\]|\{[0-9]+,[0-9]*\}|[a-zA-Z][a-zA-Z0-9-]*|[()|?*+])')
    active=set()
    @cache
    def expand(name):
        assert name not in active
        active.add(name); parts=[]; pos=0; body=rules[name]
        while pos<len(body):
            m=token.match(body,pos);assert m,body[pos:]
            t=m[1];pos=m.end()
            if t.startswith('"'): parts.append(re.escape(json.loads(t)))
            elif t[0].isalpha(): parts.append('(?:'+expand(t)+')')
            elif t=='(':parts.append('(?:')
            else:parts.append(t)
        active.remove(name)
        return ''.join(parts)
    return re.compile(expand('root'))


GRAMMAR = compiled_gbnf()
SERVICE=next(d.engine.EmailMetadata(c['input']) for c in CASES if c['input']['notice_kind']=='service')
PROMO=next(d.engine.EmailMetadata(c['input']) for c in CASES if c['input']['notice_kind']=='promotional')


def grammar_accepts(v):
    return GRAMMAR.fullmatch(json.dumps(v,separators=(',',':'))) is not None


def parser_accepts(v,projection=SERVICE):
    try:
        d.parent.parse_prediction(json.dumps(v),projection)
        return True
    except d.Error:
        return False


def test_actual_36_wire_requests_change_only_format_and_fit_original_budget(monkeypatch):
    http=mocked(monkeypatch,gold); r=d.run('full')
    previous=d.prior.setup()[0]
    sizes=[]
    for _,path,payload,_ in http.calls:
        if path!='/api/chat':continue
        original=dict(model=previous['model']['tag'],messages=payload['messages'],format=previous['output_schema'],**previous['generation'])
        assert payload!=original
        assert dict(payload,format=original['format'])==original
        assert payload['messages'][0]['content'].encode()==previous['prompt'].encode()
        sizes.append(len(d.wording.canonical(payload).encode()))
    assert len(sizes)==36 and max(sizes)<=previous['limits']['request_bytes']==16384
    assert all(v['structure_reason']=='none' for v in r['cases'])
    assert r['attributed_constraint_counts']=={'none':36}
    print('Actual serialized Mock requests: min/max bytes',min(sizes),max(sizes))


@pytest.mark.parametrize('state',['explicit_outstanding','explicit_completion','informational','promotional','abstain'])
def test_all_original_legal_step_combinations_and_optional_dates_remain_possible(state):
    import itertools
    actions=[a.value for a in d.engine.Action];statuses=[s.value for s in d.engine.Status]
    projection=PROMO if state=='promotional' else SERVICE
    selections=[[]]
    selections += [[dict(action=a,status=s)] for a,s in itertools.product(actions,statuses)]
    selections += [[dict(action=a,status=s),dict(action=b,status=t)] for a,b in itertools.permutations(actions,2) for s,t in itertools.product(statuses,repeat=2)]
    count=0
    for steps in selections:
        value=dict(state=state,steps=steps,dates=[])
        accepted=parser_accepts(value,projection)
        assert schema_accepts(value)==accepted
        assert grammar_accepts(value)==accepted
        if not accepted:continue
        count+=1
        dates=[]
        if state=='explicit_outstanding':dates=[dict(role='due_date',value='2028-02-29',action=s['action']) for s in steps if s['status']=='reported_outstanding']
        elif state=='explicit_completion':dates=[dict(role='reported_completion_date',value='2028-02-29',action=s['action']) for s in steps]
        elif state=='informational':dates=[dict(role=role,value='2028-02-29',action=None) for role in ('event_date','available_date')]
        elif state=='promotional':dates=[dict(role='offer_expiry',value='2028-02-29',action=None)]
        for date in dates:
            v=dict(value,dates=[date])
            assert parser_accepts(v,projection) and schema_accepts(v) and grammar_accepts(v)
    assert count=={'explicit_outstanding':301,'explicit_completion':49,'informational':183,'promotional':1,'abstain':1}[state]


@pytest.mark.parametrize('state,role,bound',[('explicit_outstanding','due_date',True),('explicit_completion','reported_completion_date',True),('informational','event_date',False),('informational','available_date',False),('promotional','offer_expiry',False)])
def test_wrong_date_state_or_nullability_rejected_by_both_schema_and_parser(state,role,bound):
    projection=PROMO if state=='promotional' else SERVICE
    status='reported_outstanding' if state=='explicit_outstanding' else 'reported_completed'
    steps=[dict(action='invoice_payment',status=status)] if bound else []
    good=dict(state=state,steps=steps,dates=[dict(role=role,value='2028-02-29',action='invoice_payment' if bound else None)])
    assert parser_accepts(good,projection) and schema_accepts(good) and grammar_accepts(good)
    for bad in [dict(good,dates=[dict(good['dates'][0],action=None if bound else 'invoice_payment')]),dict(good,dates=[dict(good['dates'][0],role='event_date' if bound else 'due_date')])]:
        assert not parser_accepts(bad,projection) and not schema_accepts(bad) and not grammar_accepts(bad)


@pytest.mark.parametrize('fault',['calendar','year','duplicate_action','missing_bound_step','wrong_status_bound_step','notice_kind'])
def test_remaining_constraints_are_still_rejected_by_sole_parser(fault):
    v=dict(state='explicit_outstanding',steps=[dict(action='invoice_payment',status='reported_outstanding')],dates=[dict(role='due_date',value='2028-02-29',action='invoice_payment')])
    projection=SERVICE
    if fault=='calendar':v['dates'][0]['value']='2027-02-29'
    elif fault=='year':v['dates'][0]['value']='2040-01-01'
    elif fault=='duplicate_action':v['steps']*=2
    elif fault=='missing_bound_step':v['dates'][0]['action']='contact_biller'
    elif fault=='wrong_status_bound_step':
        v['steps'].append(dict(action='contact_biller',status='reported_completed'));v['dates'][0]['action']='contact_biller'
    else:projection=PROMO
    assert schema_accepts(v) and grammar_accepts(v)  # Deliberately documented limits.
    assert not parser_accepts(v,projection)
    result=d.diagnostic.response_result(envelope(v),projection,CONFIG['limits'])
    assert result['status']=='invalid_structure' and result['prediction'] is None


def test_frozen_diagnostic_differential_and_private_rejections(monkeypatch):
    from test_email_structure_diagnostic import branch_values
    values=list(branch_values())
    values += [(dict(state='abstain',steps=[],dates=[]),'none')]
    for v,_ in values:
        reply=envelope(v)
        old=d.compat.response_result(reply,SERVICE,CONFIG['limits'])
        new=d.diagnostic.response_result(reply,SERVICE,CONFIG['limits'])
        assert {k:v for k,v in new.items() if k!='structure_reason'}==old
        assert new['structure_reason'] in d.diagnostic.REASONS
    def reject(method,path,payload,value):
        if path=='/api/chat':return envelope(dict(state='private_state',private_name='private_value',steps=[],dates=[]))
        return value
    mocked(monkeypatch,reject);report=d.run('smoke');text=d.encoded(report).decode()
    assert report['status_counts']=={'invalid_structure':6}
    assert report['attributed_constraint_counts']=={'field_set':6}
    assert all(r['actual'] is None for r in report['cases'])
    assert 'private_' not in text and report['model_metrics']['selected']==6
    assert report['model_metrics']['status_counts']['invalid_output']==6
