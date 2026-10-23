"""Independent launch-contract draft. No live authority is installed or issued."""
from hashlib import sha256
import ntpath
import re
import subprocess
import sys
import time

from experiments import email_artifact_control as runner

PINS = {
    'config': runner.CONFIG.as_posix(),
    'runner': 'experiments/email_artifact_control.py',
    'launcher': 'experiments/email_artifact_launch.py',
    'windows_gate': 'docs/email-artifact-launch-windows-template.txt',
}
NAMESPACE = runner.LOCAL.as_posix()
PARAMETERS = {'A':'4.2B', 'B':'8.2B'}
# This is not a configurable environment variable or caller-provided digest.
# Installing an external approval/activation mechanism requires a later review.
_LIVE_AUTHORITY = None
CODES = ('execution_not_frozen', 'authority_not_installed', 'contract_invalid',
         'checkout_mismatch', 'file_pin_mismatch', 'interpreter_mismatch',
         'environment_unverified', 'predecessor_invalid', 'metadata_route_rejected',
         'metadata_failed')


class Rejected(ValueError):
    def __init__(self, code='contract_invalid'):
        self.code = code if code in CODES else 'contract_invalid'
        super().__init__(self.code)


def require(ok, code='contract_invalid'):
    if not ok: raise Rejected(code)


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected))


def hex_value(value, size):
    return type(value) is str and re.fullmatch('[0-9a-f]{'+str(size)+'}', value) is not None


def record_sha(record):
    return sha256(runner.wording.canonical(record).encode('utf-8')).hexdigest()


def file_sha(path):
    raw = runner.read_bounded(path,65536).replace(b'\r\n',b'\n')
    require(b'\r' not in raw, 'file_pin_mismatch')
    return sha256(raw).hexdigest()


def require_live_launch():
    """All supported live entries stop before socket/claim. Never mint a permit."""
    config,_,_ = runner.setup()
    require(config['execution_freeze'] is not None, 'execution_not_frozen')
    require(_LIVE_AUTHORITY is not None, 'authority_not_installed')
    # No implementation for consuming a live authority is delivered by this draft.
    raise Rejected('authority_not_installed')


def models():
    config,_,_ = runner.setup()
    return {arm:dict(tag=m['tag'],digest=m['digest'],format='gguf',family=m['family'],
                    parameter_size=PARAMETERS[arm],quantization='Q4_K_M',
                    capabilities=['completion','thinking']) for arm,m in config['models'].items()}


def validate_release(release):
    keys(release,('schema','experiment','commit','tree','pins','interpreter',
                  'runtime_version','models','report_namespace','hardware'))
    require(release['schema']=='email-launch-release-v1' and release['experiment']==runner.EXPERIMENT)
    require(hex_value(release['commit'],40) and hex_value(release['tree'],40))
    keys(release['pins'],PINS)
    require(all(hex_value(v,64) for v in release['pins'].values()))
    keys(release['interpreter'],('executable','version','platform'))
    executable=release['interpreter']['executable']
    require(type(executable) is str and len(executable)<=512 and re.fullmatch(r'[A-Za-z]:\\[^\r\n\x00]+\\python\.exe',executable,re.I) is not None)
    require(not any(part in ('.','..') for part in executable.split('\\')))
    version=release['interpreter']['version']
    require(type(version) is list and all(type(n) is int for n in version)
            and version==[3,12,10] and release['interpreter']['platform']=='win32')
    require(release['runtime_version']=='0.40.6' and release['models']==models())
    require(release['report_namespace']==NAMESPACE)
    hardware=release['hardware']
    keys(hardware,('gpu','vram_total_mib','driver','ram_total_bytes'))
    require(hardware['gpu']=='NVIDIA GeForce RTX 2060 with Max-Q Design'
            and type(hardware['vram_total_mib']) is int and hardware['vram_total_mib']==6144
            and type(hardware['driver']) is str and re.fullmatch(r'[0-9]{1,4}(?:\.[0-9]{1,4}){1,3}',hardware['driver'])
            and type(hardware['ram_total_bytes']) is int and 0<hardware['ram_total_bytes']<2**63)
    return release


def validate_decision(release, decision):
    keys(decision,('schema','experiment','release_sha256','decision_id','decider',
                   'decision','phase_authorization','mode','arm','report_namespace','previous'))
    require(decision['schema']=='email-launch-stage-v1' and decision['experiment']==runner.EXPERIMENT)
    require(decision['release_sha256']==record_sha(release) and hex_value(decision['decision_id'],32))
    require(decision['decider']=='Lisa' and decision['decision']=='authorize_single_stage')
    mode,arm=decision['mode'],decision['arm']
    require((mode,arm) in runner.STAGES and decision['phase_authorization']==mode)
    require(decision['report_namespace']==NAMESPACE)
    previous=decision['previous']; index=runner.STAGES.index((mode,arm))
    require(type(previous) is list and len(previous)==index)
    ids=[]
    for receipt,(m,a) in zip(previous,runner.STAGES[:index],strict=True):
        keys(receipt,('run_id','sha256','mode','arm'))
        require(hex_value(receipt['run_id'],32) and hex_value(receipt['sha256'],64))
        require((receipt['mode'],receipt['arm'])==(m,a))
        ids.append(receipt['run_id'])
    require(len(ids)==len(set(ids)))
    return decision


