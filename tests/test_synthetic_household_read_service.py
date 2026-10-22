"""New G1 fictional Meadow school / Lantern booking probes; no external datasets."""
import ast
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

from family_os import _synthetic_household_read_service as g


HOME = g.Household.CEDAR
MARA = g.Principal.MARA
LEON = g.Principal.LEON
MEADOW = g.SourceKey(HOME, g.Source.MARA_MAIL, g.Provider.ONE, g.Object.ONE)
LANTERN = replace(MEADOW, source=g.Source.LEON_MAIL)
FOREIGN = replace(MEADOW, household=g.Household.RIDGE, source=g.Source.RIDGE_MAIL)
FIRST = g.Observation(MEADOW, 1, g.Topic.BOOKING, g.Safety.SUSPICIOUS)
SECOND = g.Observation(LANTERN, 1, g.Topic.BOOKING, g.Safety.INDETERMINATE)
TASK = g.TaskFields(g.Task.BOOKING, g.Step.CHECK_BOOKING, g.Assignment.JOINT, g.TaskStatus.OPEN, 1)
PUBLICATION = g.PublishedTask(HOME, TASK, g.Permission.ALLOWED, (MEADOW, LANTERN))


def authorization():
    return g.Authorization(
        tuple(g.Membership(HOME, p, g.Permission.ALLOWED, 1) for p in g.Principal),
        tuple(g.SourceGrant(HOME, s, p, g.Permission.ALLOWED, 1, tuple(g.ReadScope))
              for s in (g.Source.MARA_MAIL, g.Source.LEON_MAIL) for p in g.Principal),
        tuple(g.TaskGrant(HOME, g.Task.BOOKING, p, g.Permission.ALLOWED, 1) for p in g.Principal))


def service(state=None, auth=None):
    s = g.ReadService(state or g.HouseholdState((FIRST, SECOND), (PUBLICATION,)),
                      authorization() if auth is None else auth, synthetic_only=True)
    return s


def context(s, actor=MARA):
    return s.harness_context(HOME, actor)


def change_source(s, actor=MARA, source=g.Source.LEON_MAIL, permission=g.Permission.REVOKED):
    a = s._authorization
    s.harness_replace_authorization(replace(a, sources=tuple(
        replace(v, permission=permission, revision=v.revision + 1)
        if (v.source, v.principal) == (source, actor) else v for v in a.sources)))


@pytest.mark.parametrize('query', (g.Query(), g.Query(1), g.Query(1, 1),
                                   g.Query(topic=g.Topic.BOOKING), g.Query(topic=g.Topic.SCHOOL)))
def test_two_equal_peers_receive_one_complete_unified_workspace(query):
    s = service()
    assert s.project(context(s, MARA), query) == s.project(context(s, LEON), query)
    all_rows = s.project(context(s))
    assert all_rows.observations.total == 2
    assert {r.key.source for r in all_rows.observations.rows} == {g.Source.MARA_MAIL, g.Source.LEON_MAIL}
    assert all_rows.tasks.rows == (TASK,)
    assert all_rows.security.total == 2


def test_one_shared_task_revision_and_assignment_not_owner_stores():
    s = service()
    amended = replace(TASK, revision=2, assignment=g.Assignment.LEON)
    s.harness_replace_state(replace(s._state, tasks=(replace(PUBLICATION, fields=amended),)))
    assert s.project(context(s, MARA)).tasks.rows == (amended,)
    assert s.project(context(s, LEON)).tasks.rows == (amended,)
    assert s._state.tasks[0].provenance == (MEADOW, LANTERN)


@pytest.mark.parametrize('actor', tuple(g.Principal))
def test_source_revocation_preserves_independent_publication_without_provenance(actor):
    s = service(); c = context(s, actor)
    before = s.project(c).tasks
    change_source(s, actor)
    result = s.project(c)
    assert result.observations.total == result.security.total == 1
    assert result.tasks == before
    assert {f.name for f in fields(result.tasks.rows[0])} == {'task', 'step', 'assignment', 'status', 'revision'}
    assert s.observation(c, LANTERN) is None
    other = LEON if actor is MARA else MARA
    assert s.project(context(s, other)).observations.total == 2


