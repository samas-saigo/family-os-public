"""I7 opt-in fictional personal annotations over T1 and the shared receipt gate."""
import argparse
from pathlib import Path
import re
import sys
from urllib.parse import parse_qsl

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'prototypes/i6-workbench'))
import serve_explanations as i6

i5,i2,i4b=i6.i5,i6.i2,i6.i4b
t=i4b.t
PERSONAL=(t.Operation.REVIEW,t.Operation.DEFER,t.Operation.NEEDS_INFORMATION)
PAGE_SCHEMA='i7-personal-pending-page-v1'
PREVIEW_SCHEMA='i7-personal-preview-v1'


class Workbench(i6.Workbench):
    personal_operations=PERSONAL
    page_schema=PAGE_SCHEMA
    result_schema='i7-write-result-v1'
    pending_states=('all','unhandled','viewed','deferred','needs-information')
    dispositions=('active','deferred','needs-information')
    write_paths=i6.Workbench.write_paths+('/api/pending/review-preview','/api/pending/review-confirm','/api/pending/review-outcome')

    def __init__(self,lab,port):
        super().__init__(lab,port)
        raw,mime=self.assets['/']
        raw=raw.replace(b'</head>',b'<link rel="stylesheet" href="/reviews.css"></head>')
        self.assets['/reviews.css']=((Path(__file__).parent/'reviews.css').read_bytes(),'text/css; charset=utf-8')
        self.assets['/']=(raw.replace(b'<script src="/workbench.js"',b'<script src="/reviews.js" defer></script><script src="/workbench.js"'),mime)
        self.assets['/reviews.js']=((Path(__file__).parent/'reviews.js').read_bytes(),'text/javascript; charset=utf-8')

    def response(self,result,receipt,*,key=None):
        entry=self.receipts.get(key,{}).get(receipt)
        return i4b.i4.encode(dict(schema=self.result_schema,synthetic_only=True,outcome=result.outcome.value,
            receipt=receipt,operation=None if entry is None else entry.command.operation.value))

    def personal_preview(self,bearer,key,now,value):
        if (set(value)!={'id','revision','operation'} or type(value['operation']) is not str
                or type(value['revision']) is not int):raise i2.Unavailable()
        operation=t.Operation(value['operation'])
        if operation not in self.personal_operations:raise i2.Unavailable()
        owned=self.guard_preview(bearer,key,now)
        command=self.tasks.prepare_review(bearer,value['id'],operation,value['revision'])
        receipt=self.issue(key,owned,command,self.lab._now())
        return i4b.i4.encode(dict(schema=PREVIEW_SCHEMA,synthetic_only=True,id=command.resource_id,
            revision=command.expected_revision,operation=operation.value,receipt=receipt))

    def dispatch(self,bearer,key,now,path,value):
        if path=='/api/pending/review-preview':return self.personal_preview(bearer,key,now,value)
        if path in ('/api/pending/review-confirm','/api/pending/review-outcome'):
            entry=self.receipts.get(key,{}).get(value.get('receipt')) if type(value.get('receipt')) is str else None
            if entry is None or entry.command.operation not in self.personal_operations:raise i2.Unavailable()
            # One coordinator/attempt fence for ACCEPT, EDIT and personal records.
            route='/api/pending/accept' if path.endswith('confirm') else '/api/pending/outcome'
            return i4b.i4.Workbench.dispatch(self,bearer,key,now,route,value)
        return super().dispatch(bearer,key,now,path,value)

    def pending_json(self,r):
        # An older client must never silently reinterpret an I8 disposition.
        if r.disposition not in self.dispositions:raise i2.Unavailable()
        return dict(id=r.id,revision=r.revision,step=None if r.step is None else r.step.value,
            supported_date=None if r.supported_date is None else r.supported_date.isoformat(),
            can_accept=r.can_accept and r.step is not None,can_review=r.can_review,
            reviewed=r.reviewed,disposition=r.disposition)

    def read(self,env):
        if env.get('PATH_INFO')!='/api/pending':return super().read(env)
        raw=env.get('QUERY_STRING','');uri='/api/pending'+('?' +raw if raw else '')
        if (type(raw) is not str or len(raw)>128 or (raw and re.fullmatch('[a-z0-9=&-]+',raw) is None)
                or env.get('REQUEST_URI',uri)!=uri or env.get('HTTP_SEC_FETCH_SITE')!='same-origin'
                or env.get('HTTP_X_SAMAS_INTENT')!='local-session' or env.get('HTTP_ACCEPT')!='application/json'
                or env.get('CONTENT_LENGTH','') not in ('','0') or env.get('CONTENT_TYPE','')
                or env.get('HTTP_TRANSFER_ENCODING') is not None or env.get('HTTP_CONTENT_ENCODING') is not None
                or any(k.startswith('HTTP_X_') and k!='HTTP_X_SAMAS_INTENT' for k in env)):raise i2.Unavailable()
        pairs=parse_qsl(raw,keep_blank_values=True,strict_parsing=True,max_num_fields=4)
        if len(dict(pairs))!=len(pairs):raise i2.Unavailable()
        values=dict(pairs)
        state=t.PendingState(values.pop('state','all'))
        if state.value not in self.pending_states:raise i2.Unavailable()
        limit,offset,step=i4b.i3.query('&'.join(k+'='+v for k,v in values.items()))
        with self.lab.lock:
            page=self.tasks.pending(self._bearer(env),limit=limit,offset=offset,step=step,pending_state=state)
            rows=[self.pending_json(r) for r in page.items]
            self.lab._now()
            return i4b.i4.encode(dict(schema=self.page_schema,synthetic_only=True,query=dict(state=state.value,
                step=None if step is None else step.value),pagination=dict(limit=limit,offset=offset),
                pending=dict(items=rows,total=page.total,has_more=page.has_more)))


def main():
    parser=argparse.ArgumentParser(description='I7 personal Pending handling; fictional local testing only',allow_abbrev=False)
    parser.add_argument('--synthetic-only',action='store_true',required=True)
    args=parser.parse_args()
    try:
        with i2.disposable(synthetic_only=args.synthetic_only) as lab:
            coordinator=i5.initialize(lab);app=Workbench(lab,1)
            try:
                server,app,thread=i2.serve(lab,application=app)
                print('I7 personal handling enabled — no real data, global dismissal or external activity.')
                i5.interact(lab,server,app,thread,coordinator)
            finally:app.close()
    except (KeyboardInterrupt,EOFError):pass
    except Exception:parser.exit(1,'Fictional review lab unavailable. No private details are logged.\n')


if __name__=='__main__':main()
