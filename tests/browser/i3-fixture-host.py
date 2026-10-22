"""Trusted browser-test controller only; no browser-callable provisioning routes."""
import argparse
from pathlib import Path
import sys

from sqlalchemy import update

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'prototypes/i3-workbench'))
import serve_workbench as i3
from family_os.schema import task_member_grant,source_read_grant

parser=argparse.ArgumentParser(allow_abbrev=False)
parser.add_argument('--synthetic-only',action='store_true',required=True)
args=parser.parse_args()
with i3.i2.disposable(synthetic_only=args.synthetic_only) as lab:
    i3.seed(lab)
    app=i3.Workbench(lab,1)
    original=app.tasks.tasks
    server,app,thread=i3.i2.serve(lab,application=app)
    print('Open '+app.origin+'/',flush=True)
    try:
        for line in sys.stdin:
            parts=line.split()
            try:
                if parts==['quit']:break
                if len(parts)==3 and parts[0]=='approve':lab.approve(parts[1],parts[2])
                elif len(parts)==2 and parts[0] in ('revoke','source-revoke') and parts[1] in i3.i2.PEERS:
                    table=task_member_grant if parts[0]=='revoke' else source_read_grant
                    with i3.i2.a.authorization_transaction(lab.sessions._engine,i3.i2.HOME) as c:
                        c.execute(update(table).where(table.c.household_id==i3.i2.HOME,
                            table.c.person_id=='i2-'+parts[1]).values(state='revoked',revision=table.c.revision+1))
                elif parts==['fail']:
                    def fail(*a,**k):raise RuntimeError('synthetic database fault')
                    app.tasks.tasks=fail
                elif parts==['recover']:app.tasks.tasks=original
                else:raise ValueError()
                print('OK',flush=True)
            except Exception:print('UNAVAILABLE',flush=True)
    finally:i3.i2.stop(server,lab,thread)