def test_private_arrivals_evidence_changes_and_provenance_do_not_enrich_shared_task():
    s = service(); c = context(s); change_source(s)
    before = s.project(c)
    s.harness_replace_state(g.HouseholdState((FIRST, replace(SECOND, generation=99, safety=g.Safety.HIGH_RISK),
                                              replace(SECOND, key=replace(LANTERN, object=g.Object.TWO))),
                                             (replace(PUBLICATION, provenance=(LANTERN, FOREIGN)),)))
    assert s.project(c) == before


@pytest.mark.parametrize('permission', (g.Permission.REVOKED, g.Permission.UNKNOWN, g.Permission.STALE))
def test_task_read_revocation_is_independent_of_source_read(permission):
    s = service(); c = context(s)
    a = s._authorization
    s.harness_replace_authorization(replace(a, tasks=tuple(replace(v, permission=permission, revision=2)
                                                          if v.principal is MARA else v for v in a.tasks)))
    result = s.project(c)
    assert result.tasks.total == 0
    assert result.observations.total == result.security.total == 2
    assert s.project(context(s, LEON)).tasks.total == 1


@pytest.mark.parametrize('publication', (g.Permission.REVOKED, g.Permission.UNKNOWN, g.Permission.STALE))
def test_read_grant_without_current_approved_publication_discloses_no_task(publication):
    s = service(g.HouseholdState((FIRST, SECOND), (replace(PUBLICATION, publication=publication),)))
    assert s.project(context(s)).tasks == g.Page((), 0, False)


def test_no_source_rights_still_allows_independently_published_task():
    s = service(); c = context(s)
    for source in (g.Source.MARA_MAIL, g.Source.LEON_MAIL):
        change_source(s, source=source)
    result = s.project(c)
    assert result.observations == result.security == g.Page((), 0, False)
    assert result.tasks.rows == (TASK,)


@pytest.mark.parametrize('permission', (g.Permission.REVOKED, g.Permission.UNKNOWN, g.Permission.STALE))
@pytest.mark.parametrize('revision', (1, 2))
@pytest.mark.parametrize('reverse', (False, True))
def test_contradictory_source_assertions_deny_only_affected_mailbox(permission, revision, reverse):
    a = authorization()
    original = next(v for v in a.sources if v.principal is MARA and v.source is g.Source.LEON_MAIL)
    grants = a.sources + (replace(original, permission=permission, revision=revision),)
    s = service(auth=replace(a, sources=tuple(reversed(grants)) if reverse else grants))
    result = s.project(context(s))
    assert result.observations.rows == (g.ObservationEntry(MEADOW, 1, g.Topic.BOOKING),)
    assert result.security.total == 1
    assert result.tasks.total == 1
    assert s.project(context(s, LEON)).observations.total == 2


def test_numeric_latest_allowed_does_not_resolve_ambiguous_assertions():
    a = authorization(); original = a.sources[0]
    s = service(auth=replace(a, sources=a.sources + (replace(original, revision=2),)))
    assert s.project(context(s)).observations.total == 1


@pytest.mark.parametrize('reverse', (False, True))
def test_consistent_grant_and_observation_duplicates_add_no_authority_or_count(reverse):
    a = authorization(); sources = a.sources + a.sources
    state = g.HouseholdState((FIRST, SECOND, FIRST, SECOND), (PUBLICATION, PUBLICATION))
    s = service(state, replace(a, sources=tuple(reversed(sources)) if reverse else sources))
    baseline = service()
    assert s.project(context(s)) == baseline.project(context(baseline))
    assert s.project(context(s)).tasks.total == 1
    assert s.project(context(s)).security.total == 2


@pytest.mark.parametrize('scope', tuple(g.ReadScope))
def test_observation_and_security_purpose_are_explicit_not_operation_rights(scope):
    a = authorization(); a = replace(a, sources=tuple(replace(v, scopes=(scope,)) for v in a.sources))
    s = service(auth=a); result = s.project(context(s))
    assert result.observations.total == (2 if scope is g.ReadScope.OBSERVATIONS else 0)
    assert result.security.total == (2 if scope is g.ReadScope.SECURITY else 0)
    if result.observations.rows:
        assert not hasattr(result.observations.rows[0], 'safety')
    assert not hasattr(result, 'operation_permission') and not hasattr(result, 'reviewer_permission')
    assert not any(hasattr(s, name) for name in ('dispatch', 'quarantine', 'restore', 'reconcile', 'approve'))


