"""I3: actual T1 SQL reads over the existing I2 fictional loopback session boundary."""
import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from time import time
from urllib.parse import parse_qsl

import jwt
from sqlalchemy import insert

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'prototypes/i2-local-session'))
import local_session as i2

from family_os import _household_tasks as t
from family_os.registry import register
from family_os.schema import (source_read_grant, household_pending_item as pending,
    pending_member_right as right, pending_task_publication as plan)

SCHEMA = 'i3-fictional-task-page-v1'
MAX_RESPONSE = 16384
FIELDS = {'id','step','assignee','status','approved_date','revision'}


def fixture_session(lab, peer):
    """Privileged fixed-fixture setup, never a browser route or identity input."""
    challenge = lab.verifier.challenge()
    now = int(time())
    token = jwt.encode(dict(iss=i2.ISSUER, sub='i2-sub-'+peer, aud='i2-fictional-client',
        iat=now-1, nbf=now-1, exp=now+60, nonce=challenge.nonce), lab.key,
        algorithm='RS256', headers={'kid':'i2-key'})
    result = lab.sessions.establish(lab.verifier.verify(token, challenge), i2.HOME,
        request_id='i3-seed-'+peer)
    if result.outcome is not i2.s.Outcome.COMMITTED or not result.bearer:
        raise i2.Unavailable()
    return result.bearer


def seed(lab):
    """New fictional Pending → explicit T1 acceptance/edit; no direct task insertion."""
    engine = lab.sessions._engine
    register(engine, {'household':{'id':i2.HOME,'name':'Fictional I2 Willow'},
        'source_accounts':[dict(id='i3-fixture-source', provider='fixture',
            owner_type='person', owner_id='i2-clara')]})
    definitions = [('i3-school','school-session',('clara','devon'),date(2035,6,12)),
        ('i3-visit','home-visit',('clara','devon'),None),
        ('i3-private','home-visit',('clara',),None),
        ('i3-unaccepted','school-session',('clara','devon'),None)]
    fingerprint = sha256(b'new-i3-fictional-evidence-only').hexdigest()
    with i2.a.authorization_transaction(engine, i2.HOME) as c:
        c.execute(insert(source_read_grant).values(household_id=i2.HOME,
            source_account_id='i3-fixture-source',person_id='i2-clara',state='allowed',
            observations=True,security=True,revision=1,membership_revision=1))
        for resource, step, recipients, when in definitions:
            c.execute(insert(pending).values(household_id=i2.HOME,id=resource,
                source_account_id='i3-fixture-source',kind='action',step=step,supported=True,
                safety='clear',supported_date=when,generation=1,evidence_fingerprint=fingerprint,
                definition_version='i3-fictional-v1',resolution='unresolved',revision=1))
            c.execute(insert(right).values(household_id=i2.HOME,pending_id=resource,
                person_id='i2-clara',state='allowed',can_read=True,can_review=True,
                can_publish=True,revision=1,membership_revision=1,reviewed=False,disposition='active'))
            c.execute(insert(plan), [dict(household_id=i2.HOME,pending_id=resource,
                person_id='i2-'+peer,state='allowed',can_read=True,can_edit=True,
                can_history=True,revision=1,membership_revision=1) for peer in recipients])
    service = t.TaskService(lab.sessions, i2.HOME, synthetic_only=True)
    bearer = fixture_session(lab, 'clara')
    for resource, step, recipients, when in definitions[:3]:
        row = next(r for r in service.pending(bearer).items if r.id == resource)
        result = service.apply(bearer, t.Command(t.Operation.ACCEPT,resource,row.revision,
            row.rights_revision,'i3-accept-'+resource,row.binding,assignee='joint' if len(recipients)==2 else 'i2-clara',
            approved_date=when,recipients=tuple(t.Recipient('i2-'+p,1) for p in recipients)),confirm=True)
        if result.outcome is not t.Outcome.COMMITTED:
            raise i2.Unavailable()
        if resource == 'i3-visit':
            task = next(r for r in service.tasks(bearer).items if r.id == result.task_id)
            edited = service.apply(bearer,t.Command(t.Operation.EDIT,task.id,task.revision,
                task.rights_revision,'i3-complete-visit',status=t.Status.COMPLETED),confirm=True)
            if edited.outcome is not t.Outcome.COMMITTED:
                raise i2.Unavailable()
    current = lab.sessions.resolve(bearer,i2.HOME)
    if lab.sessions.logout(bearer,i2.HOME,request_id='i3-seed-logout',expected_revision=current.revision).outcome is not i2.s.Outcome.COMMITTED:
        raise i2.Unavailable()


def query(raw):
    if type(raw) is not str or len(raw)>128 or (raw and re.fullmatch(r'[a-z0-9=&-]+',raw) is None):
        raise i2.Unavailable()
    pairs = parse_qsl(raw,keep_blank_values=True,strict_parsing=True,max_num_fields=3)
    values = {}
    for name,value in pairs:
        if name not in ('limit','offset','step') or name in values or not value:
            raise i2.Unavailable()
        values[name]=value
    for name in ('limit','offset'):
        if name in values and re.fullmatch(r'0|[1-9][0-9]{0,6}',values[name]) is None:
            raise i2.Unavailable()
    limit,offset=int(values.get('limit','2')),int(values.get('offset','0'))
    if not 1<=limit<=20 or not 0<=offset<=1000000:
        raise i2.Unavailable()
    return limit,offset,None if 'step' not in values else t.Step(values['step'])


