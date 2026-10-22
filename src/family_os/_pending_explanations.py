"""I6 fictional, current-authority explanation projection; no provider/model I/O."""
from dataclasses import dataclass
from datetime import date
from enum import Enum
import json

from sqlalchemy import select
from family_os import _fictional_information as f
from family_os._household_tasks import TaskService, TaskError
from family_os.schema import fictional_information_revision as ledger

CONTRACT_VERSION='i6-pending-explanation-v1'


class Action(Enum):
    SUPPORTED='supported'
    CONFLICTING='conflicting'
    UNSUPPORTED='unsupported'
    NONE='none'
    UNAVAILABLE='unavailable'


class Reason(Enum):
    SUPPORTED='structured-support'
    CONFLICT='conflicting-action-evidence'
    MISSING_STEP='missing-action-step'
    INSUFFICIENT='insufficient-action-evidence'
    SERVICE='independent-service-only'
    RECHECK='current-evidence-unavailable'


@dataclass(frozen=True)
class Explanation:
    id: str
    revision: int
    generation: int
    definition: str
    step: str | None
    supported_date: date | None
    action: Action
    reasons: tuple[Reason,...]
    safety: str | None
    can_accept: bool


class ExplanationService:
    """Uses T1's exact session/source/Pending transaction, never a new grant engine."""
    def __init__(self,tasks,*,synthetic_only=False):
        if synthetic_only is not True or type(tasks) is not TaskService:raise TaskError()
        self._tasks=tasks

    def read(self,bearer,resource,revision):
        try:
            if (type(resource) is not str or len(resource)>64 or type(revision) is not int
                    or not 1<=revision<=1000000):raise TaskError()
            with self._tasks._transaction(bearer) as (c,actor,now):
                # Access first, before ledger lookup, consistency or parsing. Accepted
                # Tasks never establish source/Pending authority or expose origin.
                row,source=self._tasks._pending(c,actor,resource)
                if row['resolution']!='unresolved' or row['revision']!=revision:raise TaskError()
                view=self._tasks._pending_view(row,source)
                # This private finite container is decoded only after access. It
                # never leaves the service; safety uses T1's authorized CASE.
                bound=c.execute(select(ledger.c.generation,ledger.c.definition_version,
                    ledger.c.evidence_fingerprint,ledger.c.evidence_json,ledger.c.effect,ledger.c.origin,ledger.c.record_id)
                    .where(ledger.c.household_id==self._tasks._household,ledger.c.pending_id==resource,
                        ledger.c.source_account_id==row['source_account_id'])
                    .order_by(ledger.c.generation.desc()).limit(1)).mappings().one_or_none()
                if (bound is None or bound['origin']!=f.Origin.FIXTURE.value
                        or bound['definition_version']!=f.CONTRACT_VERSION
                        or (bound['generation'],bound['evidence_fingerprint'],bound['definition_version'])!=
                            (row['generation'],row['evidence_fingerprint'],row['definition_version'])
                        or bound['effect'] not in ('created','updated','blocked')):raise TaskError()
                f._record(bound['record_id'])
                if f.pending_identity(self._tasks._household,f.Source(row['source_account_id']),bound['record_id'])!=resource:raise TaskError()
                if bound['effect']=='blocked':
                    # I5 intentionally withheld the new business payload. Explain
                    # only invalidation, never rematerialize it or revive clearance.
                    action=Action.UNAVAILABLE;reasons=(Reason.RECHECK,)
                    if source['security'] and view.safety!='unknown':raise TaskError()
                else:
                    evidence=json.loads(bound['evidence_json'])
                    if type(evidence) is not dict:raise TaskError()
                    # Discard security BEFORE validating the authorized business
                    # subset. A security-only value cannot change these results/errors.
                    keys=('action','importance','promotion','informational','expiry','step','observed_date','date_basis')
                    business={k:evidence[k] for k in keys}
                    if source['security']:
                        safety=f.routing.Safety[evidence['safety']]
                        expected='clear' if safety is f.routing.Safety.SAFE_TO_ROUTE else 'high-risk' if safety in (f.routing.Safety.SUSPICIOUS,f.routing.Safety.HIGH_RISK) else 'unknown'
                        if f._hash(evidence)!=bound['evidence_fingerprint'] or view.safety!=expected:raise TaskError()
                    b=f.routing.Business(action=f.routing.ActionEvidence[business['action']],
                        importance=f.routing.Importance[business['importance']],promotion=business['promotion'],
                        informational=business['informational'],expiry=f.routing.Expiry[business['expiry']])
                    step=None if business['step'] is None else f.Step(business['step'])
                    when=None if business['observed_date'] is None else date.fromisoformat(business['observed_date'])
                    basis=f.DateBasis(business['date_basis'])
                    if ((when is None)!=(basis is f.DateBasis.NONE)
                            or (when is not None and (not 2030<=when.year<=2045 or when.isoformat()!=business['observed_date']))):raise TaskError()
                    # Only the authorized materialized fields can appear. No inferred
                    # dates, private source IDs, arbitrary text, hashes or reason prose.
                    if view.step is not None and (step is not view.step or b.action is not f.routing.ActionEvidence.SUPPORTED):raise TaskError()
                    if view.supported_date!=(when if view.supported and basis is f.DateBasis.ACTION else None):raise TaskError()
                    action=Action[b.action.name]
                    reasons=(Reason.CONFLICT,) if action is Action.CONFLICTING else (
                        (Reason.SUPPORTED,) if action is Action.SUPPORTED and view.step is not None else
                        (Reason.MISSING_STEP,) if action is Action.SUPPORTED else
                        (Reason.SERVICE,) if b.promotion and b.importance is f.routing.Importance.IMPORTANT else
                        (Reason.INSUFFICIENT,))
                self._tasks._sessions._touch(c,actor,now)
                result=Explanation(view.id,view.revision,view.binding.generation,view.binding.definition,
                    None if view.step is None else view.step.value,view.supported_date,action,reasons,view.safety,view.can_accept)
            return result
        except Exception:raise TaskError() from None