@pytest.mark.parametrize('permission', tuple(g.Permission))
@pytest.mark.parametrize('actor', tuple(g.Principal))
def test_membership_alone_never_grants_source_or_task_access(permission, actor):
    a = g.Authorization((g.Membership(HOME, actor, permission, 1),))
    s = service(auth=a)
    if permission is g.Permission.ALLOWED:
        assert s.project(context(s, actor)) == g.Projection(*(g.Page((), 0, False),) * 3)
    else:
        with pytest.raises(g.AccessUnavailable, match='^Read access unavailable$'):
            context(s, actor)


@pytest.mark.parametrize('fabrication', ('dict', 'copy', 'other-service', 'foreign-household', 'object'))
def test_fabricated_contexts_do_not_establish_authority(fabrication):
    s = service(); c = context(s)
    fake = {'dict': {'household': HOME, 'principal': MARA}, 'copy': replace(c),
            'other-service': context(service()), 'foreign-household': replace(c, household=g.Household.RIDGE),
            'object': object()}[fabrication]
    with pytest.raises(g.AccessUnavailable, match='^Read access unavailable$'):
        s.project(fake)
    with pytest.raises(g.AccessUnavailable):
        s.observation(fake, FOREIGN)


@pytest.mark.parametrize('permission', (g.Permission.UNKNOWN, g.Permission.REVOKED, g.Permission.STALE))
def test_changed_membership_invalidates_context_and_prepared_query(permission):
    s = service(); c = context(s); ticket = s.prepare(c, g.Query())
    a = s._authorization
    s.harness_replace_authorization(replace(a, memberships=tuple(replace(v, permission=permission, revision=2)
                                                                if v.principal is MARA else v for v in a.memberships)))
    for call in (lambda: s.project(c), lambda: s.consume(c, ticket), lambda: s.observation(c, MEADOW)):
        with pytest.raises(g.AccessUnavailable):
            call()
    assert s.project(context(s, LEON)).observations.total == 2


def test_renewed_membership_does_not_revive_old_context_or_prepared_request():
    s = service(); c = context(s); ticket = s.prepare(c, g.Query())
    a = s._authorization
    s.harness_replace_authorization(replace(a, memberships=tuple(replace(v, revision=2) for v in a.memberships)))
    with pytest.raises(g.AccessUnavailable):
        s.consume(c, ticket)
    assert s.project(context(s)).observations.total == 2


def test_membership_conflict_fails_closed_and_foreign_household_never_shadows_current():
    a = authorization()
    s = service(auth=replace(a, memberships=a.memberships + (replace(a.memberships[0], permission=g.Permission.REVOKED),)))
    with pytest.raises(g.AccessUnavailable):
        context(s)
    assert s.project(context(s, LEON)).observations.total == 2
    a = replace(a, memberships=a.memberships + (g.Membership(g.Household.RIDGE, MARA, g.Permission.UNKNOWN, 1),))
    s = service(auth=a)
    assert s.project(context(s)).observations.total == 2
    with pytest.raises(g.AccessUnavailable):
        s.harness_context(g.Household.RIDGE, MARA)


@pytest.mark.parametrize('hidden_count', (0, 1, 65, 200))
@pytest.mark.parametrize('query', (g.Query(1), g.Query(1, 1), g.Query(topic=g.Topic.BOOKING),
                                   g.Query(topic=g.Topic.HEALTH)))
def test_hidden_population_duplicates_conflicts_and_overlimit_do_not_affect_results(hidden_count, query):
    s = service(); c = context(s); change_source(s)
    before = s.project(c, query)
    hidden = tuple(replace(SECOND, generation=1 + i % 100, topic=g.Topic.HEALTH) for i in range(hidden_count))
    s.harness_replace_state(g.HouseholdState((FIRST,) + hidden + (g.Observation(FOREIGN, 1, g.Topic.HEALTH, g.Safety.HIGH_RISK),),
                                             (PUBLICATION,)))
    assert s.project(c, query) == before
    assert s.observation(c, LANTERN) is s.observation(c, FOREIGN) is None


@pytest.mark.parametrize('count', (0, 65, 200))
def test_all_denied_hidden_data_does_not_change_empty_projection_or_errors(count):
    s = service(auth=replace(authorization(), sources=(), tasks=()))
    c = context(s); before = s.project(c)
    s.harness_replace_state(g.HouseholdState((FIRST, SECOND) * count, (PUBLICATION,) * count))
    assert s.project(c) == before == g.Projection(*(g.Page((), 0, False),) * 3)
    assert s.observation(c, MEADOW) is None


