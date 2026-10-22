"""I5 fixed fictional feeder; original I4b browser/API, no browser injection route."""
import argparse
from dataclasses import replace
from datetime import date
from pathlib import Path
from queue import Queue, Empty
from threading import Thread, Timer
import sys

from sqlalchemy import insert

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'prototypes/i4b-workbench'))
import serve_editing as i4b
from family_os._fictional_information import Coordinator, Information, Plan, Peer, Source, Outcome, DateBasis
from family_os import _synthetic_routing as r
from family_os.schema import source_read_grant, fictional_information_revision as ledger, household_pending_item as pending, household_task as task

i2=i4b.i2


def setup(lab):
    """Independent trusted fictional source/grant/publication configuration."""
    i4b.i4.seed(lab)
    i4b.i3.register(lab.sessions._engine,{'household':{'id':i2.HOME,'name':'Fictional Willow'},
        'source_accounts':[dict(id=s.value,provider='fixture',owner_type='person',owner_id='i2-clara' if s is not Source.DEVON else 'i2-devon') for s in Source]})
    with i2.a.authorization_transaction(lab.sessions._engine,i2.HOME) as c:
        for source,peers in [(Source.SHARED,tuple(Peer)),(Source.CLARA,(Peer.CLARA,)),(Source.DEVON,(Peer.DEVON,))]:
            c.execute(insert(source_read_grant),[dict(household_id=i2.HOME,source_account_id=source.value,
                person_id=peer.value,state='allowed',observations=True,security=True,revision=1,membership_revision=1) for peer in peers])
    shared=tuple(Peer)
    records=[('i5-school',Source.SHARED,shared,(Peer.CLARA,),shared),
        ('i5-uncertain',Source.SHARED,shared,(),()),
        ('i5-promotion',Source.SHARED,(),(),()),('i5-suspicious',Source.SHARED,(),(),()),
        ('i5-information',Source.SHARED,(),(),()),
        ('i5-clara-visit',Source.CLARA,(Peer.CLARA,),(Peer.CLARA,),shared),
        ('i5-devon-visit',Source.DEVON,(Peer.DEVON,),(Peer.DEVON,),shared),
        ('i5-mixed',Source.SHARED,shared,(Peer.CLARA,),shared)]
    plans=tuple(Plan(src,record,readers,readers,publishers,recipients) for record,src,readers,publishers,recipients in records)
    # A priori fixture approval of a bounded pagination population, before any inputs.
    plans+=tuple(Plan(Source.SHARED,'i5-page-'+str(n),shared,shared,(Peer.CLARA,),shared) for n in range(14))
    return plans


def cases():
    supported=r.Business(action=r.ActionEvidence.SUPPORTED,importance=r.Importance.IMPORTANT)
    school=Information(Source.SHARED,'i5-school',1,r.Safety.SAFE_TO_ROUTE,supported,i4b.t.Step.SCHOOL,date(2040,9,18),date_basis=DateBasis.ACTION)
    return (school,
        Information(Source.SHARED,'i5-uncertain',1,r.Safety.SAFE_TO_ROUTE,r.Business(action=r.ActionEvidence.CONFLICTING,importance=r.Importance.IMPORTANT)),
        Information(Source.SHARED,'i5-promotion',1,r.Safety.SAFE_TO_ROUTE,r.Business(promotion=True,importance=r.Importance.NOT_IMPORTANT,expiry=r.Expiry.UPCOMING)),
        Information(Source.SHARED,'i5-suspicious',1,r.Safety.HIGH_RISK,supported,i4b.t.Step.SCHOOL),
        Information(Source.SHARED,'i5-information',1,r.Safety.SAFE_TO_ROUTE,r.Business(informational=True,importance=r.Importance.NOT_IMPORTANT)),
        Information(Source.CLARA,'i5-clara-visit',1,r.Safety.SAFE_TO_ROUTE,supported,i4b.t.Step.HOME),
        Information(Source.DEVON,'i5-devon-visit',1,r.Safety.SAFE_TO_ROUTE,supported,i4b.t.Step.HOME),
        Information(Source.SHARED,'i5-mixed',1,r.Safety.SAFE_TO_ROUTE,r.Business(promotion=True,importance=r.Importance.IMPORTANT)))


