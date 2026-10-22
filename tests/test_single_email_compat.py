"""Mock-only v2 protocol/telemetry/CLI tests; no Ollama, split data or inference."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys

import pytest

from experiments import single_email_compat as d
from experiments import collect_single_email_compat as entry
from test_single_email_diagnostic import mocked, envelope

CONFIG, WIRE, PROJECTION = d.setup()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*a, **k): pytest.fail('Real network/model access forbidden')
    monkeypatch.setattr(socket, 'create_connection', deny)
    monkeypatch.setattr(socket.socket, 'connect', deny)


def parse(value): return d.response_result(value, PROJECTION, CONFIG['limits'])


@pytest.mark.parametrize('cached', ['absent', 0, 64, 2**63-1])
def test_official_optional_cached_count_valid(cached):
    value = envelope()
    if cached != 'absent': value['prompt_eval_cached_count'] = cached
    result = parse(value)
    assert result['status'] == 'valid' and result['subreason'] == 'none'
    assert result['telemetry']['prompt_eval_cached_count'] == (None if cached == 'absent' else cached)
    assert result['telemetry_validation']['prompt_eval_cached_count'] == ('absent' if cached == 'absent' else 'validated')
    assert result['telemetry']['load_duration'] == 80000000000


@pytest.mark.parametrize('cached', [None, True, False, '0', 0.0, 1.5, -1, 2**63, [], {}])
def test_invalid_cache_never_accepted_or_saved_and_other_telemetry_retained(cached):
    value = dict(envelope(), prompt_eval_cached_count=cached)
    r = parse(value)
    assert r['status'] != 'valid' and r['prediction'] is None
    assert r['subreason'] in ('telemetry_type', 'telemetry_bounds')
    assert r['telemetry']['prompt_eval_cached_count'] is None
    assert r['telemetry_validation']['prompt_eval_cached_count'] in ('invalid_type','out_of_bounds')
    assert r['telemetry']['load_duration'] == 80000000000
    assert r['telemetry_validation']['load_duration'] == 'validated'


def test_no_invented_cached_vs_prompt_context_or_duration_relationship():
    r = parse(dict(envelope(), prompt_eval_cached_count=5000, prompt_eval_count=0, load_duration=200000000000))
    assert r['status'] == 'valid' and r['telemetry']['prompt_eval_cached_count'] == 5000


def test_frozen_old_validator_still_rejects_extension_not_reinterpreted():
    assert d.parent.response_result(envelope(), PROJECTION, CONFIG['limits'])[2] == 'valid'
    for count in (0,64):
        with pytest.raises(d.parent.ExperimentError, match='protocol_error'):
            d.parent.response_result(dict(envelope(),prompt_eval_cached_count=count),PROJECTION,CONFIG['limits'])


@pytest.mark.parametrize('fault,reason', [('unknown','top_level_fields'),('context','top_level_fields'),('done','done_not_true'),('shape','message_shape'),('message_extra','message_shape'),('role','message_role'),('tools','tool_calls'),('thinking','thinking_present'),('inline','inline_thinking'),('content','content_type'),('metric_type','telemetry_type'),('metric_bound','telemetry_bounds'),('end','end_reason'),('large','content_limit'),('json','prediction_json'),('structure','prediction_structure'),('truncated','truncated'),('empty','refused'),('body_reasoning','thinking_present')])
def test_finite_protocol_reasons_keep_independently_valid_telemetry(fault,reason):
    v=envelope()
    if fault=='unknown': v['arbitrary_private_name_not_for_report']='private value'
    if fault=='context': v['context']=[1]
    if fault=='done': v['done']=False
    if fault=='shape': v['message']=None
    if fault=='message_extra': v['message']['private_message_name']='private value'
    if fault=='role': v['message']['role']='private role'
    if fault=='tools': v['message']['tool_calls']=[{}]
    if fault=='thinking': v['message']['thinking']='private reasoning'
    if fault=='inline': v['message']['content']='<think>private reasoning</think>'
    if fault=='content': v['message']['content']=None
    if fault=='metric_type': v['eval_count']='private metric'
    if fault=='metric_bound': v['eval_count']=513
    if fault=='end': v['done_reason']='private reason'
    if fault=='large': v['message']['content']='x'*8193
    if fault=='json': v['message']['content']='private invalid response'
    if fault=='structure': v['message']['content']='{}'
    if fault=='truncated': v['done_reason']='length'
    if fault=='empty': v['message']['content']=''
    if fault=='body_reasoning': v['message']['content']='{"thinking":"private reasoning"}'
    r=parse(v)
    assert r['prediction'] is None and r['subreason']==reason and r['status']!='valid'
    assert r['telemetry']['load_duration']==80000000000
    assert r['telemetry_validation']['load_duration']=='validated'
    assert set(r['presence_top'])==set(CONFIG['report']['presence_top'])
    assert set(r['presence_message'])==set(CONFIG['report']['presence_message'])
    text=json.dumps(r)
    assert 'private ' not in text and 'arbitrary_private_name' not in text and 'private_message_name' not in text
    if fault=='unknown': assert r['unknown_top_level_count']==1
    if fault=='message_extra': assert r['unknown_message_field_count']==1


def test_absent_null_and_not_obtained_are_distinct_not_false_claims():
    v=envelope();v.pop('load_duration');v['eval_duration']=None
    r=parse(v)
    assert r['telemetry_validation']['load_duration']=='absent'
    assert r['telemetry_validation']['eval_duration']=='unavailable'
    assert all(s=='not_obtained' for s in d.empty_observation()['telemetry_validation'].values())
    assert r['status']=='valid'


@pytest.mark.parametrize('fault', ['wrong','missing','malformed'])
def test_identity_priority_stops_and_does_not_recover_after_normal_final_metadata(monkeypatch,fault):
    def response(m,p,v,r):
        if p=='/api/chat':
            if fault=='missing': r.pop('model')
            elif fault=='malformed': r['model']=None
            else: r['model']='other-model'
        return r
    http=mocked(monkeypatch,response);r=d.run()
    assert not r['identity_verified_at_end'] and r['observed_identity'] is None
    assert r['prediction_attribution']=='unattributed_diagnostic'
    assert r['result']['status']=='identity_unverified'
    assert r['result']['subreason']=='reply_identity'
    assert r['run_status']=='partial' and r['root_cause']=='unknown'
    assert http.calls[-1][1]=='/api/show'
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==1
    assert all(v is None for v in r['result']['telemetry'].values())


@pytest.mark.parametrize('at', [1,2,3])
def test_metadata_identity_failure_latches_and_suppresses_attribution(monkeypatch,at):
    seen=0
    def response(m,p,v,r):
        nonlocal seen
        if p=='/api/tags':
            seen+=1
            if seen==at:r['models'][0]['digest']='0'*64
        return r
    http=mocked(monkeypatch,response);r=d.run()
    assert not r['identity_verified_at_end'] and r['observed_identity'] is None
    assert r['attempted']==(1 if at==3 else 0)
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==r['attempted']


def test_no_other_runtime_inference(monkeypatch):
    http=mocked(monkeypatch,lambda m,p,v,r: dict(version='0.40.7') if p=='/api/version' else r)
    r=d.run()
    assert r['attempted']==0 and r['run_status']=='partial' and not r['identity_verified_at_end']
    assert not any(p=='/api/chat' for _,p,_,_ in http.calls)


@pytest.mark.parametrize('partial', [False,True])
def test_real_mock_entry_full_report_success_and_partial(monkeypatch,tmp_path,capsys,partial):
    def response(m,p,v,r):
        if p=='/api/chat':
            r['prompt_eval_cached_count']=64
            if partial: r['message']['role']='user'
        return r
    http=mocked(monkeypatch,response)
    original_save,original_read=d.save,entry.read_published
    def save(report):
        with monkeypatch.context() as m:
            m.setattr(d,'ROOT',tmp_path)
            return original_save(report)
    def read(runtime,relative):
        with monkeypatch.context() as m:
            m.setattr(d,'ROOT',tmp_path)
            return original_read(runtime,relative)
    monkeypatch.setattr(d,'save',save);monkeypatch.setattr(entry,'read_published',read)
    monkeypatch.setattr(entry,'version',lambda:(3,12,10))
    code=entry.main(['--synthetic-only','single'])
    result=json.loads(capsys.readouterr().out)
    assert code==result['diagnostic_exit_code']==(2 if partial else 0)
    assert result['report_read_verified'] and result['report']['root_cause']=='unknown'
    assert result['report']['result']['telemetry']['prompt_eval_cached_count']==64
    assert result['report']['result']['telemetry']['load_duration']==80000000000
    assert result['report']['result']['telemetry_validation']['load_duration']=='validated'
    assert result['report']['requests'][0]['phases']
    assert 'comparison' not in result['report'] and 'model_metrics' not in result['report']
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==1
    assert json.loads((tmp_path/result['report_path']).read_text(encoding='utf-8'))==result['report']
    if partial: assert result['report']['result']['subreason']=='message_role'


@pytest.mark.parametrize('fault', ['timeout','read','publish'])
def test_failure_null_or_retained_telemetry_no_retry(monkeypatch,tmp_path,capsys,fault):
    def response(m,p,v,r):
        if p=='/api/chat' and fault=='timeout':raise TimeoutError('private message')
        return r
    http=mocked(monkeypatch,response)
    original_save,original_read=d.save,entry.read_published
    def save(report):
        if fault=='publish':raise OSError('private path')
        with monkeypatch.context() as m:
            m.setattr(d,'ROOT',tmp_path);return original_save(report)
    def read(runtime,relative):
        if fault=='read':raise OSError('private path')
        with monkeypatch.context() as m:
            m.setattr(d,'ROOT',tmp_path);return original_read(runtime,relative)
    monkeypatch.setattr(d,'save',save);monkeypatch.setattr(entry,'read_published',read)
    monkeypatch.setattr(entry,'version',lambda:(3,12,10))
    assert entry.main(['--synthetic-only','single'])==(2 if fault=='timeout' else 1)
    text=capsys.readouterr().out;r=json.loads(text)
    assert 'private message' not in text and 'private path' not in text
    assert sum(p=='/api/chat' for _,p,_,_ in http.calls)==1
    if fault=='timeout':
        assert all(s=='not_obtained' for s in r['report']['result']['telemetry_validation'].values())
        assert all(v is None for v in r['report']['result']['telemetry'].values())
    else: assert r['report']['result']['telemetry']['load_duration']==80000000000


def test_wire_and_frozen_inputs_unchanged_no_old_validator_or_scoring(monkeypatch):
    def deny(*a,**k):pytest.fail('Old response validator/scorer/interpreter must not be invoked')
    monkeypatch.setattr(d.parent,'response_result',deny)
    monkeypatch.setattr(d.wording,'summarize',deny);monkeypatch.setattr(d.engine,'interpret',deny)
    http=mocked(monkeypatch);r=d.run()
    assert r['run_status']=='complete'
    payload=next(v for _,p,v,_ in http.calls if p=='/api/chat')
    assert payload==dict(model=CONFIG['model']['tag'],messages=[dict(role='system',content=CONFIG['prompt']),dict(role='user',content=d.wording.canonical(dict(PROJECTION.fields)))],format=CONFIG['output_schema'],**CONFIG['generation'])
    text=json.dumps(r)
    assert CONFIG['prompt'] not in text and PROJECTION.fields['subject'] not in text
    assert not any(key in payload['messages'][1]['content'] for key in ('WC01-1','reference','variant','group'))
    assert r['limits']==d.old.setup()[0]['limits']
    assert sha256((d.ROOT/d.CONFIG).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==d.CONFIG_SHA


@pytest.mark.parametrize('fault',['write','fsync','replace'])
def test_atomic_report_cleanup_and_old_reports_untouched(monkeypatch,tmp_path,fault):
    mocked(monkeypatch);r=d.run();monkeypatch.setattr(d,'ROOT',tmp_path)
    path=tmp_path/d.save(r);prior=path.read_bytes()
    def fail(*a,**k):raise OSError('private fs')
    if fault=='write':
        real=Path.open
        class Broken:
            def __init__(self,f):self.f=f
            def __enter__(self):return self
            def __exit__(self,*a):self.f.close()
            def write(self,v):self.f.write(v[:20]);fail()
        def opening(p,*a,**k):
            f=real(p,*a,**k)
            return Broken(f) if p.name.endswith('.tmp') else f
        monkeypatch.setattr(Path,'open',opening)
    else:monkeypatch.setattr(os,'fsync' if fault=='fsync' else 'replace',fail)
    with pytest.raises(OSError):d.save(r)
    assert path.read_bytes()==prior and not list(tmp_path.rglob('*.tmp'))
    assert len(list((tmp_path/d.LOCAL).iterdir()))==1


@pytest.mark.parametrize('shell_name',['powershell','pwsh'])
@pytest.mark.parametrize('scenario',['success','partial','read_error','clipboard_error','version_bad','bad_commit'])
@pytest.mark.skipif(sys.platform!='win32',reason='Native Restricted stdin workflow, no script-file execution')
def test_native_restricted_interactive_stdin_mocked(shell_name,scenario):
    import shutil
    shell=shutil.which(shell_name)
    assert shell, 'Native Windows CI must execute both shells'
    text=(d.ROOT/'docs/single-email-runtime-diagnostic-v2.md').read_text(encoding='utf-8')
    block=re.search(r'```powershell\n(.*?)\n```',text,re.S).group(1)
    assert '.ps1' not in block and 'Set-ExecutionPolicy' not in block and 'Bypass' not in block
    # The registration placeholders are replaced only before the documentation
    # pins its already-existing runtime commit. Final runs use its real pins.
    block=block.replace('APPROVED_RUNTIME_COMMIT','a'*40).replace('APPROVED_RUNTIME_TREE','b'*40)
    mocks=r'''
    function Get-ExistingPython { 'fake-python' }
    function git {
        $global:LASTEXITCODE=0
        if ($args[0] -eq 'init') {
            $null=New-Item -ItemType Directory -Path $diagRoot
            $global:Owned=$diagRoot
        }
        if ($args -contains 'rev-parse') {
            if ($args[-1] -eq 'HEAD') {
                if ($global:Scenario -eq 'bad_commit') { '0'*40 } else { $diagCommit }
            } else { $diagTree }
        }
        if ($args -contains 'status') { $global:Gate=$true }
    }
    function Invoke-ApprovedPython {
        param($Python,$Purpose)
        if (-not $global:Gate) { throw 'python_before_approval' }
        if ($Purpose -eq 'version') {
            $global:Probes++
            $v=if ($global:Scenario -eq 'version_bad') { '[3,12,0]' } else { '[3,12,10]' }
            return [pscustomobject]@{Output=$v;Code=0}
        }
        $global:Chats++
        $status=if($global:Scenario -eq 'partial'){'partial'}else{'complete'}
        $exitCode=if($global:Scenario -eq 'partial'){2}elseif($global:Scenario -eq 'read_error'){1}else{0}
        $data=@{ workflow_exit_code=$exitCode; report_read_verified=($exitCode -ne 1); report=@{run_status=$status;root_cause='unknown';result=@{telemetry=@{load_duration=80000000000;prompt_eval_cached_count=64};telemetry_validation=@{load_duration='validated'}};requests=@(@{phases=@{connect=@{completed=$true;elapsed_seconds=0.1}}})}} | ConvertTo-Json -Depth 15
        [pscustomobject]@{Output=$data;Code=$exitCode}
    }
    function Set-Clipboard {
        param($Value,$ErrorAction)
        $global:Copies++
        if ($global:Scenario -eq 'clipboard_error') {throw 'mock_clipboard_failure'}
        $global:Copied=$Value
    }
'''
    block=block.replace('    # MOCK_BOUNDARY: native CI substitutes only process/Git/clipboard boundaries here.',mocks)
    prelude=r'''
[Console]::InputEncoding=New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$global:Chats=0; $global:Probes=0; $global:Copies=0; $global:Copied=''; $global:Gate=$false; $global:Owned=$null
$original=(Get-Location).Path
$encoding=$OutputEncoding.CodePage
$console=[Console]::OutputEncoding.CodePage
$preference=$ErrorActionPreference
# Restricted blocks the Security module manifest autoload in Windows PowerShell5.1.
# Import the installed binary cmdlet module, not a script, without changing policy.
if ($PSVersionTable.PSEdition -eq 'Desktop') {
    # Desktop ships this strong-named framework assembly in the GAC, not PSHOME.
    $security=[System.Reflection.Assembly]::Load('Microsoft.PowerShell.Security, Version=3.0.0.0, Culture=neutral, PublicKeyToken=31bf3856ad364e35')
    Import-Module -Assembly $security -ErrorAction Stop
} else {
    Import-Module (Join-Path $PSHOME 'Microsoft.PowerShell.Security.dll') -ErrorAction Stop
}
$policy=Get-ExecutionPolicy -ErrorAction Stop
$printed=New-Object System.Collections.Generic.List[string]
$failed=$false
'''
    program=prelude+"\n$global:Scenario='"+scenario+"'\ntry {\n"+block+"\n | ForEach-Object { $printed.Add(\"$_\") }\n} catch {$failed=$true}\n"
    # Pipe on the same statement line: Windows PowerShell5.1 has no leading-pipe syntax.
    program=program.replace('}\n | ForEach-Object','} | ForEach-Object')
    program+=r'''
$restored=(Get-Location).Path -eq $original -and $encoding -eq $OutputEncoding.CodePage -and $console -eq [Console]::OutputEncoding.CodePage -and $preference -eq $ErrorActionPreference
if($global:Owned){Remove-Item -LiteralPath $global:Owned -Force}
@{policy="$policy";chats=$global:Chats;probes=$global:Probes;copies=$global:Copies;copied=$global:Copied;printed=($printed -join "`n");failed=$failed;restored=$restored} | ConvertTo-Json -Depth 15 -Compress
'''
    result=subprocess.run([shell,'-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Restricted','-Command','-'],input=program+'\n\n',text=True,encoding='utf-8',capture_output=True,timeout=40,env=dict(os.environ,TERM='dumb'))
    cleaned=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',result.stdout)
    rows=[line for line in cleaned.splitlines() if line.startswith('{')]
    assert result.returncode==0 and rows, result.stdout+result.stderr
    value=json.loads(rows[-1])
    assert value['policy']=='Restricted' and value['restored'], json.dumps(value)+result.stderr
    assert value['chats']==(0 if scenario in ('bad_commit','version_bad') else 1)
    assert value['probes']==(0 if scenario=='bad_commit' else 1)
    assert value['copies']==1 and value['failed']==(scenario!='success')
    if value['chats']:
        assert '80000000000' in value['printed'] and 'phases' in value['printed']
        if scenario!='clipboard_error': assert '80000000000' in value['copied']
