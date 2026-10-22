"""Developer-only paired corpus runner; fixed checked-in synthetic fixture, no DB.

No user corpus arguments or production CLI integration. Ground truth and scripted
responses are separate fixture fields; the fake is not an intelligent classifier.
"""
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path

from .analysis import AnalysisInput, AnalysisOutput, AnalysisError, canonical_json, load_classification, validate_output
from .audit import HumanLabels, EvaluationRecord, validate_labels, evaluate
from .metadata_classifier import MetadataRulesAnalyzer, load_rules
from .synthetic_reasoning import (project_metadata, ScriptedFakeTransport, ReasoningManifest,
    SyntheticReasoningAnalyzer, ReasoningRejectedError, INPUT_BYTES, RESPONSE_BYTES)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'fixtures/metadata-reasoning.synthetic.json'


def _cases(corpus, policy):
    try:
        if type(corpus) is not dict or set(corpus) != {'synthetic_only','cases'} or corpus['synthetic_only'] is not True or type(corpus['cases']) is not list or not 1 <= len(corpus['cases']) <= 1000:
            raise ValueError()
        result, ids = [], set()
        for case in corpus['cases']:
            if type(case) is not dict or set(case) != {'id','tags','input','expected','fake_response'}:
                raise ValueError()
            id = case['id']
            if type(id) is not str or not id.startswith('synthetic-') or len(id)>64 or id in ids:
                raise ValueError()
            ids.add(id)
            if type(case['tags']) is not list or not case['tags'] or any(tag not in {'recent','historical','ambiguous','missing','challenge'} for tag in case['tags']):
                raise ValueError()
            source = case['input']
            if type(source) is not dict or not {'provider','record_type','subject'} <= set(source) or not set(source) <= {'provider','record_type','subject','sender','occurred_at','raw_metadata'}:
                raise ValueError()
            expected = case['expected']
            if type(expected) is not dict or set(expected) != {'relevance','domain','action'}:
                raise ValueError()
            domain = expected['domain']
            if domain is not None and (type(domain) is not list or len(domain)!=2):
                raise ValueError()
            human = validate_labels(HumanLabels(expected['relevance'],*(domain or [None,None]),expected['action']),policy)
            occurred = datetime.fromisoformat(source['occurred_at']) if source.get('occurred_at') else None
            input = AnalysisInput(id,'raw-'+id,source['provider'],'unknown',None,source['record_type'],
                'object-'+id,occurred,source['subject'],source.get('sender'),(),source.get('raw_metadata',{}))
            # Fake response may be deliberately wrong: never synthesize it from truth.
            response = canonical_json(case['fake_response'])
            result.append((input,human,tuple(case['tags']),response))
        return result
    except Exception:
        raise ReasoningRejectedError() from None


def compare_synthetic(corpus, policy, rules):
    cases = _cases(corpus,policy)
    entries, sizes, rejected = [], [], 0
    for input, _, _, response in cases:
        try:
            projection = project_metadata(input)
            entries.append((projection.fingerprint,'response',response))
            sizes.append(projection.byte_count)
        except AnalysisError:
            rejected += 1
    # Equivalent projections must have the same fake response; otherwise fail closed.
    entries = tuple(sorted(set(entries)))
    transport = ScriptedFakeTransport(entries)
    manifest = ReasoningManifest(transport.artifact_digest,rules.ruleset.fingerprint)
    candidate = SyntheticReasoningAnalyzer(transport,manifest)
    models = {'rules':rules,'fake_reasoning':candidate}
    references = [dict(source_record_id=input.source_record_id,raw_record_id=input.raw_record_id,
                       input_fingerprint=input.fingerprint,tags=tags) for input,_,tags,_ in cases]
    results = {}
    for name, analyzer in models.items():
        records, misses, failed = [], 0, 0
        for input, human, _, _ in cases:
            try:
                output = analyzer.analyze(input,policy)
                values, _ = validate_output(output,input,policy)
            except AnalysisError:
                failed += 1
                output = AnalysisOutput('uncertain',0.0,None,None,0.0,'uncertain',0.0)
                values, _ = validate_output(output,input,policy)
            misses += int(human.action_label == 'required' and output.action_label != 'required')
            records.append(EvaluationRecord(input.provider,output.relevance_label,output.relevance_confidence,
                output.category,output.subcategory,output.domain_confidence,output.action_label,output.action_confidence,
                values['review_recommended'],human))
        results[name] = dict(definition=dict(analyzer_name=analyzer.name,analyzer_version=analyzer.version,
            taxonomy_version=policy.taxonomy_version,threshold_policy_version=policy.threshold_policy_version,
            definition_fingerprint=policy.fingerprint(analyzer.name,analyzer.version)),
            failed_count=failed,action_required_miss_count=misses,
            action_required_truth_count=sum(h.action_label=='required' for _,h,_,_ in cases),
            **evaluate(records,policy.categories))
    return dict(notice='SYNTHETIC - NOT REAL WORLD QUALITY',case_count=len(cases),
        synthetic_snapshots=references,manifest=asdict(manifest),manifest_fingerprint=manifest.fingerprint,
        projection_budget=dict(max_bytes=INPUT_BYTES,response_max_bytes=RESPONSE_BYTES,
            rejected_count=rejected,total_bytes=sum(sizes),max_observed_bytes=max(sizes,default=0),
            device_egress_bytes=0),results=results,
        persistence_exercised=False,human_revisions_modified=False)


def main():
    policy = load_classification(ROOT / 'config/classification.yaml')
    rules = MetadataRulesAnalyzer(load_rules(ROOT / 'config/metadata-classifier.yaml',policy))
    try:
        corpus = json.loads(FIXTURE.read_text(encoding='utf-8'))
        print(canonical_json(compare_synthetic(corpus,policy,rules)))
    except Exception:
        raise ReasoningRejectedError() from None


if __name__ == '__main__':
    main()