def initialize(lab):
    plans=setup(lab)
    coordinator=Coordinator(i4b.t.TaskService(lab.sessions,i2.HOME,synthetic_only=True),plans,synthetic_only=True)
    return coordinator


def feed(coordinator):
    results=tuple(coordinator.process(value) for value in cases())
    if any(result.outcome not in (Outcome.COMMITTED,Outcome.REPLAY) for result in results):raise i2.Unavailable()
    return results



def experiment(coordinator, command):
    """Bounded named fixed evidence inputs, trusted terminal only; no arbitrary data."""
    if command in ('process','repeat'):return feed(coordinator)
    first=cases()[0]
    if command=='change':values=(replace(first,generation=2,safety=r.Safety.UNAVAILABLE),)
    elif command=='revert':values=(replace(first,generation=3),)
    elif command=='pages':values=tuple(replace(first,record_id='i5-page-'+str(n),observed_date=None,date_basis=DateBasis.NONE) for n in range(14))
    else:raise i2.Unavailable()
    results=tuple(coordinator.process(value) for value in values)
    if any(result.outcome not in (Outcome.COMMITTED,Outcome.REPLAY) for result in results):raise i2.Unavailable()
    return results


def interact(lab,server,app,thread,coordinator):
    timer=Timer(i2.RUN_SECONDS,lambda:(lab.close(),server.close()));timer.daemon=True;timer.start()
    commands=Queue(maxsize=1)
    def read():
        try:
            while True:
                line=input('i5> ');commands.put(line)
                if line.strip()=='quit':return
        except (EOFError,KeyboardInterrupt):commands.put('quit')
    Thread(target=read,daemon=True).start()
    try:
        print('I5 LOCAL FICTIONAL ONLY — no providers, models or production login.')
        print('Open '+app.origin+'/ in two independent browser profiles.')
        print('Commands: pending | approve REQUEST_ID clara|devon | process | repeat | change | revert | pages | quit')
        while not lab.stopped:
            try:parts=commands.get(timeout=0.5).split()
            except Empty:continue
            if parts==['quit']:break
            try:
                with lab.lock:
                    lab._now()
                    if parts==['pending']:print('Pairing requests: '+', '.join(lab.pending()))
                    elif len(parts)==3 and parts[0]=='approve':lab.approve(parts[1],parts[2]);print('Fictional browser session approved.')
                    elif len(parts)==1:
                        results=experiment(coordinator,parts[0])
                        print('Processed '+str(len(results))+' fixed fictional inputs. No Task was automatically accepted.')
                    else:raise i2.Unavailable()
            except Exception:print('Unavailable. Do not assume a write outcome or retry an uncertain operation; stop this disposable lab.')
    finally:
        timer.cancel();app.close();i2.stop(server,lab,thread)


def main():
    parser=argparse.ArgumentParser(description='I5 fixed fictional routing to real T1 Pending; no providers or models',allow_abbrev=False)
    parser.add_argument('--synthetic-only',action='store_true',required=True)
    args=parser.parse_args()
    try:
        with i2.disposable(synthetic_only=args.synthetic_only) as lab:
            coordinator=initialize(lab)
            app=i4b.Workbench(lab,1)
            try:
                server,app,thread=i2.serve(lab,application=app)
                interact(lab,server,app,thread,coordinator)
            finally:app.close()
    except (KeyboardInterrupt,EOFError):pass
    except Exception:parser.exit(1,'Fictional information lab unavailable. No private details are logged.\n')


if __name__=='__main__':main()
