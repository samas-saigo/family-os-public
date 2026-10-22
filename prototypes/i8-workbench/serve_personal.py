"""I8 opt-in own not-applicable/resume; original T1 and shared receipt coordinator."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'prototypes/i7-workbench'))
import serve_reviews as i7

i5,i2,t=i7.i5,i7.i2,i7.t


class Workbench(i7.Workbench):
    personal_operations=i7.PERSONAL+(t.Operation.NOT_APPLICABLE,t.Operation.RESUME)
    page_schema='i8-personal-pending-page-v1'
    result_schema='i8-write-result-v1'
    pending_states=i7.Workbench.pending_states+('not-applicable',)
    dispositions=i7.Workbench.dispositions+('not-applicable',)

    def __init__(self,lab,port):
        super().__init__(lab,port)
        raw,mime=self.assets['/']
        self.assets['/']=(raw.replace(b'</head>',b'<link rel="stylesheet" href="/personal.css"></head>').replace(b'<script src="/reviews.js"',b'<script src="/personal.js" defer></script><script src="/reviews.js"'),mime)
        self.assets['/personal.css']=((Path(__file__).parent/'personal.css').read_bytes(),'text/css; charset=utf-8')
        self.assets['/personal.js']=((Path(__file__).parent/'personal.js').read_bytes(),'text/javascript; charset=utf-8')

    def pending_json(self,row):
        return dict(super().pending_json(row),can_resume=row.can_resume)

    def personal_preview(self,bearer,key,now,value):
        if type(value.get('operation')) is not str:raise i2.Unavailable()
        operation=t.Operation(value['operation'])
        expected={'id','revision','operation','reason'} if operation is t.Operation.NOT_APPLICABLE else {'id','revision','operation'}
        if set(value)!=expected or type(value['revision']) is not int or operation not in self.personal_operations:raise i2.Unavailable()
        reason=t.PersonalReason(value['reason']) if operation is t.Operation.NOT_APPLICABLE and type(value['reason']) is str else None
        if operation is t.Operation.NOT_APPLICABLE and reason is None:raise i2.Unavailable()
        owned=self.guard_preview(bearer,key,now)
        before,command,after=self.tasks.prepare_personal(bearer,value['id'],operation,value['revision'],reason=reason)
        receipt=self.issue(key,owned,command,self.lab._now())
        return i7.i4b.i4.encode(dict(schema='i8-personal-preview-v1',synthetic_only=True,
            id=command.resource_id,revision=command.expected_revision,operation=operation.value,
            reason=None if command.personal_reason is None else command.personal_reason.value,receipt=receipt,
            before=dict(reviewed=before.reviewed,disposition=before.disposition),
            after=dict(reviewed=after.reviewed,disposition=after.disposition)))


def main():
    parser=argparse.ArgumentParser(description='I8 own personal handling; fictional local testing only',allow_abbrev=False)
    parser.add_argument('--synthetic-only',action='store_true',required=True)
    args=parser.parse_args()
    try:
        with i2.disposable(synthetic_only=args.synthetic_only) as lab:
            coordinator=i5.initialize(lab);app=Workbench(lab,1)
            try:
                server,app,thread=i2.serve(lab,application=app)
                print('I8 own not-applicable/resume — fictional only; no household resolution or external action.')
                i5.interact(lab,server,app,thread,coordinator)
            finally:app.close()
    except (KeyboardInterrupt,EOFError):pass
    except Exception:parser.exit(1,'Fictional personal lab unavailable. No private details are logged.\n')


if __name__=='__main__':main()
