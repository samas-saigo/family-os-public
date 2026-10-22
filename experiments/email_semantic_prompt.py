"""One preregistered prompt; reuse pinned lifecycle code in an isolated namespace."""
from types import FunctionType

from experiments import email_relational_schema as baseline
from experiments.email_relational_schema import (
    argparse, Counter, sha256, json, os, Path, re, sys, time, uuid4,
    compat, parent, wording, engine, diagnostic, need, Error, read_bounded,
    select, encoded, version,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path('experiments/configs/synthetic-email-semantic-prompt-v1.json')
CONFIG_SHA = 'e95e846ae78f186f8a7f6f624f5a6fe48a2321f501461bbb3b4c5209344a2006'
FREEZE = 'f9530a091e9011556d8332aa03422460e1b315a6'
EXPERIMENT = 'synthetic-email-semantic-prompt-v1'
LOCAL = Path('.local/email-semantic-prompt-v1')
REPORT_BYTES = baseline.REPORT_BYTES
SOURCE_PINS = {
    **baseline.SOURCE_PINS,
    'experiments/email_relational_schema.py': '6598a3c384ed0a1e4d7dbf0466ba87606afb9ee01af6813ba5cf3e32c0479e84',
    'experiments/configs/synthetic-email-relational-schema-v1.json': baseline.CONFIG_SHA,
}


def context_bound(config, projection):
    """Offline content-byte bound under the documented framing/token assumptions."""
    policy = config['context_check']
    return (len(config['prompt'].encode('utf-8'))
            + len(wording.canonical(dict(projection.fields)).encode('utf-8'))
            + policy['framing_reserve'] + policy['output_reserve'])


def setup():
    need(ROOT == baseline.ROOT and Path(baseline.__file__).absolute() == ROOT / 'experiments/email_relational_schema.py', 'input_rejected')
    for path, expected in {CONFIG.as_posix(): CONFIG_SHA, **SOURCE_PINS}.items():
        raw = read_bounded(ROOT / path, 65536).replace(b'\r\n', b'\n')
        need(sha256(raw).hexdigest() == expected, 'input_rejected')
    config = parent.strict_json(read_bounded(ROOT / CONFIG, 65536).decode('utf-8'))
    previous, original, cases = baseline.setup()  # No frozen run or report read.
    need(config['source_pins'] == SOURCE_PINS, 'input_rejected')
    metadata = {'prompt', 'experiment', 'baseline', 'source_pins', 'report'}
    need(all(config[k] == previous[k] for k in previous.keys() - metadata), 'input_rejected')
    need(type(config['prompt']) is str and config['prompt'] and config['prompt'] != previous['prompt'], 'input_rejected')
    policy = config['context_check']
    need(policy['num_ctx'] == config['generation']['options']['num_ctx'] == 4096
         and policy['output_reserve'] == config['generation']['options']['num_predict'] == 512, 'input_rejected')
    need(all(context_bound(config, engine.EmailMetadata(c['input'])) <= policy['num_ctx'] for c in cases), 'resource_limit')
    wire = dict(original, prompt=config['prompt'])
    need(wire != original and dict(wire, prompt=original['prompt']) == original, 'input_rejected')
    return config, wire, cases


def _reuse(function):
    # Same audited bytecode, new function/global dict. No patch to a frozen module,
    # code object, shared function, validator, transport method or scorer.
    need(function.__closure__ is None, 'input_rejected')
    return FunctionType(function.__code__, globals(), function.__name__, function.__defaults__)


class Transport(baseline.Transport):
    # Only resolve setup in this adapter. All request/payload/identity methods and
    # the constructor's single-chat counters/allowlist/deadline code stay identical.
    __init__ = _reuse(baseline.Transport.__init__)


_frozen_run = _reuse(baseline.run)


def run(mode):
    report = _frozen_run(mode)
    report['notice'] = ('NEW SINGLE PROMPT DEVELOPMENT CANDIDATE ON SEEN CORRELATED SYNTHETIC36; '
                        'STRUCTURE VALIDITY IS NOT SEMANTIC IMPROVEMENT; '
                        'NOT BLIND/REAL-WORLD ACCURACY; NO POOLING OR ACTIONS')
    return report


save = _reuse(baseline.save)
read_report = _reuse(baseline.read_report)
collect = _reuse(baseline.collect)
# PR110's generic CLI has the same approved options/control flow as PR113, with
# a general comparison description rather than PR113's schema-specific help text.
main = _reuse(baseline.prior.main)


if __name__ == '__main__':
    raise SystemExit(main())
