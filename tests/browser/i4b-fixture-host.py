"""Test-only trusted fault controls; never browser-callable provider or grant APIs."""
import argparse
from pathlib import Path
import sys
from sqlalchemy import update,select,func
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'prototypes/i4b-workbench'))
import serve_editing as i4b
i4=i4b.i4
from family_os.schema import household_pending_item as pending,pending_member_right as right,household_task as task,task_domain_event as event,task_member_grant as grant,source_read_grant as source
parser=argparse.ArgumentParser(allow_abbrev=False)
parser.add_argument('--synthetic-only',action='store_true',required=True)
args=parser.parse_args()
with i4.i2.disposable(synthetic_only=args.synthetic_only) as lab:
    i4.seed(lab);app=i4b.Workbench(lab,1)
    apply,verify,read=app.tasks.apply,app.tasks.verify_outcome,app.tasks.tasks
    server,app,thread=i4.i2.serve(lab,application=app)
    print('Open '+app.origin+'/',flush=True)
    try:
        for line in sys.stdin:
            parts=line.split()
            try:
                if parts==['quit']:break
                if len(parts)==3 and parts[0]=='approve':lab.approve(parts[1],parts[2])
                elif parts==['unknown']:
                    def lost(*a,**k):
                        result=apply(*a,**k)
                        if result.outcome is not i4.t.Outcome.COMMITTED:raise RuntimeError('synthetic rejected setup')
                        raise RuntimeError('synthetic acknowledgment loss')
                    app.tasks.apply=lost
                    app.tasks.verify_outcome=lambda *a,**k:i4.t.Result(i4.t.Outcome.UNKNOWN)
                elif parts==['recover']:app.tasks.apply,app.tasks.verify_outcome,app.tasks.tasks=apply,verify,read
                elif parts==['fail']:
                    def fail(*a,**k):raise RuntimeError('synthetic read fault')
                    app.tasks.tasks=fail
                elif len(parts)==2 and parts[0]=='revoke' and parts[1] in i4.i2.PEERS:
                    with i4.i2.a.authorization_transaction(lab.sessions._engine,i4.i2.HOME) as c:
                        c.execute(update(right).where(right.c.household_id==i4.i2.HOME,right.c.person_id=='i2-'+parts[1]).values(state='revoked',revision=right.c.revision+1))
                elif parts==['edit-change']:
                    with i4.i2.a.authorization_transaction(lab.sessions._engine,i4.i2.HOME) as c:
                        c.execute(update(task).where(task.c.household_id==i4.i2.HOME).values(revision=task.c.revision+1))
                elif len(parts)==2 and parts[0]=='task-revoke':
                    with i4.i2.a.authorization_transaction(lab.sessions._engine,i4.i2.HOME) as c:
                        c.execute(update(grant).where(grant.c.household_id==i4.i2.HOME,grant.c.person_id=='i2-'+parts[1]).values(state='revoked',revision=grant.c.revision+1))
                elif parts==['source-revoke']:
                    with i4.i2.a.authorization_transaction(lab.sessions._engine,i4.i2.HOME) as c:
                        c.execute(update(source).where(source.c.household_id==i4.i2.HOME).values(state='revoked',revision=source.c.revision+1))
                elif parts==['change']:
                    with i4.i2.a.authorization_transaction(lab.sessions._engine,i4.i2.HOME) as c:
                        c.execute(update(pending).where(pending.c.household_id==i4.i2.HOME,pending.c.id=='i4a-school').values(revision=pending.c.revision+1,generation=pending.c.generation+1,evidence_fingerprint='d'*64))
                else:raise ValueError()
                print('OK',flush=True)
            except Exception:print('UNAVAILABLE',flush=True)
    finally:app.close();i4.i2.stop(server,lab,thread)