def test_visible_inconsistent_current_snapshots_fail_without_exposing_content():
    s = service(g.HouseholdState((FIRST, replace(FIRST, generation=2)), ()))
    with pytest.raises(g.ContractError, match='^Synthetic read contract rejected$'):
        s.project(context(s))
    with pytest.raises(g.ContractError):
        s.observation(context(s), MEADOW)


def test_visible_cap_applies_to_unique_authorized_items_not_hidden_or_repeated_inputs():
    observations = tuple(g.Observation(replace(MEADOW, source=source, provider=provider, object=obj),
                                       1, g.Topic.SCHOOL, g.Safety.SUSPICIOUS)
                         for source in (g.Source.MARA_MAIL, g.Source.LEON_MAIL)
                         for provider in g.Provider for obj in g.Object)
    s = service(g.HouseholdState(observations, ()))
    with pytest.raises(g.ContractError):
        s.project(context(s))
    change_source(s)
    result = s.project(context(s), g.Query(3))
    assert result.observations.total == 10
    assert len(result.observations.rows) == 3 and result.observations.has_more


def test_source_identity_is_not_principal_or_cross_source_title_similarity():
    s = service(g.HouseholdState((FIRST, FIRST, SECOND), (PUBLICATION,)))
    result = s.project(context(s))
    assert result.observations.total == 2 and result.tasks.total == 1
    assert FIRST.topic is SECOND.topic  # Never merge identical topic / object markers across mailboxes.


def test_prepared_query_rechecks_source_and_task_revocation_and_contains_no_projection():
    s = service(); c = context(s)
    ticket = s.prepare(c, g.Query())
    assert {f.name for f in fields(ticket)} == {'context', 'query'}
    change_source(s)
    a = s._authorization
    s.harness_replace_authorization(replace(a, tasks=tuple(v for v in a.tasks if v.principal is not MARA)))
    result = s.consume(c, ticket)
    assert result.observations.total == result.security.total == 1 and result.tasks.total == 0
    assert s.consume(c, ticket) == result
    with pytest.raises(g.AccessUnavailable):
        s.consume(context(s, LEON), ticket)


@pytest.mark.parametrize('safety', tuple(g.Safety))
def test_unified_security_never_treats_unknown_stale_or_promotional_risk_as_authority(safety):
    s = service(g.HouseholdState((replace(FIRST, safety=safety, topic=g.Topic.PROMOTION),), ()))
    result = s.project(context(s))
    assert result.security.total == (0 if safety is g.Safety.CLEAR else 1)
    assert result.tasks.total == 0
    if result.security.rows:
        assert {f.name for f in fields(result.security.rows[0])} == {'key', 'generation', 'safety'}


def test_task_provenance_is_never_read_or_used_for_duplicate_checks():
    s = service(g.HouseholdState((FIRST, SECOND), (PUBLICATION, replace(PUBLICATION, provenance=(FOREIGN,)))))
    assert s.project(context(s)).tasks.rows == (TASK,)
    denied = replace(PUBLICATION, publication=g.Permission.REVOKED)
    s.harness_replace_state(g.HouseholdState((FIRST, SECOND), (PUBLICATION, denied)))
    assert s.project(context(s)).tasks.rows == ()


def test_task_grant_conflict_cannot_override_revoke_or_affect_unrelated_sources():
    a = authorization(); a = replace(a, tasks=a.tasks + (replace(a.tasks[0], permission=g.Permission.REVOKED),))
    s = service(auth=a)
    assert s.project(context(s)).tasks.total == 0
    assert s.project(context(s)).observations.total == 2
    assert s.project(context(s, LEON)).tasks.total == 1


@pytest.mark.parametrize('limit', (0, -1, 9, True, '2', None))
def test_invalid_page_limits_fail_bounded_and_content_free(limit):
    with pytest.raises(g.ContractError):
        g.Query(limit=limit)


@pytest.mark.parametrize('offset', (-1, 17, True, '1', None))
def test_invalid_offsets_fail(offset):
    with pytest.raises(g.ContractError):
        g.Query(offset=offset)


