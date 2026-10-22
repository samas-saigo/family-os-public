"""Issue #63: opt-in disposable synthetic terminal adapter, never a production UI."""
from dataclasses import replace
import sys
from uuid import uuid4

MAX_INPUT = 64
NOTICE = ('SYNTHETIC ONLY — single operator; no authentication or household sharing.\n'
          'Suggestions are not proven obligations. Reviews create no tasks or actions.\n'
          'No providers, AI or real data. History lasts only until this session exits.')


class _ExitSession(Exception):
    pass


class _BadInput(Exception):
    pass


def _read(stream, output, prompt):
    output.write(prompt + '\n')
    output.flush()
    line = stream.readline(MAX_INPUT + 2)
    if not line:
        raise _ExitSession()
    # End the session rather than interpreting a truncated tail as another command.
    if len(line.rstrip('\r\n')) > MAX_INPUT:
        raise _BadInput()
    value = line.strip()
    if not value.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return ''
    value = value.lower()
    if value in ('q', 'quit'):
        raise _ExitSession()
    return {'b': 'back', 'c': 'cancel'}.get(value, value)


def _examples(core_module):
    # Newly authored enum-only cards. No fixture, source or model inputs.
    O = core_module.Observation
    A, B = core_module.ACCOUNTS
    E1, E2, E3, E4 = core_module.EVENTS
    return (
        O(A, E1, 'refund', 1),
        O(A, E2, 'attendance', 1, specimen='completed'),
        O(A, E3, 'preparation', 1, specimen='ambiguous', condition='unknown'),
        O(A, E4, 'refund', 1, specimen='invalid'),
        O(B, E2, 'preparation', 1, specimen='conflicting'),
        O(B, E3, 'attendance', 1, specimen='unsupported'),
        O(B, E1, 'refund', 1),
        O(A, E1, 'rebooking', 1),
    )