def git_read(*args):
    p=subprocess.run(['git',*args],cwd=runner.ROOT,check=True,stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL,timeout=10)
    require(len(p.stdout)<=65536,'checkout_mismatch')
    return p.stdout.decode('ascii').strip()


def validate_host(release, host):
    keys(host,('executable','version','platform','gpu','vram_total_mib','driver','ram_total_bytes'))
    expected=release['interpreter']
    require(type(host['executable']) is str and ntpath.normcase(host['executable'])==ntpath.normcase(expected['executable'])
            and type(host['version']) is list and all(type(n) is int for n in host['version'])
            and host['version']==expected['version'] and host['platform']==expected['platform'], 'interpreter_mismatch')
    require(host['gpu']=='NVIDIA GeForce RTX 2060 with Max-Q Design'
            and type(host['vram_total_mib']) is int and host['vram_total_mib']==6144
            and type(host['driver']) is str and re.fullmatch(r'[0-9]{1,4}(?:\.[0-9]{1,4}){1,3}',host['driver'])
            and type(host['ram_total_bytes']) is int and 0<host['ram_total_bytes']<2**63,
            'environment_unverified')
    require(all(host[k]==v for k,v in release['hardware'].items()),'environment_unverified')


def prepare_stage(release, decision, host, *, git=git_read, reader=None):
    """Offline consistency checks, not Lisa authentication or an execution permit.

    host is explicitly supplied evidence, not independently measured by this API.
    No network, model selection, claim, scan, save or Python process is started.
    """
    try:
        validate_release(release); validate_decision(release,decision); validate_host(release,host)
        require(git('rev-parse','HEAD')==release['commit'] and git('rev-parse','HEAD^{tree}')==release['tree'], 'checkout_mismatch')
        require(git('status','--porcelain','--untracked-files=all')=='', 'checkout_mismatch')
        require(git('merge-base','--is-ancestor',runner.FREEZE,'HEAD')=='', 'checkout_mismatch')
        require(all(file_sha(runner.ROOT/path)==release['pins'][name] for name,path in PINS.items()), 'file_pin_mismatch')
        read=runner.read_report if reader is None else reader
        execution=dict(commit=release['commit'],tree=release['tree'],kind='reviewed_manual')
        reports=[]
        for receipt in decision['previous']:
            r=read(receipt['run_id'],receipt['sha256'])
            runner.validate_report(r)
            require(sha256(runner.encoded(r)).hexdigest()==receipt['sha256'],'predecessor_invalid')
            require(r['implementation_lf_sha256']==release['pins']['runner'] and r['config_lf_sha256']==release['pins']['config'], 'predecessor_invalid')
            reports.append(r)
        runner.prerequisites(decision['mode'],decision['arm'],reports,execution)
        return dict(operation='prepare',ready_for_review=True,execution_authorized=False,
                    release_sha256=record_sha(release),decision_sha256=record_sha(decision),
                    mode=decision['mode'],arm=decision['arm'],error_code=None)
    except Rejected as exc:
        code=exc.code
    except (Exception,KeyboardInterrupt):
        code='predecessor_invalid' if isinstance(decision,dict) and decision.get('previous') else 'contract_invalid'
    return dict(operation='prepare',ready_for_review=False,execution_authorized=False,error_code=code)


class MetadataTransport(runner.compat.old.Transport):
    """Fixed read-only numeric-loopback transport, separately closed from generation."""
    def __init__(self, stage_deadline=None):
        config,baseline,_=runner.setup()
        self.targets=config['models']
        self.config=dict(baseline,model=self.targets['A'])
        self.limits=baseline['limits']
        require(stage_deadline is None or type(stage_deadline) in (int,float)
                and -float('inf')<stage_deadline<float('inf'))
        # A future stage shares its original deadline; no extra 25s allowance.
        self.deadline=min(time.monotonic()+25,stage_deadline) if stage_deadline is not None else time.monotonic()+25
        self.allowed=set();self.chat_attempts=0;self.requests=[]

    def request(self,method,path,value=None):
        require((method,path) in {('GET','/api/version'),('GET','/api/tags'),('GET','/api/ps'),('POST','/api/show')},'metadata_route_rejected')
        if method=='GET': require(value is None,'metadata_route_rejected')
        else:
            require(type(value) is dict and set(value)=={'model','verbose'} and value['verbose'] is False,'metadata_route_rejected')
            matches=[m for m in self.targets.values() if value['model']==m['tag']]
            require(len(matches)==1,'metadata_route_rejected')
            self.config=dict(self.config,model=matches[0])
        require_live_launch()  # Before HTTPConnection, including metadata-only calls.
        return runner.clone(runner.compat.old.Transport.request)(self,method,path,value)


