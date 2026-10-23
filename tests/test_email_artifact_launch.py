"""Local launch draft: explicit fake HTTP/Git/host facts, never real sockets."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import socket
import io
import shutil
import subprocess

import pytest
from experiments import email_artifact_control as d
from experiments import email_artifact_launch as launch
from test_email_artifact_control import HTTP, MockTransport, CONFIG, BASELINE, CORPORA


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*a,**k): pytest.fail('Real socket or old fixture selector forbidden')
    monkeypatch.setattr(socket,'create_connection',deny)
    monkeypatch.setattr(socket.socket,'connect',deny)
    monkeypatch.setattr(d.wording,'load',deny)
    monkeypatch.setattr(d.parent,'setup',deny)
    monkeypatch.setattr(d.prior,'setup',deny)


def release():
    return dict(schema='email-launch-release-v1',experiment=d.EXPERIMENT,commit='a'*40,tree='b'*40,
        pins={key:launch.file_sha(d.ROOT/path) for key,path in launch.PINS.items()},
        interpreter=dict(executable=r'C:\Synthetic\Python312\python.exe',version=[3,12,10],platform='win32'),
        runtime_version='0.40.6',models=launch.models(),report_namespace=launch.NAMESPACE,
        hardware=dict(gpu='NVIDIA GeForce RTX 2060 with Max-Q Design',vram_total_mib=6144,driver='610.91',ram_total_bytes=32*1024**3))


def decision(r,mode='smoke',arm='A',previous=()):
    return dict(schema='email-launch-stage-v1',experiment=d.EXPERIMENT,release_sha256=launch.record_sha(r),
        decision_id='c'*32,decider='Lisa',decision='authorize_single_stage',phase_authorization=mode,
        mode=mode,arm=arm,report_namespace=launch.NAMESPACE,previous=list(previous))


def host(r):
    return dict(executable=r['interpreter']['executable'],version=[3,12,10],platform='win32',
                **r['hardware'])


@pytest.fixture
def isolated_publication_root(publication_root):
    source=Path(d.__file__).resolve().parents[1]
    for relative in launch.PINS.values():
        target=publication_root/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/relative,target)
    return publication_root


def git_for(r, fault=None):
    def git(*args):
        if args==('rev-parse','HEAD'): return '0'*40 if fault=='commit' else r['commit']
        if args==('rev-parse','HEAD^{tree}'): return '0'*40 if fault=='tree' else r['tree']
        if args[0]=='status': return ' M private_path' if fault=='dirty' else ''
        assert args==('merge-base','--is-ancestor',d.FREEZE,'HEAD')
        if fault=='ancestry': raise OSError('private_detail')
        return ''
    return git


def test_default_offline_and_all_supported_live_entries_zero_network(monkeypatch,capsys,isolated_publication_root):
    http=HTTP(monkeypatch)
    assert launch.main([])==0 and 'offline_check' in capsys.readouterr().out
    assert launch.main(['launch'])==1 and 'contract_invalid' in capsys.readouterr().out
    assert launch.inspect_environment()['error_code']=='execution_not_frozen'
    assert launch.launch(release(),decision(release()))['execution_authorized'] is False
    native=d.Transport(CONFIG,BASELINE,CORPORA['smoke'][0],'A',d.time.monotonic()+120)
    for method,path,body in [('GET','/api/version',None),('POST','/api/chat',native.payload(d.engine.EmailMetadata(CORPORA['smoke'][0]['input'])))]:
        with pytest.raises(launch.Rejected): native.request(method,path,body)
    with pytest.raises(launch.Rejected): launch.MetadataTransport().request('GET','/api/tags')
    result=d.collect('smoke','A',execution=dict(commit='a'*40,tree='b'*40,kind='reviewed_manual'))
    assert result['report'] is None and http.calls==[]
    # Explicitly passing the production class as an alleged Mock cannot query.
    result=d.collect('smoke','A',execution=dict(commit='a'*40,tree='b'*40,kind='offline_mock'),client_factory=d.Transport)
    assert result['report'] is None or result['report']['attempted']==0
    assert http.calls==[]


@pytest.mark.parametrize('value',[None,{},True,'a'*64,dict(approved=True)])
def test_nonnull_or_digest_string_is_not_authority(monkeypatch,value):
    original=d.setup
    def changed():
        c,b,cs=original(); return dict(c,execution_freeze=value),b,cs
    monkeypatch.setattr(d,'setup',changed)
    http=HTTP(monkeypatch)
    with pytest.raises(launch.Rejected): launch.require_live_launch()
    assert launch.launch()['execution_authorized'] is False and http.calls==[]


def test_even_replacing_an_authority_object_does_not_install_a_dispatch(monkeypatch):
    original=d.setup
    def changed():
        c,b,cs=original();return dict(c,execution_freeze=dict(approved=True)),b,cs
    monkeypatch.setattr(d,'setup',changed);monkeypatch.setattr(launch,'_LIVE_AUTHORITY',object())
    http=HTTP(monkeypatch)
    assert launch.launch()['execution_authorized'] is False and http.calls==[]


def test_complete_contract_can_only_prepare_not_authorize(monkeypatch):
    HTTP(monkeypatch);r=release();s=decision(r)
    result=launch.prepare_stage(r,s,host(r),git=git_for(r))
    assert result['ready_for_review'] and result['execution_authorized'] is False
    assert result['release_sha256']==launch.record_sha(r)
    text=d.wording.canonical(result)
    assert r['interpreter']['executable'] not in text and 'Synthetic' not in text
    assert launch.launch(result)['execution_authorized'] is False


@pytest.mark.parametrize('fault',['commit','tree','dirty','ancestry','config','runner','launcher','windows_gate','executable','version','version_type','platform','ram','gpu','driver','phase','decision','release_hash','namespace','extra'])
def test_wrong_contract_or_checkout_never_queries(monkeypatch,fault):
    http=HTTP(monkeypatch);r=release();s=decision(r);h=host(r)
    if fault in launch.PINS:
        r['pins'][fault]='f'*64;s=decision(r)
    elif fault=='executable': h['executable']=r'C:\Other\python.exe'
    elif fault=='version': h['version']=[3,12,0]
    elif fault=='version_type': h['version']=[3.0,12.0,10.0]
    elif fault=='platform': h['platform']='linux'
    elif fault=='ram': h['ram_total_bytes']=None
    elif fault=='gpu': h['gpu']='Other GPU'
    elif fault=='driver': h['driver']='610.92'
    elif fault=='phase': s['phase_authorization']='full'
    elif fault=='decision': s['decision']='environment_verified'
    elif fault=='release_hash': s['release_sha256']='f'*64
    elif fault=='namespace': s['report_namespace']='.local/old-run'
    elif fault=='extra': s['allow_real']=True
    value=launch.prepare_stage(r,s,h,git=git_for(r,fault))
    assert not value['ready_for_review'] and not value['execution_authorized']
    assert 'private_' not in d.wording.canonical(value) and http.calls==[]


@pytest.mark.parametrize('route', [('POST','/api/chat',{}),('POST','/api/generate',{}),
    ('GET','http://127.0.0.1:11434/api/tags',None),('GET','/api/tags',{}),
    ('POST','/api/show',dict(model='qwen3:8b',verbose=False)),
    ('POST','/api/show',dict(model='qwen3:8b-q4_K_M',verbose=True)),
    ('POST','/api/show',dict(model='qwen3:8b-q4_K_M',verbose=False,url='private_url'))])
def test_metadata_route_allowlist_before_transport(monkeypatch,route):
    http=HTTP(monkeypatch)
    with pytest.raises(launch.Rejected): launch.MetadataTransport().request(*route)
    assert http.calls==[]


def wire_inventory(monkeypatch,responder=None):
    # Simulate the post-approval wire boundary only; socket autouse guard remains.
    monkeypatch.setattr(launch,'require_live_launch',lambda:None)
    http=HTTP(monkeypatch,responder)
    value=launch._inventory(launch.MetadataTransport().request)
    return http,value


def test_metadata_fixed_five_calls_and_no_show_text_or_permission(monkeypatch):
    def extra(m,p,v,r):
        if p=='/api/show': r.update(template='private_template',system='private_system',license='private_license')
        return r
    http,value=wire_inventory(monkeypatch,extra)
    assert value['verified_metadata'] and not value['execution_authorized'] and not value['resource_fit_verified']
    assert value['resident_count']==0
    assert [(m,p) for m,p,_ in http.calls]==[('GET','/api/version'),('GET','/api/tags'),('POST','/api/show'),('POST','/api/show'),('GET','/api/ps')]
    assert [v for _,p,v in http.calls if p=='/api/show']==[dict(model=CONFIG['models'][a]['tag'],verbose=False) for a in ('A','B')]
    assert 'private_' not in d.wording.canonical(value)


@pytest.mark.parametrize('fault',['missing','duplicate','alias','digest','conflict','format','family','parameters','quantization','capability','runtime','resident_unknown','resident_conflict','resident_duplicate','exception','interrupt','oversize','timeout'])
def test_metadata_unknown_mismatch_or_failure_blocks_with_finite_output(monkeypatch,fault):
    def wrong(m,p,v,r):
        if p=='/api/version' and fault=='runtime': r['version']='0.40.7'
        if p=='/api/tags':
            if fault=='missing': r['models']=r['models'][:1]
            if fault=='duplicate': r['models'].append(deepcopy(r['models'][1]))
            if fault=='alias': r['models'][1].update(name='qwen3:8b',model='qwen3:8b')
            if fault=='digest': r['models'][1]['digest']='0'*64
            if fault=='conflict': r['models'][1]['model']='other'
        if p=='/api/show':
            fields={'format':'format','family':'family','parameters':'parameter_size','quantization':'quantization_level'}
            if fault in fields: r['details'][fields[fault]]='private_wrong'
            if fault=='capability': r['capabilities']=['completion']
            if fault=='exception': raise OSError('private_exception')
            if fault=='interrupt': raise KeyboardInterrupt()
            if fault=='timeout': raise TimeoutError('private_exception')
            if fault=='oversize': r['template']='private_value'*10000
        if p=='/api/ps' and fault.startswith('resident_'):
            a=CONFIG['models']['A']
            r['models']=[dict(name=a['tag'],digest=a['digest'])]
            if fault=='resident_unknown': r['models'][0]['name']='private_tag'
            if fault=='resident_conflict': r['models'][0]['digest']='0'*64
            if fault=='resident_duplicate': r['models']*=2
        return r
    http,value=wire_inventory(monkeypatch,wrong)
    assert not value['verified_metadata'] and value['resident_count'] is None
    assert value['error_code'] in launch.CODES and 'private_' not in d.wording.canonical(value)
    assert len(http.calls)<=5 and not any(p in ('/api/chat','/api/generate') for _,p,_ in http.calls)


def test_known_residency_is_not_unloaded_or_claimed_as_resource_fit(monkeypatch):
    def resident(m,p,v,r):
        if p=='/api/ps': r['models']=[dict(name=CONFIG['models']['A']['tag'],digest=CONFIG['models']['A']['digest'],size=3324173934,size_vram=3000000000)]
        return r
    _,value=wire_inventory(monkeypatch,resident)
    assert value['verified_metadata'] and value['resident_count']==1
    assert value['residency']==[dict(arm='A',size=3324173934,size_vram=3000000000,context_length=None)]
    assert not value['resource_fit_verified']


def test_full_needs_separate_decision_and_original_exact_predecessors(monkeypatch):
    HTTP(monkeypatch);r=release();execution=dict(commit=r['commit'],tree=r['tree'],kind='reviewed_manual')
    reports={};receipts=[]
    for i,(mode,arm) in enumerate(d.STAGES[:3]):
        # Simulated future manual report format, generated entirely by Mock HTTP.
        report=d.run(mode,arm,client_factory=MockTransport,execution=execution)
        run_id=f'{i+1:032x}';sha=sha256(d.encoded(report)).hexdigest()
        reports[(run_id,sha)]=report
        receipts.append(dict(run_id=run_id,sha256=sha,mode=mode,arm=arm))
    def reader(run_id,sha): return deepcopy(reports[(run_id,sha)])
    s=decision(r,'full','A',receipts[:2])
    assert launch.prepare_stage(r,s,host(r),git=git_for(r),reader=reader)['ready_for_review']
    smoke_decision=deepcopy(s);smoke_decision['phase_authorization']='smoke'
    assert not launch.prepare_stage(r,smoke_decision,host(r),git=git_for(r),reader=reader)['ready_for_review']
    s=decision(r,'full','B',receipts)
    assert launch.prepare_stage(r,s,host(r),git=git_for(r),reader=reader)['ready_for_review']
    for fault in ('hash','order','duplicate','execution','mock','partial','identity','namespace'):
        bad=deepcopy(s)
        if fault=='hash': bad['previous'][0]['sha256']='f'*64
        if fault=='order': bad['previous'].reverse()
        if fault=='duplicate': bad['previous'][1]['run_id']=bad['previous'][0]['run_id']
        def changed(run_id,sha):
            value=reader(run_id,sha)
            if fault=='execution': value['execution']['commit']='0'*40
            if fault=='mock': value['execution']['kind']='offline_mock'
            if fault=='partial': value['run_status']='partial'
            if fault=='identity': value['identity_verified_at_end']=False
            if fault=='namespace': value['experiment']='other_experiment'
            return value
        assert not launch.prepare_stage(r,bad,host(r),git=git_for(r),reader=changed)['ready_for_review']


def test_claim_precedes_metadata_interrupt_and_save_failure_no_retry(monkeypatch,publication_root):
    # publication_root fixture is imported explicitly below for this module.
    events=[]
    def interrupted(m,p,v,r):
        events.append(p)
        assert (d.ROOT/d.LOCAL/'claims/smoke-A').exists()
        if p=='/api/version': raise KeyboardInterrupt()
        return r
    http=HTTP(monkeypatch,interrupted)
    result=d.collect('smoke','A',execution=dict(commit='a'*40,tree='b'*40,kind='offline_mock'),client_factory=MockTransport)
    assert result['report']['identity_tainted'] and not result['report']['identity_verified_at_end']
    assert not any(p=='/api/chat' for _,p,_ in http.calls)
    count=len(http.calls)
    repeated=d.collect('smoke','A',execution=dict(commit='a'*40,tree='b'*40,kind='offline_mock'),client_factory=MockTransport)
    assert repeated['workflow_exit_code']==1 and len(http.calls)==count


def test_template_has_no_python_dispatch_or_policy_change_and_stops():
    text=(d.ROOT/launch.PINS['windows_gate']).read_text()
    assert text.rstrip().endswith("throw 'draft_only_execution_not_frozen'")
    assert 'function Test-ApprovedCheckout' in text and 'function Get-LfSha256' in text
    assert 'py -3.12' not in text and '.ps1' not in '\n'.join(l for l in text.splitlines() if not l.startswith('#'))
    assert 'Set-ExecutionPolicy' not in '\n'.join(l for l in text.splitlines() if not l.startswith('#'))
    assert '& $' not in text and 'Invoke-Expression' not in text


@pytest.mark.parametrize('fault',['redirect','gzip','header_limit','body_limit','invalid_utf8','duplicate_json'])
def test_metadata_reuses_bounded_strict_http_and_never_redirects(monkeypatch,fault):
    monkeypatch.setattr(launch,'require_live_launch',lambda:None)
    http=HTTP(monkeypatch)
    original=http.connect
    def connect(*a,**kw):
        c=original(*a,**kw);getresponse=c.getresponse
        def response():
            r=getresponse();oldheader=r.getheader
            if fault=='redirect': r.status=302
            if fault=='gzip': r.getheader=lambda k,default=None:'gzip' if k=='Content-Encoding' else oldheader(k,default)
            if fault=='header_limit': r.getheaders=lambda:[('X','x'*8193)]
            if fault=='body_limit': r.raw=io.BytesIO(b' '*65537)
            if fault=='invalid_utf8': r.raw=io.BytesIO(b'\xff')
            if fault=='duplicate_json': r.raw=io.BytesIO(b'{"models":[],"models":[]}')
            return r
        c.getresponse=response
        return c
    monkeypatch.setattr(d.parent.http.client,'HTTPConnection',connect)
    result=launch._inventory(launch.MetadataTransport().request)
    assert not result['verified_metadata'] and result['error_code']=='metadata_failed'
    assert len(http.calls)==1


def test_metadata_deadline_prevents_connect_without_retry(monkeypatch):
    monkeypatch.setattr(launch,'require_live_launch',lambda:None)
    http=HTTP(monkeypatch);t=launch.MetadataTransport();t.deadline=d.time.monotonic()-1
    with pytest.raises(d.Error): t.request('GET','/api/version')
    assert t.limits['metadata_seconds']==5 and t.limits['response_bytes']==65536
    assert http.calls==[]


def test_metadata_stage_deadline_never_extends_original_budget():
    end=d.time.monotonic()+2
    assert launch.MetadataTransport(end).deadline==end
    begin=d.time.monotonic()
    assert launch.MetadataTransport(begin+600).deadline<=d.time.monotonic()+25
    for value in (True,float('nan'),float('inf')):
        with pytest.raises(launch.Rejected): launch.MetadataTransport(value)


def test_stage_artifacts_do_not_dirty_checkout_or_hide_other_unknown_paths(tmp_path):
    def git(*args):
        return subprocess.run(['git','-C',str(tmp_path),*args],check=True,
                              stdout=subprocess.PIPE,stderr=subprocess.DEVNULL).stdout.decode()
    (tmp_path/'.gitignore').write_bytes((d.ROOT/'.gitignore').read_bytes())
    git('init','-q');git('add','.gitignore')
    git('-c','user.name=Samas Maintainer','-c','user.email=337128921+samas-saigo@users.noreply.github.com',
        'commit','-qm','synthetic test base')
    claim=tmp_path/d.LOCAL/'claims/smoke-A';claim.parent.mkdir(parents=True);claim.write_text('claimed')
    report=tmp_path/d.LOCAL/('a'*32)/'report.json';report.parent.mkdir();report.write_text('{}')
    assert git('status','--porcelain','--untracked-files=all')==''
    unknown=tmp_path/'.local/unknown/unapproved.txt';unknown.parent.mkdir();unknown.write_text('synthetic')
    assert '.local/unknown/unapproved.txt' in git('status','--porcelain','--untracked-files=all')
    assert claim.exists() and report.exists()


from test_email_artifact_control import publication_root
