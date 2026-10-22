"""I4a: explicit fictional T1 acceptance, never provider or production writes."""
import argparse
from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from secrets import token_hex
import sys

from sqlalchemy import insert

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'prototypes/i3-workbench'))
import serve_workbench as i3

i2,t=i3.i2,i3.t
from family_os.schema import source_read_grant,household_pending_item as pending,pending_member_right as right,pending_task_publication as plan

PREVIEW_SECONDS=120
MAX_RECEIPTS=16  # Per exact session, not a hidden peer's population.
PENDING_SCHEMA='i4a-pending-page-v1'
PREVIEW_SCHEMA='i4a-acceptance-preview-v1'
RESULT_SCHEMA='i4a-acceptance-result-v1'


def seed(lab):
    i3.seed(lab)
    i3.register(lab.sessions._engine,{'household':{'id':i2.HOME,'name':'Fictional Willow'},
        'source_accounts':[dict(id='i4a-shared-source',provider='fixture',owner_type='person',owner_id='i2-devon'),
            dict(id='i4a-private-source',provider='fixture',owner_type='person',owner_id='i2-devon')]})
    with i2.a.authorization_transaction(lab.sessions._engine,i2.HOME) as c:
        c.execute(insert(source_read_grant),[dict(household_id=i2.HOME,source_account_id=src,person_id='i2-'+peer,
            state='allowed',observations=True,security=True,revision=1,membership_revision=1)
            for src,peers in [('i4a-shared-source',i2.PEERS),('i4a-private-source',('devon',))] for peer in peers])
        cases=[('i4a-school','action',True,'clear','school-session',date(2036,3,14),False),
            ('i4a-visit','action',True,'clear','home-visit',None,True),
            ('i4a-question','question',False,'unknown',None,None,False),
            ('i4a-risk','action',True,'high-risk','home-visit',None,False),
            ('i4a-offer','promotion',False,'unknown',None,None,False),
            ('i4a-notice','information',False,'clear',None,None,False)]
        for resource,kind,supported,safety,step,when,private in cases:
            peers=('devon',) if private else i2.PEERS
            c.execute(insert(pending).values(household_id=i2.HOME,id=resource,
                source_account_id='i4a-private-source' if private else 'i4a-shared-source',kind=kind,
                supported=supported,safety=safety,step=step,supported_date=when,generation=1,
                evidence_fingerprint=sha256(('new-fiction-'+resource).encode()).hexdigest(),
                definition_version='i4a-fictional-v1',resolution='unresolved',revision=1))
            c.execute(insert(right),[dict(household_id=i2.HOME,pending_id=resource,person_id='i2-'+peer,
                state='allowed',can_read=True,can_review=True,can_publish=True,revision=1,
                membership_revision=1,reviewed=False,disposition='active') for peer in peers])
            c.execute(insert(plan),[dict(household_id=i2.HOME,pending_id=resource,person_id='i2-'+peer,
                state='allowed',can_read=True,can_edit=True,can_history=True,revision=1,membership_revision=1) for peer in peers])


def encode(value):
    raw=json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode('ascii')
    if len(raw)>i3.MAX_RESPONSE: raise i2.Unavailable()
    return raw


def unique_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise i2.Unavailable()
        result[key]=value
    return result


@dataclass(repr=False)
class Receipt:
    command: t.Command = field(repr=False)
    deadline: float
    attempted: bool=False
    retired: bool=False
    resolved: bool=False


