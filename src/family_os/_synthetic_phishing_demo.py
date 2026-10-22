"""Stage C: opt-in, in-memory synthetic UX; never a household service or executor."""
from dataclasses import dataclass, replace
from enum import Enum
import sys

VERSION = "synthetic-action-first-demo-v2"
DISPLAY_CAP = 2  # Demonstration only; not a production attention/retention policy.
MAX_INPUT = 64
MAX_EVENTS = 32  # Per card, so inaccessible history cannot consume another card's budget.
NOTICE = ("SYNTHETIC ONLY — disposable single-operator session; no authentication.\n"
          "Review is not acceptance. Accepted steps are simulations, never tasks.\n"
          "Quarantine/restore are simulations, never mailbox operations. No AI or network.")


class Card(Enum):
    LIBRARY = "Invented library equipment return"
    SCHOOL = "Invented urgent school permission question"
    CLINIC = "Invented urgent clinic preparation notice"
    BANK = "Invented urgent bank service notice"
    MIXED = "Invented service question with stationery advertisement"
    CONFLICT = "Invented conflicting workshop instructions"
    INFORMATION = "Invented harmless venue information"
    OFFER = "Invented expired gardening offer"
    LURE = "Invented suspicious reward promotion"
    PRIVATE = "Invented source-B appointment question"


class View(Enum):
    TODO = "My To-do"
    PENDING = "Pending Confirmation"
    SECURITY = "Security Review"
    INFORMATION = "Information"
    OFFERS = "Offers"


class Operation(Enum):
    REVIEW = "confirm-review"
    ACCEPT = "confirm-accept"
    DEFER = "confirm-defer"
    QUARANTINE = "confirm-quarantine"
    RESTORE = "confirm-restore"
    CHANGE = "confirm-change"
    REVERT = "confirm-revert"


class DemoError(ValueError):
    def __init__(self):
        super().__init__("Synthetic intention rejected; refresh before trying again.")


@dataclass(frozen=True)
class State:
    case: object
    evidence: object
    recovery: object = None
    deferred: bool = False
    revision: int = 0


@dataclass(frozen=True)
class Command:
    card: Card
    expected: State
    operation: Operation
    request: int
    conditions: object = None

    def __post_init__(self):
        if (type(self.card) is not Card or type(self.expected) is not State
                or type(self.operation) is not Operation or type(self.request) is not int
                or not 1 <= self.request <= MAX_EVENTS):
            raise DemoError()


@dataclass(frozen=True)
class Event:
    command: Command
    result: State