def _inventory(request):
    """Bounded finite projection of metadata. Inject Mock request in offline tests.

    This function neither creates a connection nor issues a permission. A live
    caller can only supply MetadataTransport.request, whose entry remains closed.
    """
    try:
        require(request('GET','/api/version').get('version')=='0.40.6','environment_unverified')
        tags=request('GET','/api/tags').get('models')
        require(type(tags) is list and len(tags)<=128 and all(type(m) is dict for m in tags),'environment_unverified')
        expected=models(); output={}
        for arm,m in expected.items():
            matches=[v for v in tags if v.get('name')==m['tag'] or v.get('model')==m['tag']]
            require(len(matches)==1 and matches[0].get('digest')==m['digest']
                    and all(matches[0].get(k,m['tag'])==m['tag'] for k in ('name','model')),'environment_unverified')
            show=request('POST','/api/show',{'model':m['tag'],'verbose':False})
            details,info,caps=show.get('details'),show.get('model_info'),show.get('capabilities')
            require(type(details) is dict and type(info) is dict and type(caps) is list and len(caps)<=32,'environment_unverified')
            require(details.get('format')=='gguf' and details.get('family')==info.get('general.architecture')==m['family']
                    and details.get('parameter_size')==m['parameter_size'] and details.get('quantization_level')=='Q4_K_M'
                    and all(type(c) is str and re.fullmatch('[a-z_]{1,32}',c) for c in caps)
                    and len(caps)==len(set(caps)) and {'completion','thinking'}<=set(caps),'environment_unverified')
            output[arm]=m  # Never retain template/system/license or unknown raw values.
        residents=request('GET','/api/ps').get('models')
        require(type(residents) is list and len(residents)<=128 and all(type(m) is dict for m in residents),'environment_unverified')
        selected=[]; seen=set()
        for value in residents:
            matches=[(a,m) for a,m in expected.items() if value.get('name')==m['tag'] or value.get('model')==m['tag']]
            require(len(matches)==1,'environment_unverified')
            arm,m=matches[0]
            require(arm not in seen and value.get('digest')==m['digest']
                    and all(value.get(k,m['tag'])==m['tag'] for k in ('name','model')),'environment_unverified')
            seen.add(arm)
            finite={k:value.get(k) for k in ('size','size_vram','context_length')}
            require(all(v is None or type(v) is int and 0<=v<2**63 for v in finite.values()),'environment_unverified')
            selected.append(dict(arm=arm,**finite))
        return dict(operation='environment',verified_metadata=True,execution_authorized=False,
                    runtime_version='0.40.6',models=output,resident_count=len(residents),
                    residency=selected,resource_fit_verified=False,error_code=None)
    except Rejected as exc:
        code=exc.code
    except (Exception,KeyboardInterrupt):
        code='metadata_failed'
    return dict(operation='environment',verified_metadata=False,execution_authorized=False,
                runtime_version=None,models=None,resident_count=None,residency=None,
                resource_fit_verified=False,error_code=code)


def inspect_environment():
    try:
        require_live_launch()
        return _inventory(MetadataTransport().request)
    except Rejected as exc:
        return dict(operation='environment',verified_metadata=False,execution_authorized=False,
                    error_code=exc.code)
    except (Exception,KeyboardInterrupt):
        return dict(operation='environment',verified_metadata=False,execution_authorized=False,
                    error_code='execution_not_frozen')


def launch(*args,**kwargs):
    # Deliberately no real dispatch/authorization issuer in this local draft.
    try:
        require_live_launch()
    except Rejected as exc:
        return dict(operation='launch',execution_authorized=False,error_code=exc.code)
    except (Exception,KeyboardInterrupt):
        return dict(operation='launch',execution_authorized=False,error_code='execution_not_frozen')
    raise Rejected('authority_not_installed')


def main(argv=None):
    # Default is offline, uses only current pinned public files.
    try:
        args=list(sys.argv[1:] if argv is None else argv)
        require(args in ([],['check']))
        runner.setup()
        value=dict(operation='offline_check',execution_authorized=False,error_code=None)
    except (Exception,KeyboardInterrupt):
        value=dict(operation='offline_check',execution_authorized=False,error_code='contract_invalid')
    print(runner.json.dumps(value,sort_keys=True))
    return 1 if value['error_code'] else 0


if __name__=='__main__':
    raise SystemExit(main())
