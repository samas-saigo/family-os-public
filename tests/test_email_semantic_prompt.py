"""Single prompt adapter: real inherited lifecycle/transport with mocked HTTP only."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import runpy
import socket
import sys

import pytest
from experiments import email_semantic_prompt as d
from test_email_model_evidence import mocked, envelope, output

CONFIG, WIRE, CASES = d.setup()
BY_INPUT = {d.wording.canonical(c['input']): c for c in CASES}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*a, **k): pytest.fail('Real network/model forbidden')
    monkeypatch.setattr(socket, 'create_connection', deny)
    monkeypatch.setattr(socket.socket, 'connect', deny)


def gold(method,path,payload,value):
    if path=='/api/chat':
        return envelope(output(BY_INPUT[payload['messages'][1]['content']]['reference']))
    return value


def test_freeze_reuse_and_frozen_namespace_isolation(monkeypatch):
    before=dict(vars(d.baseline))
    previous, old_wire, _=d.baseline.setup()
    assert d.FREEZE=='f9530a091e9011556d8332aa03422460e1b315a6'
    for path,expected in {d.CONFIG.as_posix():d.CONFIG_SHA,**d.SOURCE_PINS}.items():
        assert sha256((d.ROOT/path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==expected
    assert CONFIG['prompt']!=previous['prompt'] and dict(WIRE,prompt=old_wire['prompt'])==old_wire
    for name in ('save','read_report','collect'):
        new,old=getattr(d,name),getattr(d.baseline,name)
        assert new.__code__ is old.__code__ and new.__globals__ is vars(d)
    assert d._frozen_run.__code__ is d.baseline.run.__code__
    assert d.main.__code__ is d.baseline.prior.main.__code__
    assert d.Transport.__init__.__code__ is d.baseline.Transport.__init__.__code__
    for name in ('request','payload','identity','remaining','residency'):
        assert getattr(d.Transport,name) is getattr(d.baseline.Transport,name)
    assert d.parent.score is d.baseline.parent.score and d.parent.compare is d.baseline.parent.compare
    mocked(monkeypatch,gold);d.run('smoke')
    # No rebinding/mutation of frozen module constants, functions, classes or configs.
    assert all(vars(d.baseline)[k] is v for k,v in before.items())
    assert d.baseline.setup()==(previous,old_wire,CASES)


@pytest.mark.parametrize('mode,n',[('smoke',6),('full',36)])
def test_actual_requests_only_prompt_changes_and_budgets_gold_isolation(monkeypatch,mode,n):
    http=mocked(monkeypatch,gold);r=d.run(mode);previous=d.baseline.setup()[0]
    assert r['run_status']=='complete' and r['identity_verified_at_end'] and r['attempted']==n
    assert r['model_metrics']['selected']==r['rule_metrics']['selected']==n
    assert r['comparison']['selected']==n and sum(x['selected'] for x in r['by_group'].values())==n
    sent=[v for _,p,v,_ in http.calls if p=='/api/chat'];ids=[];sizes=[];contexts=[]
    for payload in sent:
        case=BY_INPUT[payload['messages'][1]['content']];ids.append(case['id'])
        projection=d.engine.EmailMetadata(case['input'])
        old=d.baseline.Transport(previous,mode,case['id'],d.time.monotonic()+600).payload(projection)
        restored=deepcopy(payload);restored['messages'][0]['content']=old['messages'][0]['content']
        assert payload!=old and restored==old
        assert payload['format']==previous['output_schema'] and payload['messages'][0]['content']==CONFIG['prompt']
        assert set(json.loads(payload['messages'][1]['content']))=={'schema','synthetic_only','provider','record_type','notice_kind','subject'}
        sizes.append(len(d.wording.canonical(payload).encode()));contexts.append(d.context_bound(CONFIG,projection))
    assert ids==(CONFIG['smoke'] if mode=='smoke' else [c['id'] for c in CASES]) and len(set(ids))==n
    assert max(sizes)<=16384 and max(contexts)<=4096
    assert r['schema_sha256']==sha256(d.wording.canonical(previous['output_schema']).encode()).hexdigest()
    assert r['prompt_sha256']==sha256(CONFIG['prompt'].encode()).hexdigest()
    assert r['implementation_lf_sha256']==sha256(Path(d.__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    assert all(row['structure_reason']=='none' for row in r['cases'])
    text=d.encoded(r).decode()
    assert 'input_fingerprint' not in text and CONFIG['prompt'] not in text
    assert all(c['input']['subject'] not in text for c in CASES)
    if mode=='full':
        assert r['selected']==dict(cases=36,clear=24,ambiguous=12,groups=12)
        assert r['model_metrics']['clear_outcomes']['full']==24 and r['model_metrics']['ambiguous_abstain']==12
        print('Actual Mock full36 request bytes:',min(sizes),max(sizes),'context content-byte/framing/output bound:',max(contexts))


def test_single_generic_prompt_and_preregistered_nonstructural_evaluation():
    prompt=CONFIG['prompt'];rules=CONFIG['evaluation']
    assert not re.search(r'WC[0-9]|\bgroup\b|\bgold\b',prompt,re.I)
    assert all(c['input']['subject'] not in prompt for c in CASES)
    assert len(prompt.encode())==2081 and sha256(prompt.encode()).hexdigest()=='5008dbe3028f54869e9234b809699123e1f478544c9c40d450a11312f8fe8bed'
    assert rules['joint_screen']==dict(clear_full_min=7,ambiguous_abstain_min=1,ambiguous_overreach_max=6,unsupported_step_cases_max=3,missed_outstanding_cases_max=10,missed_date_cases_max=12)
    assert rules['remaining_nonregression']==['unsupported_completion_cases','invented_date_cases','misbound_date_cases','false_clearance_proxy_cases']
    assert 'unknown, never zero' in rules['decision'] and 'inconclusive' in rules['decision']


def test_original_parser_rejection_differential_and_private_failure_report(monkeypatch):
    from test_email_structure_diagnostic import branch_values
    projection=next(d.engine.EmailMetadata(c['input']) for c in CASES if c['input']['notice_kind']=='service')
    for value,_ in branch_values():
        response=envelope(value)
        # Same validator and parser; adapter never intercepts/replaces their result.
        annotated=d.diagnostic.response_result(response,projection,CONFIG['limits'])
        original=d.compat.response_result(response,projection,CONFIG['limits'])
        assert {k:v for k,v in annotated.items() if k!='structure_reason'}==original
    def invalid(m,p,v,r):
        if p=='/api/chat':return envelope(dict(state='abstain',steps=[],dates=[],private_key='private_value'))
        return r
    mocked(monkeypatch,invalid);r=d.run('smoke')
    assert r['status_counts']=={'invalid_structure':6} and r['attributed_constraint_counts']=={'field_set':6}
    assert all(x['actual'] is None for x in r['cases']) and 'private_' not in d.encoded(r).decode()
    assert r['model_metrics']['status_counts']['invalid_output']==6 and r['model_metrics']['ambiguous_abstain']==0


def test_structurally_valid_semantic_errors_and_omissions_are_still_scored(monkeypatch):
    def wrong(m,p,v,r):
        if p!='/api/chat':return r
        c=BY_INPUT[v['messages'][1]['content']]
        if c['input']['notice_kind']=='service':
            return envelope(dict(state='explicit_completion',steps=[dict(action='return_form',status='reported_completed')],dates=[dict(role='reported_completion_date',value='2034-03-19',action='return_form')]))
        return envelope(dict(state='promotional',steps=[],dates=[dict(role='offer_expiry',value='2034-03-19',action=None)]))
    mocked(monkeypatch,wrong);r=d.run('full');m=r['model_metrics']
    assert r['status_counts']=={'valid':36} and r['comparison'] is not None
    assert m['unsupported_step_cases']>0 and m['unsupported_completion_cases']>0 and m['invented_date_cases']>0
    assert m['missed_outstanding_cases']==12 and m['missed_date_cases']>0 and m['ambiguous_overreach']==12
    assert r['comparison']['additional_errors']['unsupported_completion_cases']>0
    mocked(monkeypatch);r=d.run('full');m=r['model_metrics']
    assert m['ambiguous_abstain']==12 and m['clear_outcomes']['full']==0
    assert m['missed_outstanding_cases']==12 and m['missed_date_cases']==16  # Always abstain cannot pass joint screen.


@pytest.mark.parametrize('endpoint',['/api/version','/api/tags','/api/show'])
@pytest.mark.parametrize('at,attempted',[(1,0),(2,0),(3,1),(8,6)])
def test_identity_interrupt_is_permanent_even_after_normal_final_observation(monkeypatch,endpoint,at,attempted):
    seen=0
    def fault(m,p,v,r):
        nonlocal seen
        if p==endpoint:
            seen+=1
            if seen==at:raise KeyboardInterrupt()
        return gold(m,p,v,r)
    http=mocked(monkeypatch,fault);r=d.run('smoke')
    assert r['run_status']=='partial' and r['stop_code']=='interrupted' and r['attempted']==attempted
    assert r['model_metrics'] is r['comparison'] is r['by_group'] is r['attributed_constraint_counts'] is None
    assert not r['identity_verified_at_end'] and r['selected']['cases']==len(r['cases'])==6
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==attempted


@pytest.mark.parametrize('fault,code',[('reply_identity','identity_unverified'),('thinking','thinking_leakage'),('timeout','timeout'),('prompt_tokens','resource_limit')])
def test_fatal_partial_denominators_no_retry(monkeypatch,fault,code):
    def failing(m,p,v,r):
        if p=='/api/chat':
            if fault=='reply_identity':r['model']='different'
            elif fault=='thinking':r['message']['thinking']='private_thought'
            elif fault=='timeout':raise TimeoutError('private_error')
            else:r['prompt_eval_count']=4097
        return r
    http=mocked(monkeypatch,failing);r=d.run('full')
    assert r['run_status']=='partial' and r['stop_code']==code and r['attempted']==1
    assert len(r['cases'])==r['selected']['cases']==36 and r['status_counts']['not_attempted']==35
    assert r['cases'][0]['actual'] is None and r['comparison'] is None
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==1
    assert 'private_' not in d.encoded(r).decode()
    if fault=='reply_identity':assert not r['identity_verified_at_end'] and r['model_metrics'] is None
    else:assert r['model_metrics']['selected']==36


@pytest.mark.parametrize('seconds,code',[(60.01,'timeout'),(601,'resource_limit')])
def test_absolute_chat_run_budgets_and_partial_save(monkeypatch,tmp_path,seconds,code):
    clock=[100.0];monkeypatch.setattr(d.time,'monotonic',lambda:clock[0])
    def elapsed(m,p,v,r):
        if p=='/api/chat':clock[0]+=seconds
        return r
    http=mocked(monkeypatch,elapsed);r=d.run('smoke')
    assert r['stop_code']==code and r['attempted']==1 and len(r['cases'])==6
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==1
    monkeypatch.setattr(d,'ROOT',tmp_path);path=tmp_path/d.save(r)
    assert d.read_report(path.parent.name,sha256(path.read_bytes()).hexdigest())==r


@pytest.mark.parametrize('target',['config','baseline','context'])
def test_preflight_failure_is_zero_requests(monkeypatch,target):
    http=mocked(monkeypatch)
    if target=='context':monkeypatch.setattr(d,'context_bound',lambda *a:99999)
    else:
        real=d.read_bounded;chosen=d.CONFIG if target=='config' else Path('experiments/email_relational_schema.py')
        monkeypatch.setattr(d,'read_bounded',lambda p,n:real(p,n)+(b' ' if p==d.ROOT/chosen else b''))
    with pytest.raises(d.Error):d.run('full')
    assert not http.calls


def test_report_namespace_atomic_failure_cli_and_readonly_recovery(monkeypatch,tmp_path,capsys):
    http=mocked(monkeypatch,gold);monkeypatch.setattr(d,'version',lambda:(3,12,10))
    save,read=d.save,d.read_report
    def saving(report):
        with monkeypatch.context() as m:m.setattr(d,'ROOT',tmp_path);return save(report)
    def reading(run,expected):
        with monkeypatch.context() as m:m.setattr(d,'ROOT',tmp_path);return read(run,expected)
    monkeypatch.setattr(d,'save',saving);monkeypatch.setattr(d,'read_report',reading)
    assert d.main(['--synthetic-only','smoke'])==0
    result=json.loads(capsys.readouterr().out);r=result['report'];calls=len(http.calls)
    path=tmp_path/result['report_path'];raw=path.read_bytes()
    assert d.LOCAL!=d.baseline.LOCAL and result['report_read_verified']
    assert d.main(['--synthetic-only','recover',path.parent.name,result['report_sha256']])==0
    assert json.loads(capsys.readouterr().out)['report']==r and len(http.calls)==calls
    assert d.main(['--synthetic-only','recover',path.parent.name,'0'*64])==1;capsys.readouterr()
    assert len(http.calls)==calls
    with monkeypatch.context() as m:
        m.setattr(d,'ROOT',tmp_path)
        second=tmp_path/save(r);assert second!=path and path.read_bytes()==raw
        wrong=dict(r,experiment=d.baseline.EXPERIMENT);path.write_bytes(d.encoded(wrong))
        with pytest.raises(d.Error):read(path.parent.name,sha256(path.read_bytes()).hexdigest())
        path.write_bytes(raw)
        with pytest.raises(d.Error):read('../'+path.parent.name,result['report_sha256'])
    def fail(*a,**k):raise OSError('private_filesystem_error')
    monkeypatch.setattr(os,'fsync',fail)
    value=d.collect('smoke')
    assert value['error_code'] and value['report'] and value['report_source']=='retained_in_memory'
    assert 'private_filesystem_error' not in json.dumps(value) and not list(tmp_path.rglob('*.tmp'))
    assert path.read_bytes()==raw


def test_wrong_python_and_unsupported_cli_never_generate(monkeypatch,capsys):
    http=mocked(monkeypatch);monkeypatch.setattr(d,'version',lambda:(3,12,0))
    assert d.main(['--synthetic-only','full'])==1
    assert json.loads(capsys.readouterr().out)['error_code']=='python_version_mismatch'
    for args in (['smoke'],['--synthetic-only','inventory'],['--synthetic-only','full','--host','x']):
        with pytest.raises(SystemExit):d.main(args)
    with monkeypatch.context() as m:
        m.setattr(sys,'argv',['email_semantic_prompt','--synthetic-only','smoke']);m.setattr(sys,'version_info',(3,12,0))
        with pytest.raises(SystemExit) as exc:runpy.run_path(d.__file__,run_name='__main__')
        assert exc.value.code==1
    assert json.loads(capsys.readouterr().out)['workflow']==d.EXPERIMENT and not http.calls


@pytest.mark.parametrize('shell_name',['powershell','pwsh'])
@pytest.mark.parametrize('scenario',['success','full','partial','read_error','clipboard_error','version_bad','bad_commit','bad_tree','dirty','recover','recover_failed'])
@pytest.mark.skipif(sys.platform!='win32',reason='Native Restricted interactive stdin workflow; mocked boundaries only')
def test_native_restricted_smoke_full_and_readonly_recovery(shell_name,scenario):
    import shutil
    import subprocess
    shell=shutil.which(shell_name)
    assert shell, 'Native CI must execute both PowerShell shells'
    text=(d.ROOT/'docs/synthetic-email-semantic-prompt-v1.md').read_text(encoding='utf-8')
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
    $global:Owned=Join-Path $env:TEMP ('samas-email-semantic-prompt-v1-'+$checkoutId)
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
