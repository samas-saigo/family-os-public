"""Trusted stdin-only controls over an owned fictional I4b store; no new API."""
import argparse
from datetime import date
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from time import time
import jwt

from sqlalchemy import insert, update

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'prototypes/i4b-workbench'))
import serve_editing as i4b
from family_os.schema import (household_pending_item as pending, pending_member_right as right,
    pending_task_publication as plan, household_task as task, task_member_grant as grant,
    household_membership as member)
i4, i2, t = i4b.i4, i4b.i2, i4b.t
parser = argparse.ArgumentParser(allow_abbrev=False)
parser.add_argument('--synthetic-only', action='store_true', required=True)
parser.add_argument('--baseline', action='store_true')
args = parser.parse_args()

with i2.disposable(synthetic_only=args.synthetic_only) as lab:
    i4.seed(lab)
    app = i4b.Workbench(lab, 1)
    if args.baseline:
        # Capture the actual merged predecessor, served by the same genuine I4b host.
        for path, filename in [('/workbench.js', 'workbench.js'), ('/connected.css', 'connected.css')]:
            raw = subprocess.run(['git', 'show', '53f687c96d91d277e421f2228e2e79081ec38ce2:prototypes/i3-workbench/' + filename],
                                 cwd=ROOT, check=True, capture_output=True).stdout
            app.assets[path] = (raw, app.assets[path][1])
    apply, verify, tasks, proposals = app.tasks.apply, app.tasks.verify_outcome, app.tasks.tasks, app.tasks.pending
    server, app, thread = i2.serve(lab, application=app)
    print('Open ' + app.origin + '/', flush=True)
    try:
        for line in sys.stdin:
            parts = line.split()
            try:
                if parts == ['quit']: break
                if len(parts) == 3 and parts[0] == 'approve': lab.approve(parts[1], parts[2])
                elif parts == ['recover']:
                    app.tasks.apply, app.tasks.verify_outcome, app.tasks.tasks, app.tasks.pending = apply, verify, tasks, proposals
                elif parts in (['fail-tasks'], ['fail-pending']):
                    def fail(*a, **k): raise RuntimeError('fictional unavailable')
                    if parts[0] == 'fail-tasks': app.tasks.tasks = fail
                    else: app.tasks.pending = fail
                elif parts == ['unknown']:
                    def lost(*a, **k):
                        result = apply(*a, **k)
                        if result.outcome is not t.Outcome.COMMITTED: raise RuntimeError('fictional rejected setup')
                        raise RuntimeError('fictional acknowledgment loss')
                    app.tasks.apply = lost
                    app.tasks.verify_outcome = lambda *a, **k: t.Result(t.Outcome.UNKNOWN)
                elif len(parts) == 2 and parts[0] in ('tasks-revoke', 'pending-revoke', 'member-revoke') and parts[1] in i2.PEERS:
                    table = {'tasks-revoke': grant, 'pending-revoke': right, 'member-revoke': member}[parts[0]]
                    with i2.a.authorization_transaction(lab.sessions._engine, i2.HOME) as c:
                        c.execute(update(table).where(table.c.household_id == i2.HOME,
                            table.c.person_id == 'i2-' + parts[1]).values(state='revoked', revision=table.c.revision + 1))
                elif parts == ['many-pending']:
                    with i2.a.authorization_transaction(lab.sessions._engine, i2.HOME) as c:
                        for n in range(14):
                            resource = 'a1-overflow-question-' + str(n)
                            c.execute(insert(pending).values(household_id=i2.HOME,id=resource,
                                source_account_id='i4a-shared-source',kind='question',supported=False,safety='unknown',
                                step=None,supported_date=None,generation=1,evidence_fingerprint=sha256(resource.encode()).hexdigest(),
                                definition_version='a1-pagination-fiction-v1',resolution='unresolved',revision=1))
                            c.execute(insert(right), [dict(household_id=i2.HOME,pending_id=resource,person_id='i2-'+peer,
                                state='allowed',can_read=True,can_review=True,can_publish=False,revision=1,
                                membership_revision=1,reviewed=False,disposition='active') for peer in i2.PEERS])
                elif parts == ['no-dates']:
                    with i2.a.authorization_transaction(lab.sessions._engine, i2.HOME) as c:
                        c.execute(update(task).where(task.c.household_id == i2.HOME).values(approved_date=None, revision=task.c.revision + 1))
                elif parts == ['responsibility']:
                    sys.path.insert(0,str(ROOT/'tests'))
                    from responsibility_fixtures import seed as seed_responsibility
                    challenge=lab.verifier.challenge();now=int(time())
                    assertion=jwt.encode(dict(iss=i2.ISSUER,sub='i2-sub-clara',aud='i2-fictional-client',
                        iat=now-1,nbf=now-1,exp=now+60,nonce=challenge.nonce),lab.key,algorithm='RS256',headers={'kid':'i2-key'})
                    issued=lab.sessions.establish(lab.verifier.verify(assertion,challenge),i2.HOME,request_id='responsibility-seed')
                    if issued.outcome is not i2.s.Outcome.COMMITTED or not issued.bearer:raise RuntimeError()
                    seed_responsibility(app,issued.bearer)
                    current=lab.sessions.resolve(issued.bearer,i2.HOME)
                    lab.sessions.logout(issued.bearer,i2.HOME,request_id='responsibility-seed-logout',expected_revision=current.revision)
                elif parts == ['many']:
                    # Newly authored pagination fixtures. Tasks are created only by actual T1 ACCEPT.
                    challenge = lab.verifier.challenge()
                    now = int(time())
                    assertion = jwt.encode(dict(iss=i2.ISSUER,sub='i2-sub-clara',aud='i2-fictional-client',
                        iat=now-1,nbf=now-1,exp=now+60,nonce=challenge.nonce),lab.key,
                        algorithm='RS256',headers={'kid':'i2-key'})
                    issued = lab.sessions.establish(lab.verifier.verify(assertion,challenge),i2.HOME,request_id='a1-pagination-seed')
                    if issued.outcome is not i2.s.Outcome.COMMITTED or not issued.bearer: raise RuntimeError()
                    bearer = issued.bearer
                    for n in range(14):
                        resource = 'a1-fiction-' + str(n)
                        with i2.a.authorization_transaction(lab.sessions._engine, i2.HOME) as c:
                            c.execute(insert(pending).values(household_id=i2.HOME,id=resource,
                                source_account_id='i4a-shared-source',kind='action',supported=True,safety='clear',
                                step='home-visit',supported_date=date(2038,7,18) if n % 3 == 0 else None,
                                generation=1,evidence_fingerprint=sha256(resource.encode()).hexdigest(),
                                definition_version='a1-pagination-fiction-v1',resolution='unresolved',revision=1))
                            for table, permissions in [(right, dict(can_read=True,can_review=True,can_publish=True,reviewed=False,disposition='active')),
                                                       (plan, dict(can_read=True,can_edit=True,can_history=True))]:
                                c.execute(insert(table), [dict(household_id=i2.HOME,pending_id=resource,person_id='i2-'+peer,
                                    state='allowed',revision=1,membership_revision=1,**permissions) for peer in i2.PEERS])
                        _, command = app.tasks.prepare_acceptance(bearer, resource)
                        if apply(bearer, command, confirm=True).outcome is not t.Outcome.COMMITTED: raise RuntimeError()
                    current = lab.sessions.resolve(bearer, i2.HOME)
                    lab.sessions.logout(bearer, i2.HOME, request_id='a1-seed-logout', expected_revision=current.revision)
                else: raise ValueError()
                print('OK', flush=True)
            except Exception: print('UNAVAILABLE', flush=True)
    finally:
        app.close()
        i2.stop(server, lab, thread)