@pytest.mark.parametrize('flag', (False, 1, 'true', None))
def test_exact_synthetic_opt_in_precedes_initialization(flag):
    with pytest.raises(g.ContractError):
        g.ReadService(object(), object(), synthetic_only=flag)


@pytest.mark.parametrize('value', (0, -1, 1001, True, '1', None))
def test_invalid_revisions_rejected(value):
    with pytest.raises(g.ContractError):
        replace(FIRST, generation=value)
    with pytest.raises(g.ContractError):
        replace(authorization().memberships[0], revision=value)


@pytest.mark.parametrize('cls,field,value', ((g.SourceKey, 'source', 'private-mailbox'),
    (g.Observation, 'topic', 'private-subject'), (g.PublishedTask, 'provenance', ('private-id',)),
    (g.SourceGrant, 'scopes', ('quarantine',)), (g.SourceGrant, 'scopes', (g.ReadScope.SECURITY,) * 2),
    (g.SourceGrant, 'permission', 'allowed'), (g.TaskFields, 'step', 'private-task'),
    (g.Query, 'topic', 'secret-search')))
def test_closed_value_contract_rejects_private_text_and_authority_injection(cls, field, value):
    originals = {g.SourceKey: MEADOW, g.Observation: FIRST, g.PublishedTask: PUBLICATION,
                 g.SourceGrant: authorization().sources[0], g.TaskFields: TASK, g.Query: g.Query()}
    with pytest.raises(g.ContractError):
        replace(originals[cls], **{field: value})


def test_results_and_shared_state_are_immutable_and_queries_do_not_write():
    s = service(); c = context(s); state = s._state; auth = s._authorization
    projection = s.project(c)
    with pytest.raises(FrozenInstanceError):
        projection.tasks.rows[0].status = g.TaskStatus.COMPLETE
    with pytest.raises(FrozenInstanceError):
        state.observations = ()
    assert s.project(c) == projection
    assert s._state is state and s._authorization is auth


def test_no_production_wiring_research_dependencies_or_io(monkeypatch):
    root = Path(__file__).parents[1]
    path = root / 'src/family_os/_synthetic_household_read_service.py'
    tree = ast.parse(path.read_text())
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imports |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imports == {'dataclasses', 'enum'}
    for other in (root / 'src').rglob('*.py'):
        if other != path:
            assert '_synthetic_household_read_service' not in other.read_text()
    def blocked(*args, **kwargs):
        raise AssertionError('I/O forbidden in G1')
    monkeypatch.setattr('builtins.open', blocked)
    monkeypatch.setattr('socket.socket', blocked)
    s = service(); c = context(s)
    assert s.consume(c, s.prepare(c, g.Query())).observations.total == 2


@pytest.mark.parametrize('actor', tuple(g.Principal))
def test_valid_foreign_membership_still_limits_context_to_one_household(actor):
    a = authorization()
    a = replace(a, memberships=a.memberships + (g.Membership(g.Household.RIDGE, actor, g.Permission.ALLOWED, 1),),
                sources=a.sources + (g.SourceGrant(g.Household.RIDGE, g.Source.RIDGE_MAIL, actor,
                                                  g.Permission.ALLOWED, 1, tuple(g.ReadScope)),))
    s = service(g.HouseholdState((FIRST, SECOND, g.Observation(FOREIGN, 1, g.Topic.HEALTH, g.Safety.HIGH_RISK)),
                                 (PUBLICATION,)), a)
    assert s.project(context(s, actor)).observations.total == 2
    foreign = s.harness_context(g.Household.RIDGE, actor)
    assert s.project(foreign).observations.rows == (g.ObservationEntry(FOREIGN, 1, g.Topic.HEALTH),)
    assert s.project(foreign).tasks.total == 0
    assert s.observation(foreign, MEADOW) is None


@pytest.mark.parametrize('actor', tuple(g.Principal))
def test_read_projection_search_and_link_are_fresh_without_recurring_sharing_prompts(actor):
    s = service(); c = context(s, actor)
    before = s._authorization
    for _ in range(3):
        assert s.project(c, g.Query(topic=g.Topic.BOOKING)).observations.total == 2
        assert s.observation(c, LANTERN) == g.ObservationEntry(LANTERN, 1, g.Topic.BOOKING)
    assert s._authorization is before
    change_source(s, actor=actor)
    assert s.observation(c, LANTERN) is None
    assert s.project(c, g.Query(topic=g.Topic.BOOKING)).observations.total == 1