def serialize(page, limit, offset):
    if (type(page) is not t.Page or type(page.total) is not int or not 0<=page.total<=1000000
            or type(page.has_more) is not bool or len(page.items)>limit):
        raise i2.Unavailable()
    for r in page.items:
        if (type(r) is not t.TaskView or re.fullmatch(r'task_[0-9a-f]{32}',r.id) is None
                or type(r.step) is not t.Step or type(r.status) is not t.Status
                or r.assignee not in ('joint','i2-clara','i2-devon')
                or type(r.revision) is not int or not 1<=r.revision<=1000000
                or (r.approved_date is not None and type(r.approved_date) is not date)):
            raise i2.Unavailable()
    rows = [dict(id=r.id,step=r.step.value,assignee=r.assignee,status=r.status.value,
        approved_date=None if r.approved_date is None else r.approved_date.isoformat(),revision=r.revision)
        for r in page.items]
    result = dict(schema=SCHEMA,synthetic_only=True,pagination=dict(limit=limit,offset=offset),
        tasks=dict(items=rows,total=page.total,has_more=page.has_more))
    body=json.dumps(result,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode('ascii')
    if len(body)>MAX_RESPONSE:
        raise i2.Unavailable()
    return body


class Workbench(i2.Application):
    serialize=staticmethod(serialize)

    def __init__(self, lab, port):
        super().__init__(lab,port)
        resources={'/':(HERE/'index.html','text/html; charset=utf-8'),
            '/workbench.js':(HERE/'workbench.js','text/javascript; charset=utf-8'),
            '/contract.js':(HERE/'contract.js','text/javascript; charset=utf-8'),
            '/connected.css':(HERE/'connected.css','text/css; charset=utf-8'),
            '/styles.css':(ROOT/'prototypes/h0-workbench/styles.css','text/css; charset=utf-8')}
        self.assets={path:(file.read_bytes(),mime) for path,(file,mime) in resources.items()}
        self.tasks=t.TaskService(lab.sessions,i2.HOME,synthetic_only=True)

    def allows_query(self, env):
        return (env.get('PATH_INFO')=='/api/tasks' and env.get('REQUEST_METHOD')=='GET') or super().allows_query(env)

    def task_parameters(self, raw):
        limit, offset, step = query(raw)
        return dict(limit=limit, offset=offset, step=step)

    def task_response(self, page, parameters):
        return self.serialize(page, parameters['limit'], parameters['offset'])

    def read(self, env):
        raw=env.get('QUERY_STRING','')
        exact_uri='/api/tasks'+('?' + raw if raw else '')
        if (env.get('PATH_INFO')!='/api/tasks' or env.get('HTTP_SEC_FETCH_SITE')!='same-origin'
                or env.get('REQUEST_URI',exact_uri)!=exact_uri
                or env.get('HTTP_X_SAMAS_INTENT')!='local-session'
                or env.get('HTTP_ACCEPT')!='application/json'
                or env.get('CONTENT_LENGTH','') not in ('','0') or env.get('CONTENT_TYPE','')
                or env.get('HTTP_TRANSFER_ENCODING') is not None
                or env.get('HTTP_CONTENT_ENCODING') is not None
                or any(k.startswith('HTTP_X_') and k!='HTTP_X_SAMAS_INTENT' for k in env)):
            raise i2.Unavailable()
        parameters=self.task_parameters(env.get('QUERY_STRING',''))
        cookies=i2.cookie_values(env)
        if set(cookies)!={i2.COOKIE}:
            raise i2.Unavailable()
        bearer=cookies[i2.COOKIE]
        with self.lab.lock:
            self.lab._current(bearer)
            # T1 independently revalidates session/current membership + task grant
            # in its own household transaction. A prior resolve is never a lease.
            page=self.tasks.tasks(bearer,**parameters)
            self.lab._now()
            return self.task_response(page,parameters)


def main():
    parser=argparse.ArgumentParser(description='Samas I3 fictional read-only connected workbench',allow_abbrev=False)
    parser.add_argument('--synthetic-only',action='store_true',required=True)
    args=parser.parse_args()
    try:
        with i2.disposable(synthetic_only=args.synthetic_only) as lab:
            seed(lab)
            app=Workbench(lab,1)
            server,app,thread=i2.serve(lab,application=app)
            i2.interact(lab,server,app,thread,banner='LOCAL BACKEND TEST — fictional T1 tasks, read-only; not real login or household data.')
    except (KeyboardInterrupt,EOFError):
        pass
    except Exception:
        parser.exit(1,'Local read-only workbench unavailable. No private details are logged.\n')


if __name__=='__main__':
    main()