class Session:
    """Finite curated harness. Declared grants are not real identity authentication."""
    def __init__(self, routing, policy):
        self.a, self.p = routing, policy
        self.grants = {routing.Source.A: routing.Permission.ALLOWED,
                       routing.Source.B: routing.Permission.DENIED}
        self.states, self.originals, self.events = {}, {}, ()
        a, p = routing, policy
        supported = a.Business(action=a.ActionEvidence.SUPPORTED, importance=a.Importance.IMPORTANT)
        important = a.Business(importance=a.Importance.IMPORTANT)
        # New authored scenarios; no evaluation-corpus imports or inference.
        scenarios = (
            (Card.LIBRARY, supported, (p.Finding.CHECKED_CLEAR,), p.EvidenceState.CURRENT),
            (Card.SCHOOL, important, (p.Finding.ANOMALY,), p.EvidenceState.CURRENT),
            (Card.CLINIC, supported, (p.Finding.IMPERSONATION,), p.EvidenceState.CURRENT),
            (Card.BANK, important, (), p.EvidenceState.UNAVAILABLE),
            (Card.MIXED, replace(important, promotion=True), (p.Finding.CHECKED_CLEAR,), p.EvidenceState.CURRENT),
            (Card.CONFLICT, replace(important, action=a.ActionEvidence.CONFLICTING),
             (p.Finding.CHECKED_CLEAR,), p.EvidenceState.CURRENT),
            (Card.INFORMATION, a.Business(informational=True, importance=a.Importance.NOT_IMPORTANT),
             (p.Finding.CHECKED_CLEAR,), p.EvidenceState.CURRENT),
            (Card.OFFER, a.Business(promotion=True, expiry=a.Expiry.EXPIRED),
             (p.Finding.CHECKED_CLEAR,), p.EvidenceState.CURRENT),
            (Card.LURE, a.Business(promotion=True), (p.Finding.COMPROMISED,), p.EvidenceState.CURRENT),
            (Card.PRIVATE, supported, (p.Finding.CHECKED_CLEAR,), p.EvidenceState.CURRENT),
        )
        for index, (card, business, findings, freshness) in enumerate(scenarios, 1):
            source = a.Source.B if card is Card.PRIVATE else a.Source.A
            snapshot = a.Snapshot(source=source, generation=index, business=business)
            evidence = p.Evidence(binding=self.binding(snapshot, a.Policy.V1), findings=findings,
                                  state=freshness, authentication=p.Authentication.PASS,
                                  familiar_sender=True, user_released=True)
            case = self.assess(a.Case(snapshot), evidence)
            self.states[card] = State(case, evidence)
        self.originals = self.states.copy()

    def binding(self, snapshot, policy):
        return self.p.Binding(self.p.Source[snapshot.source.name], self.p.Item[snapshot.item.name],
                              snapshot.generation, self.p.Policy[policy.name])

    def access(self, card):
        source = self.states[card].case.snapshot.source
        return self.a.Access(source=source, permission=self.grants[source])

    def visible(self, card):
        return (type(card) is Card and card in self.states
                and self.a._allowed(self.states[card].case, self.access(card)))

    def state(self, card):
        return self.states[card] if self.visible(card) else None

    def assess(self, case, evidence):
        p, a = self.p, self.a
        binding = self.binding(case.snapshot, case.policy)
        result = p.evaluate(binding, evidence, p.Access(binding.source))
        mapping = {p.Outcome.SAFE_TO_ROUTE: a.Safety.SAFE_TO_ROUTE, p.Outcome.SUSPICIOUS: a.Safety.SUSPICIOUS,
                   p.Outcome.HIGH_RISK: a.Safety.HIGH_RISK, p.Outcome.INDETERMINATE: a.Safety.UNKNOWN}
        return replace(case, assessment=a.Assessment(case.snapshot, case.policy, mapping[result.outcome]))

    def projection(self, card, offers=False):
        state = self.state(card)
        if state is None:
            return None
        return self.a.route(state.case, self.access(card),
                            self.a.Intent.OFFER_QUERY if offers else self.a.Intent.INSPECT)

    def cards(self, view):
        if type(view) is not View:
            raise DemoError()
        selected = []
        for card in Card:
            projection = self.projection(card, view is View.OFFERS)
            if projection is None:
                continue
            a = self.a
            business = projection.business
            # A safety question is not a household obligation. Promotion-only
            # uncertainty stays inspectable in Security, never Pending or Offers.
            household_question = (not business.promotion
                                  or business.importance is a.Importance.IMPORTANT
                                  or business.action is a.ActionEvidence.SUPPORTED)
            match = {
                View.TODO: projection.historical_acceptance,
                View.PENDING: household_question and projection.destination in (
                    a.Destination.PENDING, a.Destination.UNASSESSED, a.Destination.ABSTAIN),
                View.SECURITY: projection.safety is not a.Safety.SAFE_TO_ROUTE,
                View.INFORMATION: projection.destination is a.Destination.INFORMATION,
                View.OFFERS: projection.offer_visible,
            }[view]
            if match:
                selected.append(card)
        return tuple(selected)

    def history(self, card):
        return tuple(e for e in self.events if e.command.card is card) if self.visible(card) else ()

    def prepare(self, card, operation, conditions=None):
        state = self.state(card)
        if state is None or type(operation) is not Operation:
            raise DemoError()
        return Command(card, state, operation, len(self.history(card)) + 1, conditions)

    def commit(self, command, confirmation):
        if type(command) is not Command or not self.visible(command.card):
            raise DemoError()
        if type(confirmation) is not str or confirmation != command.operation.value:
            raise DemoError()
        history = self.history(command.card)
        for event in history:
            if event.command.request == command.request:
                if event.command != command:
                    raise DemoError()
                return "replayed-current" if self.state(command.card) == event.result else "replayed-historical"
        state = self.state(command.card)
        if command.expected != state or len(history) >= MAX_EVENTS or command.request != len(history) + 1:
            raise DemoError()
        a, p, op = self.a, self.p, command.operation
        result = state
        if op in (Operation.REVIEW, Operation.ACCEPT):
            if command.conditions is not None:
                raise DemoError()
            authority = a.Authority.REVIEW_CONFIRMED if op is Operation.REVIEW else a.Authority.SIMULATED_ACCEPTANCE
            result = replace(state, case=a.decide(state.case, self.access(command.card), authority,
                                                 a.Confirmation.EXPLICIT))
        elif op is Operation.DEFER:
            if command.conditions is not None:
                raise DemoError()
            result = replace(state, deferred=True)
        elif op in (Operation.CHANGE, Operation.REVERT):
            if command.conditions is not None:
                raise DemoError()
            original = self.originals[command.card]
            case = a.advance(state.case, a.Evidence.CHANGED if op is Operation.CHANGE else a.Evidence.ORIGINAL,
                             original.case.snapshot.business)
            evidence = replace(original.evidence, binding=self.binding(case.snapshot, case.policy),
                               state=p.EvidenceState.MISSING if op is Operation.CHANGE else original.evidence.state)
            result = replace(state, case=self.assess(case, evidence), evidence=evidence, deferred=False)
        else:
            conditions = command.conditions
            binding = self.binding(state.case.snapshot, state.case.policy)
            if (type(conditions) is not p.Conditions or conditions.binding != binding
                    or conditions.approval is not p.Approval.EXPLICIT_SIMULATION):
                raise DemoError()
            access = p.Access(binding.source, p.Permission[self.access(command.card).permission.name])
            assessment = p.evaluate(binding, state.evidence, access)
            if op is Operation.QUARANTINE:
                # Unknown/failed moves cannot be retried or guessed undone through this demo.
                if state.recovery is not None:
                    raise DemoError()
                recovery = p.quarantine(assessment, conditions, access)
            else:
                if state.recovery is None:
                    raise DemoError()
                recovery = p.restore(state.recovery, conditions, access)
            result = replace(state, recovery=recovery)
        result = replace(result, revision=state.revision + 1)
        self.states[command.card] = result
        self.events += (Event(command, result),)
        return "saved-simulation"

    def totals(self):
        # Revocation also removes history-derived aggregates; no global saved counter.
        events = tuple(e for e in self.events if self.visible(e.command.card))
        return {"saved_annotations": len(events), "accepted_annotations": sum(
            e.command.operation is Operation.ACCEPT for e in events), "recovery_annotations": sum(
            e.command.operation in (Operation.QUARANTINE, Operation.RESTORE) for e in events)}