@pytest.mark.parametrize('reverse', (False, True))
def test_hidden_unpublished_task_conflicts_cannot_affect_authorized_tasks(reverse):
    hidden = replace(PUBLICATION, fields=replace(TASK, task=g.Task.SCHOOL, step=g.Step.CHECK_SCHOOL))
    tasks = (PUBLICATION,) + tuple(replace(hidden, fields=replace(hidden.fields, revision=i % 100 + 1))
                                  for i in range(100))
    s = service(g.HouseholdState((FIRST, SECOND), tuple(reversed(tasks)) if reverse else tasks))
    assert s.project(context(s)).tasks.rows == (TASK,)


@pytest.mark.parametrize('permission', (g.Permission.REVOKED, g.Permission.UNKNOWN, g.Permission.STALE))
def test_read_denial_hides_visible_conflicts_before_consistency_validation(permission):
    s = service(g.HouseholdState((FIRST, replace(FIRST, generation=2), SECOND), ()))
    change_source(s, source=g.Source.MARA_MAIL, permission=permission)
    assert s.project(context(s)).observations.total == 1
    assert s.observation(context(s), MEADOW) is None


def test_harness_updates_are_typed_atomic_and_contexts_are_service_local():
    s = service(); state = s._state; auth = s._authorization
    with pytest.raises(g.ContractError):
        s.harness_replace_state({})
    with pytest.raises(g.ContractError):
        s.harness_replace_authorization({})
    assert s._state is state and s._authorization is auth
    with pytest.raises(g.AccessUnavailable):
        service().project(context(s))


def test_authorization_precedes_query_or_lookup_validation():
    s = service()
    for operation in (lambda: s.project({}, object()), lambda: s.observation({}, object()),
                      lambda: s.prepare({}, object()), lambda: s.consume({}, object())):
        with pytest.raises(g.AccessUnavailable, match='^Read access unavailable$'):
            operation()


def test_page_order_and_search_are_deterministic_from_authorized_keys_only():
    state = g.HouseholdState((SECOND, FIRST), (PUBLICATION,))
    s = service(state); c = context(s)
    before = s.project(c, g.Query(1))
    s.harness_replace_state(replace(state, observations=tuple(reversed(state.observations))))
    assert s.project(c, g.Query(1)) == before
    assert s.project(c, g.Query(1, 1)).observations.rows != before.observations.rows
    assert s.project(c, g.Query(1, 2)).observations == g.Page((), 2, False)
    assert s.project(c, g.Query(topic=g.Topic.PROMOTION)).observations == g.Page((), 0, False)


def observation_only_authorization():
    a = authorization()
    return replace(a, sources=tuple(replace(v, scopes=(g.ReadScope.OBSERVATIONS,)) for v in a.sources))


@pytest.mark.parametrize('actor', tuple(g.Principal))
@pytest.mark.parametrize('reverse', (False, True))
@pytest.mark.parametrize('query', (g.Query(), g.Query(1), g.Query(1, 1),
                                   g.Query(topic=g.Topic.BOOKING), g.Query(topic=g.Topic.SCHOOL)))
def test_observation_only_safety_conflicts_cannot_change_projection_or_lookup(actor, reverse, query):
    baseline = service(auth=observation_only_authorization())
    expected = baseline.project(context(baseline, actor), query)
    duplicates = (FIRST, replace(FIRST, safety=g.Safety.CLEAR),
                  replace(FIRST, safety=g.Safety.HIGH_RISK), SECOND)
    s = service(g.HouseholdState(tuple(reversed(duplicates)) if reverse else duplicates, (PUBLICATION,)),
                observation_only_authorization())
    c = context(s, actor)
    assert s.project(c, query) == expected
    assert s.observation(c, MEADOW) == g.ObservationEntry(MEADOW, 1, g.Topic.BOOKING)


@pytest.mark.parametrize('safety', tuple(g.Safety))
def test_observation_only_safety_changes_preserve_output_and_prepared_query(safety):
    s = service(auth=observation_only_authorization()); c = context(s)
    before = s.project(c), s.observation(c, MEADOW)
    prepared = s.prepare(c, g.Query())
    s.harness_replace_state(replace(s._state, observations=(replace(FIRST, safety=safety), SECOND)))
    assert (s.project(c), s.observation(c, MEADOW)) == before
    assert s.consume(c, prepared) == before[0]


