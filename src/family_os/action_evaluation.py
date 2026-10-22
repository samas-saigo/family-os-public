"""Fixed synthetic Action dataset validation and offline rules; no model or DB wiring.

Annotations are evaluation-side only. model_projection returns the exact approved
metadata contract, never expected labels, rationale, evidence, split or IDs.
"""
import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

from .analysis import AnalysisInput, AnalysisError, canonical_json, freeze_json, load_classification, validate_output
from .audit import HumanLabels, EvaluationRecord, evaluate, ratio, validate_labels
from .metadata_classifier import MetadataRulesAnalyzer, load_rules
from .synthetic_reasoning import MetadataProjection, project_metadata, ENGINE_VERSION as PROJECTION_ENGINE

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / 'fixtures/action-evaluation-v1'
VERSION = 'action-evaluation-v1'
ENGINE_VERSION = 'action-evaluation-e1'
FILE_BYTES = 262144
# Updated only with a reviewed version/changelog; pins rubric and both annotated splits.
FROZEN_MANIFEST_SHA256 = 'f676baa523a8c7a9b187e8139be8e556244a09009ef674b7830a3729b831634f'
PROVIDERS = {'gmail': 'message', 'outlook': 'message', 'google_calendar': 'calendar_event', 'google_drive': 'document'}
ACTIONS = ('required', 'not_required', 'uncertain')
SCENARIOS = {'payment','renewal','reservation','cancellation','appointment','marketing','historical','security','government','purchase','document','maintenance'}
CASE_KEYS = {'id','scenario','temporal','truth_certainty','counterfactual_group','cue_field','input','expected','rationale','evidence_refs','ambiguity_notes'}
RUBRIC_KEYS = {'synthetic_only','rubric_version','reference_time','action_definitions','relevance_definition','domain_definition','calendar_caveat','drive_caveat','historical_caveat','annotation_policy','split_protocol','freeze_policy','limitations'}


class DatasetRejectedError(AnalysisError):
    def __init__(self):
        super().__init__('Synthetic Action dataset rejected; check frozen schema, rubric and manifest')


def digest(value):
    return sha256(canonical_json(value).encode('utf-8')).hexdigest()


def strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    try:
        if type(text) is not str or len(text.encode('utf-8')) > FILE_BYTES:
            raise ValueError()
        return json.loads(text, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Exception:
        raise DatasetRejectedError() from None


def _read(path):
    try:
        with path.open('rb') as file:
            data = file.read(FILE_BYTES + 1)
        if len(data) > FILE_BYTES:
            raise ValueError()
        return strict_json(data.decode('utf-8'))
    except Exception:
        raise DatasetRejectedError() from None


def _text(value, limit):
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise ValueError()
    canonical_json(value)


def _timestamp(value):
    if type(value) is not str or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',value):
        raise ValueError()
    result = datetime.fromisoformat(value.replace('Z','+00:00'))
    if not datetime(2015,1,1,tzinfo=timezone.utc) <= result <= datetime(2035,1,1,tzinfo=timezone.utc):
        raise ValueError()
    return result


def _resolve(source, path):
    if type(path) is not str or len(path)>80 or not re.fullmatch(r'(?:subject|sender|occurred_at|provider|record_type|raw_metadata\.(?:status|eventType|mimeType|trashed|removed|(?:start|end)\.(?:date|dateTime)))',path):
        raise ValueError()
    value=source
    for part in path.split('.'):
        if not isinstance(value,dict) or part not in value:
            raise ValueError()
        value=value[part]
    if value is None or isinstance(value,(dict,list)):
        raise ValueError()
    return value


@dataclass(frozen=True)
class SyntheticCase:
    id: str
    split: str
    input: AnalysisInput = field(repr=False)
    expected: HumanLabels = field(repr=False)
    annotations: object = field(repr=False)


def model_projection(case):
    """Only this projection is eligible for a separately reviewed future adapter."""
    if type(case) is not SyntheticCase:
        raise DatasetRejectedError()
    return project_metadata(case.input)


def _words(text):
    return frozenset(re.findall(r'\w+',unicodedata.normalize('NFKC',text).casefold()))


def _near(a,b):
    left,right=_words(a),_words(b)
    return left==right or min(len(left),len(right))>=4 and len(left & right)/len(left | right)>=0.8


def validate_cases(development, holdout, policy, legacy):
    """Strict all-or-nothing semantic/schema validation; no skipping bad cases."""
    try:
        parsed, ids, projections, groups, subjects = [], set(), set(), {}, []
        old_subjects=[c['input']['subject'] for c in legacy['cases'] if isinstance(c.get('input'),dict)
                      and type(c['input'].get('subject')) is str]
        for split, corpus, count in (('development',development,60),('holdout',holdout,30)):
            if type(corpus) is not dict or set(corpus)!={'synthetic_only','dataset_version','split','cases'} or corpus['synthetic_only'] is not True or corpus['dataset_version']!=VERSION or corpus['split']!=split or type(corpus['cases']) is not list or len(corpus['cases'])!=count:
                raise ValueError()
            labels=Counter()
            for case in corpus['cases']:
                if type(case) is not dict or set(case)!=CASE_KEYS:
                    raise ValueError()
                id=case['id']
                if type(id) is not str or not re.fullmatch(r'synthetic-action-[a-z0-9-]{1,40}',id) or id in ids:
                    raise ValueError()
                ids.add(id)
                if case['scenario'] not in SCENARIOS or case['temporal'] not in {'current','historical','unknown'} or case['truth_certainty'] not in {'explicit','ambiguous'}:
                    raise ValueError()
                source=case['input']
                if type(source) is not dict or not {'provider','record_type','subject','occurred_at','raw_metadata'} <= set(source) or not set(source)<= {'provider','record_type','subject','sender','occurred_at','raw_metadata'}:
                    raise ValueError()
                if source['provider'] not in PROVIDERS or source['record_type']!=PROVIDERS[source['provider']]:
                    raise ValueError()
                _text(source['subject'],600)
                if 'sender' in source and (type(source['sender']) is not str or not re.fullmatch(r'[a-z0-9-]{1,40}@example\.invalid',source['sender']) or source['provider'] not in {'gmail','outlook'}):
                    raise ValueError()
                occurred=_timestamp(source['occurred_at'])
                if case['temporal']=='historical' and occurred.year>=2026 or case['temporal']=='current' and occurred.year!=2026:
                    raise ValueError()
                # Reject extra/nested fields instead of relying on the projector to omit them.
                MetadataProjection(dict(source,occurred_at=occurred.isoformat(timespec='microseconds').replace('+00:00','Z')))
                metadata=source['raw_metadata']
                allowed=({'status','eventType','start','end'} if source['provider']=='google_calendar' else
                         {'mimeType','trashed','removed'} if source['provider']=='google_drive' else set())
                if not set(metadata)<=allowed or ('status' in metadata and metadata['status'] not in {'confirmed','cancelled','tentative'}):
                    raise ValueError()
                for parent in ('start','end'):
                    for key,value in metadata.get(parent,{}).items():
                        if key=='date':
                            if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',value): raise ValueError()
                            _timestamp(value+'T00:00:00Z')
                        else:
                            _timestamp(value)
                expected=case['expected']
                if type(expected) is not dict or set(expected)!={'relevance','domain','action'}:
                    raise ValueError()
                domain=expected['domain']
                if domain is not None and (type(domain) is not list or len(domain)!=2):
                    raise ValueError()
                human=validate_labels(HumanLabels(expected['relevance'],*(domain if domain is not None else (None,None)),expected['action']),policy)
                if (case['truth_certainty']=='ambiguous') != (human.action_label=='uncertain') or case['temporal']=='historical' and human.action_label=='required':
                    raise ValueError()
                labels[human.action_label]+=1
                _text(case['rationale'],512); _text(case['ambiguity_notes'],512)
                refs=case['evidence_refs']
                if type(refs) is not list or not 1<=len(refs)<=8 or any(type(ref) is not str for ref in refs) or len(set(refs))!=len(refs):
                    raise ValueError()
                for ref in refs:
                    _resolve(source,ref)
                group, cue=case['counterfactual_group'],case['cue_field']
                if group is None:
                    if cue is not None:
                        raise ValueError()
                else:
                    if type(group) is not str or not re.fullmatch(r'[a-z][a-z0-9-]{0,31}',group) or cue not in {'subject','raw_metadata.status'}:
                        raise ValueError()
                    _resolve(source,cue)
                    groups.setdefault(group,[]).append((split,case))
                if any(_near(source['subject'],s) for s in old_subjects):
                    raise ValueError()
                if any(_near(source['subject'],s) and (group is None or group!=g) for s,g in subjects):
                    raise ValueError()
                subjects.append((source['subject'],group))
                input=AnalysisInput(id,'raw-'+id,source['provider'],'unknown',None,source['record_type'],'object-'+id,
                    occurred,source['subject'],source.get('sender'),(),source['raw_metadata'])
                projection=project_metadata(input)
                if projection.fingerprint in projections or projection.byte_count>1024:
                    raise ValueError()
                projections.add(projection.fingerprint)
                parsed.append(SyntheticCase(id,split,input,human,freeze_json({k:case[k] for k in ('scenario','temporal','truth_certainty','counterfactual_group','cue_field','rationale','evidence_refs','ambiguity_notes')})))
            if labels!=Counter({a:count//3 for a in ACTIONS}):
                raise ValueError()
        # Each triad differs at exactly its one declared visible field, never its split.
        for members in groups.values():
            if len(members)!=3 or len({s for s,_ in members})!=1 or {c['expected']['action'] for _,c in members}!=set(ACTIONS) or len({c['cue_field'] for _,c in members})!=1:
                raise ValueError()
            if len({canonical_json({k:c['expected'][k] for k in ('relevance','domain')}) for _,c in members})!=1:
                raise ValueError()
            masked=[]
            for _,c in members:
                value=json.loads(canonical_json(c['input']))
                parts=c['cue_field'].split('.')
                target=value
                for part in parts[:-1]: target=target[part]
                target[parts[-1]]='<controlled-cue>'
                masked.append(value)
            if any(value!=masked[0] for value in masked[1:]):
                raise ValueError()
        if len(groups)!=24 or {c.input.provider for c in parsed}!=set(PROVIDERS) or {c.expected.domain_category for c in parsed if c.expected.domain_category is not None}!=set(policy.categories):
            raise ValueError()
        return tuple(sorted(parsed,key=lambda c:c.id))
    except Exception:
        raise DatasetRejectedError() from None


def manifest_for(development, holdout, rubric, policy):
    """Canonical content identity includes annotations; projection identity excludes them."""
    splits={}
    for split,corpus in (('development',development),('holdout',holdout)):
        ordered=dict(corpus,cases=sorted(corpus['cases'],key=lambda c:c['id']))
        splits[split]={'case_count':len(ordered['cases']),'annotated_sha256':digest(ordered),
            'input_sha256':digest([c['input'] for c in ordered['cases']])}
    return dict(synthetic_only=True,dataset_version=VERSION,rubric_version=rubric['rubric_version'],
        projection_schema='metadata_only_v1',projection_engine=PROJECTION_ENGINE,
        rubric_sha256=digest(rubric),splits=splits,
        corpus_sha256=digest({'splits':splits,'rubric_sha256':digest(rubric)}),
        taxonomy_sha256=digest({'version':policy.taxonomy_version,'categories':policy.categories}))


def validate_dataset(development,holdout,rubric,manifest,policy,legacy):
    try:
        if type(rubric) is not dict or set(rubric)!=RUBRIC_KEYS or rubric['synthetic_only'] is not True or rubric['rubric_version']!='action-rubric-v1' or rubric['reference_time']!='2026-10-09T12:00:00Z':
            raise ValueError()
        if type(rubric['action_definitions']) is not dict or set(rubric['action_definitions'])!=set(ACTIONS):
            raise ValueError()
        for v in rubric['action_definitions'].values(): _text(v,1024)
        for k in RUBRIC_KEYS-{'synthetic_only','action_definitions'}: _text(rubric[k],1024)
        cases=validate_cases(development,holdout,policy,legacy)
        if manifest!=manifest_for(development,holdout,rubric,policy) or digest(manifest)!=FROZEN_MANIFEST_SHA256:
            raise ValueError()
        return cases
    except Exception:
        raise DatasetRejectedError() from None


def load_dataset():
    policy=load_classification(ROOT/'config/classification.yaml')
    development,holdout,rubric,manifest=(_read(DIRECTORY/name) for name in ('development.json','holdout.json','rubric.json','manifest.json'))
    cases=validate_dataset(development,holdout,rubric,manifest,policy,_read(ROOT/'fixtures/metadata-reasoning.synthetic.json'))
    return cases,policy,manifest


def distribution(cases):
    dimensions={'action':lambda c:c.expected.action_label,'relevance':lambda c:c.expected.relevance_label,
        'provider':lambda c:c.input.provider,'record_type':lambda c:c.input.record_type,
        'scenario':lambda c:c.annotations['scenario'],'temporal':lambda c:c.annotations['temporal'],
        'truth_certainty':lambda c:c.annotations['truth_certainty'],
        'visible_status':lambda c:c.input.raw_metadata.get('status','absent'),
        'domain':lambda c:c.expected.domain_category or 'unknown'}
    return dict(case_count=len(cases),**{k:dict(sorted(Counter(f(c) for c in cases).items())) for k,f in dimensions.items()},
        relevance_by_action={action:dict(sorted(Counter(c.expected.relevance_label for c in cases if c.expected.action_label==action).items())) for action in ACTIONS},
        counterfactual_family_count=len({c.annotations['counterfactual_group'] for c in cases if c.annotations['counterfactual_group']}))


def evaluate_rules(cases,policy,rules):
    records,cohorts=[],{}
    domain_truth_count=domain_observed_count=required_false_irrelevant=0
    for action in ACTIONS:
        subset=[c for c in cases if c.expected.action_label==action]
        predictions=[]
        for c in subset:
            output=rules.analyze(c.input,policy)
            values,_=validate_output(output,c.input,policy)
            predictions.append(output.action_label)
            domain_truth_count+=int(c.expected.domain_category is not None)
            domain_observed_count+=int(c.expected.domain_category is not None and output.category is not None)
            required_false_irrelevant+=int(action=='required' and output.relevance_label=='irrelevant')
            records.append(EvaluationRecord(c.input.provider,output.relevance_label,output.relevance_confidence,
                output.category,output.subcategory,output.domain_confidence,output.action_label,output.action_confidence,
                values['review_recommended'],c.expected))
        cohorts[action]=dict(count=len(subset),predictions={a:predictions.count(a) for a in ACTIONS})
    required=cohorts['required']; not_required=cohorts['not_required']
    return dict(action_cohorts=cohorts,required_recall=ratio(required['predictions']['required'],required['count']),
        required_miss_count=required['count']-required['predictions']['required'],
        not_required_false_positive_count=not_required['predictions']['required'],
        uncertain_concrete_count=sum(cohorts['uncertain']['predictions'][a] for a in ('required','not_required')),
        domain_truth_count=domain_truth_count,decisive_domain_classified_count=domain_observed_count,
        decisive_domain_coverage=ratio(domain_observed_count,domain_truth_count),
        required_false_irrelevant_count=required_false_irrelevant,
        **evaluate(records,policy.categories))


def report(*,final_holdout=False):
    if type(final_holdout) is not bool: raise DatasetRejectedError()
    cases,policy,manifest=load_dataset()
    selected='holdout' if final_holdout else 'development'
    rules=MetadataRulesAnalyzer(load_rules(ROOT/'config/metadata-classifier.yaml',policy))
    return dict(notice='SYNTHETIC ONLY - PROCEDURAL HOLDOUT, NOT PRODUCTION ACCURACY',engine_version=ENGINE_VERSION,
        manifest=manifest,manifest_sha256=digest(manifest),
        distributions={s:distribution([c for c in cases if c.split==s]) for s in ('development','holdout')},
        evaluated_split=selected,definition=dict(analyzer_name=rules.name,analyzer_version=rules.version,
            taxonomy_version=policy.taxonomy_version,threshold_policy_version=policy.threshold_policy_version,
            definition_fingerprint=policy.fingerprint(rules.name,rules.version)),
        projection_max_bytes=max(model_projection(c).byte_count for c in cases),
        rules=evaluate_rules([c for c in cases if c.split==selected],policy,rules),device_egress_bytes=0,
        persistence_exercised=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Fixed synthetic Action corpus: validation, distributions and offline rules only')
    parser.add_argument('--final-holdout',action='store_true',help='explicit final-only frozen holdout rules evaluation; never use for tuning')
    args=parser.parse_args(argv)
    try:
        print(canonical_json(report(final_holdout=args.final_holdout)))
        return 0
    except Exception:
        print('Synthetic Action evaluation failed; no partial report or source content printed')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
