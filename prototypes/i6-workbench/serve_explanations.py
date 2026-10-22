"""I6 only: bounded authorized fictional explanations over unchanged I4b writes."""
import argparse
from pathlib import Path
import re
import sys
from urllib.parse import parse_qsl

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'prototypes/i5-workbench'))
import serve_information as i5
from family_os._pending_explanations import ExplanationService, CONTRACT_VERSION

i4b,i2=i5.i4b,i5.i2


class Workbench(i4b.Workbench):
    def __init__(self,lab,port):
        super().__init__(lab,port)
        self.explanations=ExplanationService(self.tasks,synthetic_only=True)
        raw,mime=self.assets['/']
        self.assets['/']=(raw.replace(b'<script src="/workbench.js"',b'<script src="/explanations.js" defer></script><script src="/workbench.js"'),mime)
        self.assets['/explanations.js']=((Path(__file__).parent/'explanations.js').read_bytes(),'text/javascript; charset=utf-8')

    def dispatch(self,bearer,key,now,path,value):
        if path=='/api/pending/preview':
            if (set(value)!={'id','revision'} or type(value['revision']) is not int
                    or not 1<=value['revision']<=1000000):raise i2.Unavailable()
            return self.pending_preview(bearer,key,now,value['id'],expected_revision=value['revision'])
        return super().dispatch(bearer,key,now,path,value)

    def allows_query(self,env):
        return (env.get('PATH_INFO')=='/api/pending/explanation' and env.get('REQUEST_METHOD')=='GET') or super().allows_query(env)

    def read(self,env):
        if env.get('PATH_INFO')!='/api/pending/explanation':return super().read(env)
        raw=env.get('QUERY_STRING','');uri='/api/pending/explanation?'+raw
        if (type(raw) is not str or len(raw)>100 or re.fullmatch(r'[a-z0-9_=&-]+',raw) is None
                or env.get('REQUEST_URI',uri)!=uri or env.get('HTTP_SEC_FETCH_SITE')!='same-origin'
                or env.get('HTTP_X_SAMAS_INTENT')!='local-session' or env.get('HTTP_ACCEPT')!='application/json'
                or env.get('CONTENT_LENGTH','') not in ('','0') or env.get('CONTENT_TYPE','')
                or env.get('HTTP_TRANSFER_ENCODING') is not None or env.get('HTTP_CONTENT_ENCODING') is not None
                or any(k.startswith('HTTP_X_') and k!='HTTP_X_SAMAS_INTENT' for k in env)):raise i2.Unavailable()
        pairs=parse_qsl(raw,keep_blank_values=True,strict_parsing=True,max_num_fields=2)
        if len(pairs)!=2 or len(dict(pairs))!=2 or set(dict(pairs))!={'id','revision'}:raise i2.Unavailable()
        values=dict(pairs)
        if (re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',values['id']) is None
                or re.fullmatch(r'[1-9][0-9]{0,5}|1000000',values['revision']) is None):raise i2.Unavailable()
        with self.lab.lock:
            row=self.explanations.read(self._bearer(env),values['id'],int(values['revision']))
            self.lab._now()
            # Explicit safe fields; no ORM/dataclass dump or private provenance.
            body=i4b.i4.encode(dict(schema=CONTRACT_VERSION,synthetic_only=True,
                id=row.id,revision=row.revision,generation=row.generation,definition=row.definition,
                source_kind='structured-fictional-input',step=row.step,
                supported_date=None if row.supported_date is None else row.supported_date.isoformat(),
                action=row.action.value,reasons=[r.value for r in row.reasons],safety=row.safety,can_accept=row.can_accept))
            if len(body)>4096:raise i2.Unavailable()
            return body


def main():
    parser=argparse.ArgumentParser(description='I6 authorized fictional Pending explanations; no real accounts',allow_abbrev=False)
    parser.add_argument('--synthetic-only',action='store_true',required=True)
    args=parser.parse_args()
    try:
        with i2.disposable(synthetic_only=args.synthetic_only) as lab:
            coordinator=i5.initialize(lab);app=Workbench(lab,1)
            try:
                server,app,thread=i2.serve(lab,application=app)
                print('I6 explanations enabled — fictional evidence only, not verified real-world facts.')
                i5.interact(lab,server,app,thread,coordinator)
            finally:app.close()
    except (KeyboardInterrupt,EOFError):pass
    except Exception:parser.exit(1,'Fictional explanation lab unavailable. No private details are logged.\n')


if __name__=='__main__':main()
