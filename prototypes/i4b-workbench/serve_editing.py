"""I4b opt-in fictional EDIT, sharing I4a's exact-session write gates."""
import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from secrets import token_hex
from urllib.parse import parse_qsl
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'prototypes/i4a-workbench'))
import serve_acceptance as i4

i2,i3,t=i4.i2,i4.i3,i4.t


@dataclass(repr=False)
class Draft:
    before: t.TaskView
    commands: tuple = field(repr=False)
    deadline: float
    used: bool=False


def task_json(row):
    # Explicit neutral projection; never serialize private origin or grants.
    value=json.loads(i3.serialize(t.Page((row,),1,False),1,0))['tasks']['items'][0]
    if type(row.can_edit) is not bool: raise i2.Unavailable()
    return dict(value,can_edit=row.can_edit)


class Workbench(i4.Workbench):
    write_paths=tuple(p for p in i4.Workbench.write_paths if not p.endswith('/recover'))+(
        '/api/tasks/edit-options','/api/tasks/edit-preview','/api/tasks/edit-confirm',
        '/api/tasks/edit-outcome','/api/writes/recover')

    def __init__(self,lab,port):
        super().__init__(lab,port)
        html=self.assets['/'][0].replace(b'data-connection="i4a"',b'data-connection="i4b"')
        self.assets['/']=(html.replace(b'<script src="/workbench.js"',b'<script src="/editing.js" defer></script><script src="/workbench.js"'),self.assets['/'][1])
        self.assets['/editing.js']=((HERE/'editing.js').read_bytes(),'text/javascript; charset=utf-8')
        self.drafts={}

    @staticmethod
    def serialize(page,limit,offset):
        value=json.loads(i3.serialize(page,limit,offset))
        value['schema']='i4b-task-page-v1'
        value['tasks']['items']=[task_json(r) for r in page.items]
        return i4.encode(value)

    def task_parameters(self, raw):
        # Only this opt-in adapter extends Tasks; I3/I4a and Pending retain i3.query.
        if type(raw) is not str or len(raw)>128 or (raw and re.fullmatch(r'[a-z0-9=&-]+',raw) is None):
            raise i2.Unavailable()
        pairs=parse_qsl(raw,keep_blank_values=True,strict_parsing=True,max_num_fields=4)
        filters=[value for name,value in pairs if name=='responsibility']
        if len(filters)>1: raise i2.Unavailable()
        parameters=super().task_parameters('&'.join(name+'='+value for name,value in pairs if name!='responsibility'))
        if filters: parameters['responsibility']=t.Responsibility(filters[0])
        return parameters

    def task_response(self, page, parameters):
        body=super().task_response(page,parameters)
        if 'responsibility' not in parameters: return body  # Unfiltered v1 compatibility.
        value=json.loads(body)
        value['schema']='i4b-task-page-v2'
        value['query']=dict(responsibility=parameters['responsibility'].value,
            step=None if parameters['step'] is None else parameters['step'].value)
        return i4.encode(value)

    def response(self,result,receipt,*,key=None):
        entry=self.receipts.get(key,{}).get(receipt)
        return i4.encode(dict(schema='i4b-write-result-v1',synthetic_only=True,
            outcome=result.outcome.value,receipt=receipt,
            operation=None if entry is None else entry.command.operation.value))

    def dispatch(self,bearer,key,now,path,value):
        self.drafts={k:v for k,v in self.drafts.items() if k in self.lab.leases}
        drafts=self.drafts.setdefault(key,{})
        if path=='/api/tasks/edit-options':
            if set(value)!={'id'}: raise i2.Unavailable()
            self.guard_preview(bearer,key,now)  # Same unresolved-intent gate as ACCEPT.
            drafts={h:d for h,d in drafts.items() if now<d.deadline}
            self.drafts[key]=drafts
            if len(drafts)>=i4.MAX_RECEIPTS: raise i2.Unavailable()
            before,commands=self.tasks.prepare_edits(bearer,value['id'])
            # Fixed approved fictional peers only, fail closed on unsupported setup.
            choices=sorted({r.person_id for c in commands for r in c.edit_recipients})
            if any(p not in ('i2-clara','i2-devon') for p in choices): raise i2.Unavailable()
            handle=token_hex(16)
            if handle in drafts: raise i2.Unavailable()
            drafts[handle]=Draft(before,commands,self.lab._now()+i4.PREVIEW_SECONDS)
            return i4.encode(dict(schema='i4b-edit-options-v1',synthetic_only=True,draft=handle,
                task=task_json(before),assignees=choices+(['joint'] if len(choices)==2 else [])))
        if path=='/api/tasks/edit-preview':
            if (set(value) not in ({'draft','action'},{'draft','action','assignee'})
                    or type(value.get('draft')) is not str or re.fullmatch('[0-9a-f]{32}',value['draft']) is None
                    or type(value.get('action')) is not str): raise i2.Unavailable()
            owned=self.guard_preview(bearer,key,now)
            draft=drafts.get(value['draft'])
            if draft is None or draft.used or now>=draft.deadline: raise i2.Unavailable()
            if value['action']=='assign' and set(value)=={'draft','action','assignee'}:
                if type(value['assignee']) is not str: raise i2.Unavailable()
                commands=[c for c in draft.commands if c.assignee is not None and c.assignee==value['assignee']]
            elif set(value)=={'draft','action'} and value['action'] in ('complete','reopen'):
                target=t.Status.COMPLETED if value['action']=='complete' else t.Status.PENDING
                commands=[c for c in draft.commands if c.status is target]
            else: raise i2.Unavailable()
            if len(commands)!=1: raise i2.Unavailable()
            command=commands[0]
            before,current=self.tasks.prepare_edits(bearer,command.resource_id)
            if (before!=draft.before or any(c.edit_recipients!=command.edit_recipients for c in current)):
                raise i2.Unavailable()  # Never silently rebase the displayed draft.
            fresh_now=self.lab._now()
            if fresh_now>=draft.deadline: raise i2.Unavailable()
            receipt=self.issue(key,owned,command,fresh_now)
            draft.used=True
            return i4.encode(dict(schema='i4b-edit-preview-v1',synthetic_only=True,receipt=receipt,
                task=task_json(before),action=value['action'],
                assignee=before.assignee if command.assignee is None else command.assignee,
                status=before.status.value if command.status is None else command.status.value))
        if path=='/api/writes/recover':
            return super().dispatch(bearer,key,now,'/api/pending/recover',value)
        is_edit=path in ('/api/tasks/edit-confirm','/api/tasks/edit-outcome')
        if is_edit or path in ('/api/pending/accept','/api/pending/outcome'):
            entry=self.receipts.get(key,{}).get(value.get('receipt')) if type(value.get('receipt')) is str else None
            if entry is None or entry.command.operation is not (t.Operation.EDIT if is_edit else t.Operation.ACCEPT):
                raise i2.Unavailable()  # No cross-operation replay/result substitution.
            if is_edit:path='/api/pending/accept' if path.endswith('confirm') else '/api/pending/outcome'
        return super().dispatch(bearer,key,now,path,value)

    def close(self):
        with self.lab.lock:
            self.drafts.clear()
            super().close()


def main():
    parser=argparse.ArgumentParser(description='Samas I4b fictional confirmed acceptance and task editing',allow_abbrev=False)
    parser.add_argument('--synthetic-only',action='store_true',required=True)
    args=parser.parse_args()
    try:
        with i2.disposable(synthetic_only=args.synthetic_only) as lab:
            i4.seed(lab);app=Workbench(lab,1)
            try:
                server,app,thread=i2.serve(lab,application=app)
                i2.interact(lab,server,app,thread,banner='LOCAL FICTIONAL I4b — confirmed tracking edits only; no external activity or production login.')
            finally: app.close()
    except (KeyboardInterrupt,EOFError): pass
    except Exception: parser.exit(1,'Local editing workbench unavailable. No private details are logged.\n')


if __name__=='__main__': main()