class Workbench(i3.Workbench):
    write_paths=('/api/pending/preview','/api/pending/accept','/api/pending/outcome','/api/pending/recover')

    def __init__(self,lab,port):
        super().__init__(lab,port)
        html=self.assets['/'][0].replace(b'<html lang="zh-CN">',b'<html lang="zh-CN" data-connection="i4a">')
        html=html.replace(b'<script src="/workbench.js"',b'<script src="/acceptance.js" defer></script><script src="/workbench.js"')
        self.assets['/']=(html,self.assets['/'][1])
        self.assets['/acceptance.js']=((HERE/'acceptance.js').read_bytes(),'text/javascript; charset=utf-8')
        self.receipts={}
        self.last_attempt={}
        self.latest_preview={}

    def allows_query(self,env):
        return (env.get('PATH_INFO')=='/api/pending' and env.get('REQUEST_METHOD')=='GET') or super().allows_query(env)

    def _bearer(self,env):
        cookies=i2.cookie_values(env)
        if set(cookies)!={i2.COOKIE}: raise i2.Unavailable()
        bearer=cookies[i2.COOKIE]
        self.lab._current(bearer)
        return bearer

    def read(self,env):
        if env.get('PATH_INFO')!='/api/pending': return super().read(env)
        raw=env.get('QUERY_STRING','');uri='/api/pending'+('?' +raw if raw else '')
        if (env.get('REQUEST_URI',uri)!=uri or env.get('HTTP_SEC_FETCH_SITE')!='same-origin'
                or env.get('HTTP_X_SAMAS_INTENT')!='local-session' or env.get('HTTP_ACCEPT')!='application/json'
                or env.get('CONTENT_LENGTH','') not in ('','0') or env.get('CONTENT_TYPE','')
                or env.get('HTTP_TRANSFER_ENCODING') is not None or env.get('HTTP_CONTENT_ENCODING') is not None
                or any(k.startswith('HTTP_X_') and k!='HTTP_X_SAMAS_INTENT' for k in env)): raise i2.Unavailable()
        limit,offset,step=i3.query(raw)
        with self.lab.lock:
            bearer=self._bearer(env)
            page=self.tasks.pending(bearer,limit=limit,offset=offset,step=step)
            if (type(page) is not t.Page or type(page.total) is not int or not 0<=page.total<=1000000
                    or type(page.has_more) is not bool or len(page.items)>limit): raise i2.Unavailable()
            for r in page.items:
                if (type(r) is not t.PendingView or type(r.id) is not str
                        or re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',r.id) is None
                        or type(r.revision) is not int or not 1<=r.revision<=1000000
                        or (r.step is not None and type(r.step) is not t.Step)
                        or type(r.can_accept) is not bool
                        or (r.supported_date is not None and type(r.supported_date) is not date)): raise i2.Unavailable()
            rows=[dict(id=r.id,revision=r.revision,step=None if r.step is None else r.step.value,
                supported_date=None if r.supported_date is None else r.supported_date.isoformat(),
                can_accept=r.can_accept and r.step is not None) for r in page.items]
            self.lab._now()
            return encode(dict(schema=PENDING_SCHEMA,synthetic_only=True,pagination=dict(limit=limit,offset=offset),
                pending=dict(items=rows,total=page.total,has_more=page.has_more)))

    def write(self,env):
        path=env.get('PATH_INFO')
        if (path not in self.write_paths
                or env.get('REQUEST_URI',path)!=path or env.get('QUERY_STRING')
                or env.get('HTTP_ORIGIN')!=self.origin or env.get('HTTP_SEC_FETCH_SITE')!='same-origin'
                or env.get('HTTP_X_SAMAS_INTENT')!='local-session' or env.get('CONTENT_TYPE')!='application/json'
                or re.fullmatch(r'[1-9][0-9]{0,2}',env.get('CONTENT_LENGTH','')) is None
                or not 1<=int(env['CONTENT_LENGTH'])<=256
                or env.get('HTTP_TRANSFER_ENCODING') is not None or env.get('HTTP_CONTENT_ENCODING') is not None
                or any(k.startswith('HTTP_X_') and k!='HTTP_X_SAMAS_INTENT' for k in env)): raise i2.Unavailable()
        raw=env['wsgi.input'].read(int(env['CONTENT_LENGTH']))
        if len(raw)!=int(env['CONTENT_LENGTH']): raise i2.Unavailable()
        value=json.loads(raw.decode('ascii'),object_pairs_hook=unique_pairs)
        if type(value) is not dict: raise i2.Unavailable()
        with self.lab.lock:
            bearer=self._bearer(env);key=i2.digest(bearer);now=self.lab._now()
            return self.dispatch(bearer,key,now,path,value)

    def response(self,result,receipt,*,key=None):
        return encode(dict(schema=RESULT_SCHEMA,synthetic_only=True,outcome=result.outcome.value,receipt=receipt))

    def guard_preview(self,bearer,key,now):
        owned=self.receipts.setdefault(key,{})
        previous=owned.get(self.last_attempt.get(key))
        if previous and not previous.resolved:
            if self.tasks.verify_outcome(bearer,previous.command).outcome is t.Outcome.UNKNOWN:
                raise i2.Unavailable()
            previous.resolved=True
        for entry in owned.values():
            if not entry.attempted: entry.retired=True
        owned={k:r for k,r in owned.items() if r.attempted or now<r.deadline}
        self.receipts[key]=owned
        if len(owned)>=MAX_RECEIPTS: raise i2.Unavailable()
        return owned

    def issue(self,key,owned,command,now):
        receipt=token_hex(16)
        if receipt in owned: raise i2.Unavailable()
        owned[receipt]=Receipt(command,now+PREVIEW_SECONDS)
        self.latest_preview[key]=receipt
        return receipt

    def pending_preview(self,bearer,key,now,resource,*,expected_revision=None):
        # Shared preparation; I6 additionally binds the displayed explanation.
        owned=self.guard_preview(bearer,key,now)
        step,command=self.tasks.prepare_acceptance(bearer,resource)
        if expected_revision is not None and command.expected_revision!=expected_revision:raise i2.Unavailable()
        receipt=self.issue(key,owned,command,self.lab._now())
        return encode(dict(schema=PREVIEW_SCHEMA,synthetic_only=True,receipt=receipt,
            id=command.resource_id,revision=command.expected_revision,step=step.value,
            assignee=command.assignee,approved_date=None if command.approved_date is None else command.approved_date.isoformat()))

    def dispatch(self,bearer,key,now,path,value):
        self.receipts={k:v for k,v in self.receipts.items() if k in self.lab.leases}
        owned=self.receipts.setdefault(key,{})
        if path=='/api/pending/recover':
            if value: raise i2.Unavailable()
            # Close every unexecuted gate BEFORE checking absence: a delayed POST
            # arriving after recovery must never turn verified absence into a write.
            for entry in owned.values(): entry.retired=True
            latest=owned.get(self.latest_preview.get(key))
            result=self.tasks.verify_outcome(bearer,latest.command) if latest else t.Result(t.Outcome.NOT_APPLIED)
            if latest and result.outcome is not t.Outcome.UNKNOWN: latest.resolved=True
            handle=self.latest_preview.get(key) if latest and result.outcome is not t.Outcome.UNKNOWN else None
            return self.response(result,handle,key=key)
        if path=='/api/pending/preview':
            if set(value)!={'id'}: raise i2.Unavailable()
            return self.pending_preview(bearer,key,now,value['id'])
        expected={'receipt','confirm'} if path.endswith('/accept') else {'receipt'}
        if (set(value)!=expected or type(value.get('receipt')) is not str
                or re.fullmatch(r'[0-9a-f]{32}',value['receipt']) is None
                or (path.endswith('/accept') and value['confirm'] is not True)): raise i2.Unavailable()
        receipt=owned.get(value['receipt'])
        if receipt is None: raise i2.Unavailable()
        if path.endswith('/outcome'): receipt.retired=True
        if path.endswith('/outcome') or receipt.attempted or receipt.retired:
            # Fresh T1 same-primary verification only; never re-execute an ambiguous write.
            result=self.tasks.verify_outcome(bearer,receipt.command)
            outcome=t.Outcome.REPLAY if path.endswith('/accept') and result.outcome is t.Outcome.COMMITTED else result.outcome
        elif now>=receipt.deadline:
            receipt.retired=True
            outcome=t.Outcome.STALE
        else:
            self.last_attempt[key]=value['receipt']
            receipt.attempted=True  # Consume before calling apply, including unexpected failure.
            try: outcome=self.tasks.apply(bearer,receipt.command,confirm=True).outcome
            except Exception: outcome=t.Outcome.UNKNOWN
        # A durably established result is not made ambiguous by later loss of
        # historical access. Responses still require fresh operation authority.
        if outcome is not t.Outcome.UNKNOWN: receipt.resolved=True
        return self.response(t.Result(outcome),value['receipt'],key=key)

    def close(self):
        with self.lab.lock:
            self.receipts.clear();self.last_attempt.clear();self.latest_preview.clear()


def main():
    parser=argparse.ArgumentParser(description='Samas I4a fictional confirmed task acceptance',allow_abbrev=False)
    parser.add_argument('--synthetic-only',action='store_true',required=True)
    args=parser.parse_args()
    try:
        with i2.disposable(synthetic_only=args.synthetic_only) as lab:
            seed(lab);app=Workbench(lab,1)
            try:
                server,app,thread=i2.serve(lab,application=app)
                i2.interact(lab,server,app,thread,banner='LOCAL FICTIONAL I4a — explicit acceptance only; no provider activity or production login.')
            finally: app.close()
    except (KeyboardInterrupt,EOFError): pass
    except Exception: parser.exit(1,'Local acceptance workbench unavailable. No private details are logged.\n')


if __name__=='__main__': main()
