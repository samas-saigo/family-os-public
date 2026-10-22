"""Trusted stdin-only I7 faults over an owned fictional DB; never product routes."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from sqlalchemy import update
ROOT=Path(__file__).resolve().parents[2]
from family_os.schema import task_member_grant as grants
from family_os.schema import source_read_grant as sources,pending_member_right as rights,external_identity_binding as bindings,household_membership as members
parser=argparse.ArgumentParser(allow_abbrev=False)
parser.add_argument('--synthetic-only',action='store_true',required=True)
parser.add_argument('--i8',action='store_true')
parser.add_argument('--i9',action='store_true')
args=parser.parse_args()
if args.i9:
    sys.path.insert(0,str(ROOT/'prototypes/i9-workbench'))
    import serve_home as i7
elif args.i8:
    sys.path.insert(0,str(ROOT/'prototypes/i8-workbench'))
    import serve_personal as i7
else:
    sys.path.insert(0,str(ROOT/'prototypes/i7-workbench'))
    import serve_reviews as i7
i6=i7
i5,i2=i6.i5,i6.i2
with i2.disposable(synthetic_only=args.synthetic_only) as lab:
    coordinator=i5.initialize(lab);app=i6.Workbench(lab,1)
    server,app,thread=i2.serve(lab,application=app)
    original=app.explanations.read
    apply,verify=app.tasks.apply,app.tasks.verify_outcome
    home=app.tasks.action_home
    print('Open '+app.origin+'/',flush=True)
    from family_os._fictional_information import pending_identity
    print('Ids '+json.dumps({v.record_id:pending_identity(i2.HOME,v.source,v.record_id) for v in i5.cases()}),flush=True)
    try:
        for line in sys.stdin:
            parts=line.split()
            try:
                if parts==['quit']:break
                with lab.lock:
                    lab._now()
                    if len(parts)==3 and parts[0]=='approve':lab.approve(parts[1],parts[2])
                    elif len(parts)==1 and parts[0] in ('process','repeat','change','revert','pages'):i5.experiment(coordinator,parts[0])
                    elif parts in (['blocked'],['fresh']):
                        v=replace(i5.cases()[0],generation=4 if parts==['blocked'] else 5,safety=i5.r.Safety.HIGH_RISK if parts==['blocked'] else i5.r.Safety.SAFE_TO_ROUTE)
                        if coordinator.process(v).effect!=('blocked' if parts==['blocked'] else 'updated'):raise ValueError()
                    elif args.i9 and parts==['home-fail']:
                        def unavailable(*args):raise RuntimeError('fictional read failure')
                        app.tasks.action_home=unavailable
                    elif args.i9 and parts==['home-recover']:app.tasks.action_home=home
                    elif args.i9 and len(parts)==2 and parts[0]=='task-revoke' and parts[1] in i2.PEERS:
                        with i2.a.authorization_transaction(lab.sessions._engine,i2.HOME) as c:
                            c.execute(update(grants).where(grants.c.person_id=='i2-'+parts[1]).values(state='revoked',revision=grants.c.revision+1))
                    elif parts==['fail']:
                        def unavailable(*args):raise RuntimeError('synthetic unavailable')
                        app.explanations.read=unavailable
                    elif parts==['unknown']:
                        def lost(*args,**kw):
                            if apply(*args,**kw).outcome is not i6.t.Outcome.COMMITTED:raise RuntimeError('synthetic failure')
                            raise RuntimeError('synthetic acknowledgment loss')
                        app.tasks.apply=lost
                        app.tasks.verify_outcome=lambda *args,**kw:i6.t.Result(i6.t.Outcome.UNKNOWN)
                    elif parts==['recover']:app.explanations.read,app.tasks.apply,app.tasks.verify_outcome=original,apply,verify
                    elif len(parts)==3 and parts[0] in ('source-revoke','source-grant','security-revoke') and parts[1] in ('shared','clara','devon') and parts[2] in i2.PEERS:
                        source={'shared':i5.Source.SHARED,'clara':i5.Source.CLARA,'devon':i5.Source.DEVON}[parts[1]]
                        with i2.a.authorization_transaction(lab.sessions._engine,i2.HOME) as c:
                            values=dict(revision=sources.c.revision+1)
                            if parts[0]=='security-revoke':values['security']=False
                            else:values['state']='allowed' if parts[0]=='source-grant' else 'revoked'
                            c.execute(update(sources).where(sources.c.household_id==i2.HOME,sources.c.source_account_id==source.value,sources.c.person_id=='i2-'+parts[2]).values(**values))
                    elif parts==['review-only']:
                        with i2.a.authorization_transaction(lab.sessions._engine,i2.HOME) as c:
                            c.execute(update(rights).where(rights.c.person_id=='i2-devon').values(can_review=False,revision=rights.c.revision+1))
                    elif len(parts)==2 and parts[0] in ('pending-revoke','binding-revoke','member-revoke') and parts[1] in i2.PEERS:
                        table={'pending-revoke':rights,'binding-revoke':bindings,'member-revoke':members}[parts[0]]
                        with i2.a.authorization_transaction(lab.sessions._engine,i2.HOME) as c:
                            c.execute(update(table).where(table.c.household_id==i2.HOME,table.c.person_id=='i2-'+parts[1]).values(state='revoked',revision=table.c.revision+1))
                    else:raise ValueError()
                print('OK',flush=True)
            except Exception:print('UNAVAILABLE',flush=True)
    finally:app.close();i2.stop(server,lab,thread)
