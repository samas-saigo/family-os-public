"""New invented responsibility/page cases; trusted test setup, never an HTTP route."""
from dataclasses import replace
from hashlib import sha256
from sqlalchemy import insert
from family_os.schema import household_pending_item as pending, pending_member_right as right, pending_task_publication as plan


def seed(app, bearer):
    t, i2 = app.tasks, app.lab
    from family_os import _household_tasks as domain
    from family_os._household_authorization import authorization_transaction
    rows = []
    # Every bucket exceeds the actual UI page size; both step and tracking states.
    for assignee in ('i2-clara', 'i2-devon', 'joint'):
        for n in range(14):
            resource = 'responsibility-fiction-' + assignee + '-' + str(n)
            with authorization_transaction(i2.sessions._engine, t._household) as c:
                c.execute(insert(pending).values(household_id=t._household, id=resource,
                    source_account_id='i4a-shared-source',kind='action',supported=True,safety='clear',
                    step='school-session' if n % 2 else 'home-visit',supported_date=None,
                    generation=1,evidence_fingerprint=sha256(resource.encode()).hexdigest(),
                    definition_version='responsibility-fiction-v1',resolution='unresolved',revision=1))
                for table, permissions in [(right,dict(can_read=True,can_review=True,can_publish=True,reviewed=False,disposition='active')),
                                           (plan,dict(can_read=True,can_edit=True,can_history=True))]:
                    c.execute(insert(table),[dict(household_id=t._household,pending_id=resource,person_id=peer,
                        state='allowed',revision=1,membership_revision=1,**permissions) for peer in ('i2-clara','i2-devon')])
            _, command = t.prepare_acceptance(bearer, resource)
            result = t.apply(bearer, replace(command,assignee=assignee), confirm=True)
            assert result.outcome is domain.Outcome.COMMITTED
            if n % 2:
                _, commands = t.prepare_edits(bearer,result.task_id)
                command = next(c for c in commands if c.status is domain.Status.COMPLETED)
                assert t.apply(bearer,command,confirm=True).outcome is domain.Outcome.COMMITTED
            rows.append((result.task_id,assignee,'school-session' if n % 2 else 'home-visit','completed' if n % 2 else 'pending'))
    return rows