class _Exit(Exception):
    pass


class _InputLimit(Exception):
    pass


def read(stream, output, prompt):
    output.write(prompt + "\n")
    output.flush()
    line = stream.readline(MAX_INPUT + 2)
    if not line:
        raise _Exit()
    if len(line.rstrip("\r\n")) > MAX_INPUT:
        raise _InputLimit()
    value = line.strip()
    if not value.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return ""
    value = value.lower()
    if value in ("q", "quit"):
        raise _Exit()
    return {"b": "back", "c": "cancel"}.get(value, value)


class Terminal:
    def __init__(self, session, stream, output):
        self.session, self.stream, self.output = session, stream, output

    def say(self, value):
        self.output.write(value + "\n")
        self.output.flush()

    def read(self, prompt):
        return read(self.stream, self.output, prompt)

    def show(self, card):
        state = self.session.state(card)
        projection = self.session.projection(card)
        if state is None:
            return False
        self.say(card.value)
        self.say(f"Episode={state.case.snapshot.generation}; revision={state.revision}; "
                 f"safety={projection.safety.name}; authority={projection.authority.name}")
        questions = {
            Card.LIBRARY: "Question: Accept the invented equipment return step? Fixed safe-to-route and step evidence supplied; no real deadline.",
            Card.SCHOOL: "Question: Is the invented urgent permission notice genuine? Independent anomaly unresolved; do not follow message instructions.",
            Card.CLINIC: "Question: Is the invented preparation notice incorrectly held? Fixed legitimate notice with a false risk finding; independent verification missing.",
            Card.BANK: "Question: Does the invented bank service notice require attention? Detector unavailable; safety and step details unknown.",
            Card.MIXED: "Question: What does the separate service notice require? Service step missing; advertisement does not supply an obligation.",
            Card.CONFLICT: "Question: Which workshop instruction applies? Conflicting step evidence; concrete acceptance unavailable.",
            Card.INFORMATION: "Quiet invented venue information; no supported action and no provider archive operation.",
            Card.OFFER: "Explicitly queried invented gardening offer; expired terms do not create urgency or a task.",
            Card.LURE: "Question: Is the invented reward promotion compromised? Authentication, familiarity and prior release do not override the risk finding.",
            Card.PRIVATE: "Question: Accept the independently scoped invented appointment step? Fixed evidence only.",
        }
        self.say(questions[card])
        self.say("Safe choices: inspect/history, verify independently outside this demo, or defer. "
                 "Supported clear steps alone permit review and separate simulated acceptance.")
        if projection.acceptance_requires_revalidation:
            self.say("Historical accepted step: EVIDENCE CHANGED — verify before proceeding; no current authority.")
        if state.deferred:
            self.say("Deferred and still discoverable; no date/deadline invented.")
        if state.recovery is not None:
            self.say(f"SIMULATION quarantine={state.recovery.quarantine.name}; "
                     f"restore={state.recovery.restoration.name if state.recovery.restoration else 'NONE'}")
        return True

    def choose(self, prompt, choices):
        value = self.read(prompt + " / ".join(choices) + " / back / cancel / quit")
        if value in ("back", "cancel"):
            return value
        if value not in choices:
            self.say("Invalid choice; unfinished intention discarded.")
            return "cancel"
        return value

    def intention(self, card, operation, displayed):
        # Capture display before asking for any simulated gates/confirmation.
        command = replace(self.session.prepare(card, operation), expected=displayed)
        answers, step = [], 0
        prompts = (("Simulated provider state: ", ("unchanged", "user_changed", "unknown")),
                   ("Simulated retention/recovery records: ", ("verified", "uncertain")),
                   ("Simulated observed outcome: ", ("verified", "failed", "unknown")))
        recovery = operation in (Operation.QUARANTINE, Operation.RESTORE)
        while True:
            if recovery and step < len(prompts):
                prompt, choices = prompts[step]
                answer = self.choose(prompt, choices)
                if answer == "cancel" or (answer == "back" and step == 0):
                    return
                if answer == "back":
                    step -= 1
                    answers = answers[:step]
                    continue
                answers = answers[:step] + [answer]
                step += 1
                continue
            self.say(f"Only this intention: {operation.name}; displayed revision={command.expected.revision}. "
                     "No unrelated authority or external operation.")
            answer = self.read(f"Type exactly {operation.value} / back / cancel / quit")
            if answer == "back":
                if recovery:
                    step = len(prompts) - 1
                    answers = answers[:step]
                    continue
                return
            if answer != operation.value:
                self.say("No annotation saved.")
                return
            if recovery:
                p = self.session.p
                conditions = p.Conditions(self.session.binding(command.expected.case.snapshot,
                                           command.expected.case.policy),
                    p.ProviderState[answers[0].upper()], p.Retention[answers[1].upper()],
                    p.Approval.EXPLICIT_SIMULATION, p.Observed[answers[2].upper()])
                command = replace(command, conditions=conditions)
            self.say(self.session.commit(command, answer))
            return

    def card(self, card):
        operations = {"review": Operation.REVIEW, "accept": Operation.ACCEPT, "defer": Operation.DEFER,
                      "quarantine": Operation.QUARANTINE, "restore": Operation.RESTORE,
                      "change": Operation.CHANGE, "revert": Operation.REVERT}
        while True:
            displayed = self.session.state(card)
            if not self.show(card):
                return
            value = self.read("Card: review / accept / defer / quarantine / restore / history / "
                              "replay / change / revert / back / cancel / quit")
            if value in ("back", "cancel"):
                return
            try:
                if value == "history":
                    for event in self.session.history(card):
                        self.say(f"History revision={event.result.revision}; "
                                 f"episode={event.command.expected.case.snapshot.generation}; "
                                 f"annotation={event.command.operation.name}; synthetic only")
                elif value == "replay":
                    history = self.session.history(card)
                    if history and self.read("Acknowledge last exact request only (no new annotation): "
                                             "confirm-replay / back / cancel / quit") == "confirm-replay":
                        command = history[-1].command
                        self.say(self.session.commit(command, command.operation.value))
                elif value in operations:
                    self.intention(card, operations[value], displayed)
                else:
                    self.say("Unavailable choice; no annotation saved.")
            except (DemoError, self.session.a.RoutingError, self.session.p.PolicyError):
                self.say("Intention rejected; refresh the card. No success claimed.")

    def listing(self, view):
        page = 0
        while True:
            cards = self.session.cards(view)
            page = min(page, max(0, (len(cards) - 1) // DISPLAY_CAP))
            visible = cards[page * DISPLAY_CAP:(page + 1) * DISPLAY_CAP]
            self.say(f"{view.value}: authorized backlog={len(cards)}; "
                     f"outside this page={len(cards) - len(visible)}; page={page + 1}. Demo cap={DISPLAY_CAP}.")
            for index, card in enumerate(visible, 1):
                self.say(f"{index}. {card.value}")
            value = self.read("View: 1 / 2 / next / previous / all (View all pending) / back / cancel / quit")
            if value in ("back", "cancel"):
                return
            if value in ("next", "all"):
                page = min(page + 1, max(0, (len(cards) - 1) // DISPLAY_CAP))
            elif value == "previous":
                page = max(0, page - 1)
            elif value in ("1", "2") and int(value) <= len(visible):
                self.card(visible[int(value) - 1])
            else:
                self.say("Unavailable choice; no annotation saved.")

    def run(self):
        views = {"todo": View.TODO, "pending": View.PENDING, "security": View.SECURITY,
                 "information": View.INFORMATION, "offers": View.OFFERS}
        while True:
            self.say("Views: My To-do / Pending Confirmation / Security Review / Information. "
                     "Offers require an explicit query.")
            value = self.read("Home: todo / pending / security / information / offers / revoke / quit")
            if value in views:
                self.listing(views[value])
            elif value == "revoke":
                if self.read("Demo revoke current source access: type confirm-revoke / back / cancel / quit") == "confirm-revoke":
                    self.session.grants[self.session.a.Source.A] = self.session.a.Permission.REVOKED
                    self.say("Demo access revoked; future projections and summaries recheck access.")
            else:
                self.say("Unavailable choice; no annotation saved.")


def main(argv=None, *, stream=None, output=None):
    args = sys.argv[1:] if argv is None else argv
    output = sys.stdout if output is None else output
    if args == ["--help"]:
        output.write("Usage: python -m family_os._synthetic_phishing_demo --synthetic-only\n" + NOTICE + "\n")
        return 0
    if args != ["--synthetic-only"]:
        output.write("Requires exactly --synthetic-only; no scenarios initialized.\n")
        return 2
    # Gate before contract imports and any scenario initialization. No file/store exists.
    session = None
    try:
        from family_os import _synthetic_routing as routing
        from family_os import _synthetic_phishing_policy as policy
        session = Session(routing, policy)
        terminal = Terminal(session, sys.stdin if stream is None else stream, output)
        terminal.say(NOTICE)
        try:
            terminal.run()
        except (_Exit, EOFError, KeyboardInterrupt):
            pass
        except _InputLimit:
            terminal.say("Input limit exceeded; unfinished intention discarded.")
        terminal.say("Session totals (currently authorized only): " + "; ".join(
            f"{key}={value}" for key, value in session.totals().items()) + ". No tasks or provider writes.")
        return 0
    except (EOFError, KeyboardInterrupt):
        output.write("Synthetic session interrupted; no unfinished intention saved.\n")
        return 130
    except Exception:
        output.write("Synthetic demo unavailable; session stopped. No success claimed.\n")
        return 1
    finally:
        if session is not None:
            session.states.clear()
            session.originals.clear()
            session.events = ()


if __name__ == "__main__":
    raise SystemExit(main())