@pytest.mark.parametrize('reverse', (False, True))
@pytest.mark.parametrize('query', (g.Query(), g.Query(topic=g.Topic.SCHOOL)))
def test_security_read_rejects_contradictory_authorized_risk_even_when_filtered_out(reverse, query):
    duplicates = (replace(FIRST, safety=g.Safety.CLEAR), replace(FIRST, safety=g.Safety.HIGH_RISK))
    s = service(g.HouseholdState(tuple(reversed(duplicates)) if reverse else duplicates, (PUBLICATION,)))
    with pytest.raises(g.ContractError, match='^Synthetic read contract rejected$'):
        s.project(context(s), query)
    # The direct lookup is an observation-scope operation even for a dual-scope reader.
    assert s.observation(context(s), MEADOW) == g.ObservationEntry(MEADOW, 1, g.Topic.BOOKING)


@pytest.mark.parametrize('scopes', ((g.ReadScope.OBSERVATIONS,), (g.ReadScope.SECURITY,), tuple(g.ReadScope)))
@pytest.mark.parametrize('change', ({'generation': 2}, {'topic': g.Topic.HEALTH}))
def test_authorized_generation_and_topic_conflicts_still_fail_closed(scopes, change):
    a = authorization(); a = replace(a, sources=tuple(replace(v, scopes=scopes) for v in a.sources))
    s = service(g.HouseholdState((FIRST, replace(FIRST, **change)), ()), a)
    with pytest.raises(g.ContractError):
        s.project(context(s))
    if g.ReadScope.OBSERVATIONS in scopes:
        with pytest.raises(g.ContractError):
            s.observation(context(s), MEADOW)


@pytest.mark.parametrize('topic', tuple(g.Topic))
def test_security_topic_is_authorized_filter_dimension_and_consistent_duplicates_coalesce(topic):
    a = authorization(); a = replace(a, sources=tuple(replace(v, scopes=(g.ReadScope.SECURITY,)) for v in a.sources))
    o = replace(FIRST, topic=topic)
    s = service(g.HouseholdState((o, o), ()), a)
    result = s.project(context(s), g.Query(topic=topic))
    assert result.security == g.Page((g.SecurityEntry(MEADOW, 1, FIRST.safety),), 1, False)
    assert result.observations == g.Page((), 0, False)
    other = next(t for t in g.Topic if t is not topic)
    assert s.project(context(s), g.Query(topic=other)).security == g.Page((), 0, False)


@pytest.mark.parametrize('scopes', ((g.ReadScope.OBSERVATIONS,), (g.ReadScope.SECURITY,), tuple(g.ReadScope)))
def test_hidden_and_cross_household_field_conflicts_remain_invisible_by_scope(scopes):
    a = authorization(); a = replace(a, sources=tuple(replace(v, scopes=scopes) for v in a.sources))
    s = service(auth=a); c = context(s); change_source(s)
    before = s.project(c)
    hidden = tuple(replace(SECOND, safety=safety, topic=g.Topic.HEALTH) for safety in g.Safety)
    foreign = tuple(g.Observation(FOREIGN, 1, g.Topic.SCHOOL, safety) for safety in g.Safety)
    s.harness_replace_state(g.HouseholdState((FIRST,) + hidden * 20 + foreign, (PUBLICATION,)))
    assert s.project(c) == before
    assert s.observation(c, LANTERN) is s.observation(c, FOREIGN) is None


def test_scope_specific_consistency_preserves_equal_peer_views_and_independent_revocation():
    s = service(g.HouseholdState((FIRST, replace(FIRST, safety=g.Safety.HIGH_RISK), SECOND), (PUBLICATION,)),
                observation_only_authorization())
    mara, leon = context(s), context(s, LEON)
    assert s.project(mara) == s.project(leon)
    before_task = s.project(mara).tasks
    change_source(s)
    assert s.project(mara).observations.total == 1
    assert s.project(leon).observations.total == 2
    assert s.project(mara).tasks == s.project(leon).tasks == before_task
    a = s._authorization
    s.harness_replace_authorization(replace(a, tasks=tuple(v for v in a.tasks if v.principal is not MARA)))
    assert s.project(mara).tasks.total == 0
    assert s.project(leon).tasks == before_task