class _Demo:
    """Presentation only; the supplied private core owns all persisted review rules."""
    def __init__(self, core, core_module, stream, output):
        self.core, self.types = core, core_module
        self.stream, self.output = stream, output
        self.originals = _examples(core_module)
        self.observations = {}
        self.encounters = self.saved = self.replayed = self.cancelled = self.rejected = 0

    def say(self, text):
        self.output.write(text + '\n')
        self.output.flush()

    def read(self, prompt):
        return _read(self.stream, self.output, prompt)

    def receipt(self, obs):
        return self.core.state(obs.account, obs.event_id, obs.step)

    def load(self):
        if self.observations:
            self.say('Examples already loaded; browsing does not create encounters.')
            return
        for index, obs in enumerate(self.originals, 1):
            self.core.encounter(obs)
            self.observations[index] = obs
            self.encounters += 1
        self.say('Explicit load created eight synthetic encounters; no decisions saved.')

    def listing(self):
        self.say('All — every loaded synthetic item stays visible (no status filtering).')
        if not self.observations:
            self.say('Empty. Use load to explicitly create the fixed examples.')
        for index, obs in self.observations.items():
            receipt = self.receipt(obs)
            if receipt is None or receipt.fingerprint != obs.fingerprint:
                self.say(f'{index}. {obs.account} / {obs.event_id} / {obs.step}: '
                         'Evidence changed; refresh and review again')
                continue
            self.say(f'{index}. {obs.account} / {obs.event_id} / {obs.step}: '
                     f'proposal={obs.proposal["action"]}; decision={receipt.disposition}; '
                     f'{receipt.kind}; visible={receipt.visible}; needs_review={receipt.needs_review}')

    def show(self, obs, receipt):
        proposal = obs.proposal
        self.say(f'Synthetic card: {obs.account} / {obs.event_id} / named step={obs.step}')
        self.say(f'Snapshot={obs.snapshot}; versions={", ".join(obs.stamp)}; '
                 f'status={obs.status}; condition={obs.condition}; scope={obs.scope}')
        self.say(f'Suggestion only: {proposal["action"]}; reason={proposal["reason"]}; '
                 f'evidence refs={", ".join(proposal["refs"])}')
        self.say(f'Human decision={receipt.disposition}; annotation={receipt.kind}; '
                 f'visible={receipt.visible}; needs_review={receipt.needs_review}; '
                 f'epoch={receipt.epoch}; revision={receipt.revision}; authority=none')
        self.say('Review history is separate. Future task execution is not implemented.')

    def history(self, obs):
        decisions = self.core.history(obs.account, obs.event_id, obs.step)
        self.say('Read-only append-only decision history:')
        if not decisions:
            self.say('No saved decisions.')
        for decision in decisions:
            old = decision.observation
            self.say(f'revision={decision.revision}; epoch={decision.epoch}; '
                     f'{old.account} / {old.event_id} / {old.step}; snapshot={old.snapshot}; '
                     f'status={old.status}; condition={old.condition}; '
                     f'versions={", ".join(old.stamp)}; scope={old.scope}; '
                     f'proposal={old.proposal["action"]}; decision={decision.disposition}; authority=none')

    def update(self, index):
        choice = self.read('Explicit new encounter: repeat / change / revert / back / cancel / quit')
        if choice in ('back', 'cancel'):
            return
        obs = self.observations[index]
        if choice == 'repeat':
            new = obs
        elif choice == 'change':
            new = replace(obs, snapshot=obs.snapshot + 1, status='tentative', condition='unknown')
        elif choice == 'revert':
            new = replace(self.originals[index - 1], snapshot=obs.snapshot + 1)
        else:
            self.say('Invalid update; no encounter created.')
            return
        self.core.encounter(new)
        self.observations[index] = new
        self.encounters += 1
        self.say('Explicit encounter committed. Refresh shows its current receipt; history remains.')

    def commit(self, command):
        # An intent keeps one request ID; identical delivery reuses core idempotency.
        result = self.core.save(command)
        if result.replayed:
            self.replayed += 1
            self.say('Previously saved request acknowledged; no new revision.')
        else:
            self.saved += 1
            self.say(f'Review saved: revision={result.decision.revision}; authority=none.')
        if not result.applies_to_current:
            self.say('Historical decision only; it does not resolve current evidence.')

    def review(self, obs, receipt):
        proposal = obs.proposal
        allowed = self.types.DISPOSITIONS if (proposal['action'] in ('required', 'not_required')
                    and proposal['reason'] == 'supported') else self.types.DISPOSITIONS[2:]
        self.say('Confirm agrees with this suggestion; reject disagrees. Neither completes a task.\n'
                 'Needs information and defer leave the named step unresolved.')
        while True:
            choice = self.read('Choose human intention (no default): ' + ' / '.join(allowed)
                               + ' / back / cancel / quit')
            if choice in ('back', 'cancel'):
                self.cancelled += 1
                return
            if choice not in allowed:
                self.say('Invalid or unresolved choice; nothing saved.')
                return
            command = dict(account=receipt.account, event_id=receipt.event_id, step=receipt.step,
                receipt_token=receipt.token, expected_revision=receipt.revision, epoch=receipt.epoch,
                fingerprint=receipt.fingerprint, proposal_fingerprint=receipt.proposal_fingerprint,
                disposition=choice, confirmation='save', request_id='synthetic-request-' + uuid4().hex)
            self.say(f'Save review confirmation: {choice}, scoped to {obs.step}, '
                     f'snapshot={obs.snapshot}, epoch={receipt.epoch}, revision={receipt.revision}.')
            confirm = self.read('Type save explicitly / back to intention / cancel / quit')
            if confirm == 'back':
                continue
            if confirm == 'cancel':
                self.cancelled += 1
                return
            if confirm != 'save':
                self.say('Invalid confirmation; nothing saved.')
                return
            self.commit(command)
            return

    def card(self, index):
        while True:
            obs = self.observations[index]
            receipt = self.receipt(obs)
            fresh = receipt is not None and receipt.fingerprint == obs.fingerprint
            if fresh:
                self.show(obs, receipt)
            else:
                self.say('Evidence changed; refresh and review again. Saving is unavailable.')
            choice = self.read('Card: review / history / refresh / update / back / cancel / quit')
            try:
                if choice in ('back', 'cancel'):
                    return
                if choice == 'history':
                    self.history(obs)
                elif choice == 'refresh':
                    continue  # Read only: state() never rotates the receipt token.
                elif choice == 'update':
                    self.update(index)
                elif choice == 'review' and fresh:
                    self.review(obs, receipt)
                else:
                    self.say('Invalid or unavailable choice; nothing saved.')
            except self.types.SyntheticStoreError:
                raise
            except self.types.StaleReviewError:
                self.rejected += 1
                self.say('Evidence changed; refresh and review again. Nothing saved by this intention.')
            except self.types.IdempotencyConflictError:
                self.rejected += 1
                self.say('Request conflict; nothing saved. Display again before a new intention.')
            except self.types.ReviewCoreError:
                self.rejected += 1
                self.say('Review/update rejected; unresolved proposal or session capacity reached. Nothing saved.')

    def run(self):
        while True:
            self.listing()
            choice = self.read('All: load / 1–8 to view / quit')
            if choice == 'load':
                self.load()
            elif choice in tuple(str(i) for i in self.observations):
                self.card(int(choice))
            else:
                self.say('Invalid choice; no data or decisions written.')

    def summary(self):
        self.say(f'Session totals: encounters={self.encounters}; saved={self.saved}; '
                 f'replayed={self.replayed}; cancelled={self.cancelled}; rejected={self.rejected}. '
                 'No tasks or actions. Disposable session ended.')


def main(argv=None, *, stream=None, output=None):
    args = sys.argv[1:] if argv is None else argv
    output = sys.stdout if output is None else output
    if args == ['--help']:
        output.write('Usage: python -m family_os._synthetic_review_demo --synthetic-only\n' + NOTICE + '\n')
        return 0
    if args != ['--synthetic-only']:
        output.write('Requires exactly --synthetic-only; no database initialized.\n')
        return 2
    # Gate before core import, initialization or any store/data access.
    demo = None
    try:
        from family_os import _synthetic_review_core as core_module
        output.write(NOTICE + '\n')
        with core_module.disposable_store(synthetic_only=True) as store:
            demo = _Demo(core_module.ReviewCore(store, synthetic_only=True), core_module,
                         sys.stdin if stream is None else stream, output)
            try:
                demo.run()
            except (_ExitSession, EOFError, KeyboardInterrupt):
                pass
            except _BadInput:
                demo.say('Input limit exceeded; session stopped without saving the unfinished intention.')
        demo.summary()
        return 0
    except (EOFError, KeyboardInterrupt):
        output.write('Synthetic session interrupted; no unfinished intention saved.\n')
        return 130
    except Exception:
        # No raw exception, traceback, request token, URL or environment in output.
        output.write('Synthetic demo unavailable; session stopped. No success claimed.\n')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
