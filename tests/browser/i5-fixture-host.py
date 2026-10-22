"""Owned I5 lab with bounded trusted stdin faults; never client/provider APIs."""
from dataclasses import replace
import argparse
import json
from pathlib import Path
import sys
from sqlalchemy import update
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'prototypes/i5-workbench'))
import serve_information as i5
from family_os._fictional_information import pending_identity,Source
from family_os.schema import source_read_grant,household_membership
parser=argparse.ArgumentParser(allow_abbrev=False)
parser.add_argument('--synthetic-only',action='store_true',required=True)
args=parser.parse_args()
with i5.i2.disposable(synthetic_only=args.synthetic_only) as lab:
    coordinator=i5.initialize(lab);app=i5.i4b.Workbench(lab,1)
    original,verify,pending=app.tasks.apply,app.tasks.verify_outcome,app.tasks.pending
    server,app,thread=i5.i2.serve(lab,application=app)
    print('Open '+app.origin+'/',flush=True)
    print('Ids '+json.dumps({v.record_id:pending_identity(i5.i2.HOME,v.source,v.record_id) for v in (*i5.cases(),replace(i5.cases()[0],record_id='i5-page-0'))}),flush=True)
    try:
        for line in sys.stdin:
            parts=line.split()
            try:
                if parts==['quit']:break
                with lab.lock:
                    lab._now()
                    if len(parts)==3 and parts[0]=='approve':lab.approve(parts[1],parts[2])
                    elif len(parts)==1 and parts[0] in ('process','repeat','change','revert','pages'):i5.experiment(coordinator,parts[0])
                    elif len(parts)==1 and parts[0] in ('guard-create','guard-risk','guard-fresh'):
                        stage={'guard-create':1,'guard-risk':2,'guard-fresh':3}[parts[0]]
                        value=replace(i5.cases()[0],record_id='i5-page-0',generation=stage,observed_date=None,date_basis=i5.DateBasis.NONE,
                            safety=i5.r.Safety.HIGH_RISK if stage==2 else i5.r.Safety.SAFE_TO_ROUTE)
                        result=coordinator.process(value)
                        if result.outcome is not i5.Outcome.COMMITTED:raise ValueError()
                    elif parts==['unknown']:
                        def lost(*a,**k):
                            if original(*a,**k).outcome is not i5.i4b.t.Outcome.COMMITTED:raise RuntimeError('synthetic setup failed')
                            raise RuntimeError('synthetic acknowledgment loss')
                        app.tasks.apply=lost
                        app.tasks.verify_outcome=lambda *a,**k:i5.i4b.t.Result(i5.i4b.t.Outcome.UNKNOWN)
                    elif parts==['recover']:app.tasks.apply,app.tasks.verify_outcome,app.tasks.pending=original,verify,pending
                    elif parts==['fail']:
                        def fail(*a,**k):raise RuntimeError('synthetic unavailable')
                        app.tasks.pending=fail
                    elif len(parts)==3 and parts[0] in ('source-revoke','source-grant') and parts[1] in ('shared','clara','devon') and parts[2] in i5.i2.PEERS:
                        src={'shared':Source.SHARED,'clara':Source.CLARA,'devon':Source.DEVON}[parts[1]]
                        with i5.i2.a.authorization_transaction(lab.sessions._engine,i5.i2.HOME) as c:
                            c.execute(update(source_read_grant).where(source_read_grant.c.household_id==i5.i2.HOME,
                                source_read_grant.c.source_account_id==src.value,source_read_grant.c.person_id=='i2-'+parts[2]).values(state='revoked' if parts[0]=='source-revoke' else 'allowed',revision=source_read_grant.c.revision+1))
                    else:raise ValueError()
                print('OK',flush=True)
            except Exception:print('UNAVAILABLE',flush=True)
    finally:app.close();i5.i2.stop(server,lab,thread)
