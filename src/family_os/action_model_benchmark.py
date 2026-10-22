"""Manual, fixed development-only Action benchmark. No production/model auto-wiring.

The transport receives only Phase 2Q model_projection, never SyntheticCase. Shared
Phase 2P helpers own HTTP/protocol/prompt semantics; annotations stay evaluation-side.
"""
import argparse
from collections import Counter
from itertools import combinations
import time

from . import action_evaluation as dataset
from . import ollama_synthetic_benchmark as local
from .analysis import canonical_json, validate_output
from .audit import EvaluationRecord, evaluate, ratio
from .metadata_classifier import MetadataRulesAnalyzer, load_rules

ENGINE_VERSION = 'action-development-e1'
SMOKE_IDS = ('synthetic-action-water-1','synthetic-action-club-2',
             'synthetic-action-vaccine-1','synthetic-action-vaccine-3','synthetic-action-overview')
DEVELOPMENT_PROJECTION_SHA256 = 'b3fac7d7c286a0a2c1f7ba013825a3bbc19e1cbf2dd0faefd0a8500f3cabe6f0'
ACTIONS = dataset.ACTIONS
STATUSES = ('valid','model_invalid','projection_failed','infrastructure_failed','not_attempted')


def projection(case):
    if type(case) is not dataset.SyntheticCase or case.split!='development':
        raise local.BenchmarkError()
    return dataset.model_projection(case)


def select_development(cases, *, full):
    """Holdout discarded before projection/payload construction; fixed dev pin too."""
    if type(full) is not bool or type(cases) is not tuple or any(type(c) is not dataset.SyntheticCase for c in cases):
        raise local.BenchmarkError()
    development=tuple(sorted((c for c in cases if c.split=='development'),key=lambda c:c.id))
    if len(development)!=60 or len({c.id for c in development})!=60:
        raise local.BenchmarkError()
    if local.digest([projection(c).fields for c in development])!=DEVELOPMENT_PROJECTION_SHA256:
        raise local.BenchmarkError()
    if full:
        return development
    by_id={c.id:c for c in development}
    try:
        return tuple(by_id[id] for id in SMOKE_IDS)
    except Exception:
        raise local.BenchmarkError() from None


def triad_metrics(cases, outputs):
    groups={}
    for c,out in zip(cases,outputs):
        group=c.annotations['counterfactual_group']
        if group:
            groups.setdefault(group,[]).append((c,out))
    def summary(groups):
        selected_triads=scored_triads=correct_triads=distinct_triads=0
        selected_pairs=scored_pairs=changed_pairs=correct_pairs=0
        for members in groups:
            if len(members)==3:
                selected_triads+=1
                if all(out is not None for _,out in members):
                    scored_triads+=1
                    correct_triads+=int(all(out.action_label==c.expected.action_label for c,out in members))
                    distinct_triads+=int(len({out.action_label for _,out in members})==3)
            for (a,left),(b,right) in combinations(members,2):
                selected_pairs+=1
                if left is not None and right is not None:
                    scored_pairs+=1
                    changed_pairs+=int(left.action_label!=right.action_label)
                    correct_pairs+=int(left.action_label==a.expected.action_label and right.action_label==b.expected.action_label)
        return dict(selected_triads=selected_triads,scored_triads=scored_triads,correct_triads=correct_triads,
            distinct_prediction_triads=distinct_triads,selected_pairs=selected_pairs,scored_pairs=scored_pairs,
            changed_prediction_pairs=changed_pairs,correct_pairs=correct_pairs,
            pair_change_rate=ratio(changed_pairs,scored_pairs),pair_correct_rate=ratio(correct_pairs,scored_pairs))
    return dict(summary(groups.values()),by_cue={cue:summary(members for members in groups.values()
        if members[0][0].annotations['cue_field']==cue) for cue in ('subject','raw_metadata.status')})


def metrics(cases, outputs, statuses, policy, *, providers=True):
    """No fallback predictions: invalid/unobserved cases never become abstentions.

    Required recall counts semantic-invalid attempts as misses, but excludes infra,
    projection failure and unattempted cases. Three-label matrix contains valid only.
    """
    if not len(cases)==len(outputs)==len(statuses) or any(s not in STATUSES for s in statuses):
        raise local.BenchmarkError()
    records=[]
    matrix={truth:dict.fromkeys(ACTIONS,0) for truth in ACTIONS}
    cohorts={truth:dict(selected=0,evaluated=0,valid=0,invalid=0,not_evaluated=0) for truth in ACTIONS}
    known_domains=classified_domains=required_false_irrelevant=0
    for c,out,status in zip(cases,outputs,statuses):
        if type(c) is not dataset.SyntheticCase or c.split!='development' or (out is None)!=(status!='valid'):
            raise local.BenchmarkError()
        truth=c.expected.action_label
        cohort=cohorts[truth];cohort['selected']+=1
        cohort['evaluated']+=int(status in {'valid','model_invalid'})
        cohort['invalid']+=int(status=='model_invalid')
        cohort['not_evaluated']+=int(status not in {'valid','model_invalid'})
        if out is None:
            continue
        values,_=validate_output(out,c.input,policy)
        cohort['valid']+=1
        matrix[truth][out.action_label]+=1
        known_domains+=int(c.expected.domain_category is not None)
        classified_domains+=int(c.expected.domain_category is not None and out.category is not None)
        required_false_irrelevant+=int(truth=='required' and out.relevance_label=='irrelevant')
        records.append(EvaluationRecord(c.input.provider,out.relevance_label,out.relevance_confidence,
            out.category,out.subcategory,out.domain_confidence,out.action_label,out.action_confidence,
            values['review_recommended'],c.expected))
    base=evaluate(records,policy.categories)
    base.pop('providers',None)
    result=dict(base,selected_count=len(cases),scored_count=sum(s in {'valid','model_invalid'} for s in statuses),
        status_counts={s:statuses.count(s) for s in STATUSES},
        observed_valid_coverage=ratio(len(records),len(cases)),
        semantic_validity=ratio(len(records),sum(s in {'valid','model_invalid'} for s in statuses)),action_confusion=matrix,action_cohorts=cohorts,
        required_recall=ratio(matrix['required']['required'],cohorts['required']['evaluated']),
        required_miss_count=cohorts['required']['evaluated']-matrix['required']['required'],
        required_false_irrelevant_count=required_false_irrelevant,
        not_required_false_positive_count=matrix['not_required']['required'],
        not_required_false_positive_rate=ratio(matrix['not_required']['required'],cohorts['not_required']['valid']),
        uncertain_concrete_count=matrix['uncertain']['required']+matrix['uncertain']['not_required'],
        uncertainty_preserved_count=matrix['uncertain']['uncertain'],
        uncertainty_preserved_rate=ratio(matrix['uncertain']['uncertain'],cohorts['uncertain']['valid']),
        false_irrelevant_count=base['concrete_predictions']['irrelevant']['false_positive'],
        domain_truth_valid_count=known_domains,decisive_domain_coverage=ratio(classified_domains,known_domains),
        triads=triad_metrics(cases,outputs))
    if providers:
        result['providers']={provider:metrics(tuple(c for c in cases if c.input.provider==provider),
            tuple(out for c,out in zip(cases,outputs) if c.input.provider==provider),
            tuple(s for c,s in zip(cases,statuses) if c.input.provider==provider),policy,providers=False)
            for provider in sorted({c.input.provider for c in cases})}
    return result


def _checked_payload(projected, transport, policy, model, model_digest, deadline):
    """Model dispatch takes an approved projection only, not input/case/annotations."""
    if time.monotonic()>=deadline:
        raise local.BenchmarkError()
    payload=local.request_payload(projected,policy,'flat-domain',model)
    if transport.installed_digest(deadline=deadline)!=model_digest:
        raise local.BenchmarkError()
    return payload


def benchmark(*,full=False,model=local.MODEL,transport=None):
    if type(full) is not bool or type(model) is not str or model not in local.MODELS:
        raise local.BenchmarkError()
    if transport is not None and (type(transport) is not local.LocalOllama or transport.model!=model):
        raise local.BenchmarkError()
    try:
        all_cases,policy,corpus=dataset.load_dataset()
        if dataset.digest(corpus)!=dataset.FROZEN_MANIFEST_SHA256:
            raise local.BenchmarkError()
        cases=select_development(all_cases,full=full)
        rules=MetadataRulesAnalyzer(load_rules(dataset.ROOT/'config/metadata-classifier.yaml',policy))
        # Preflight every selected payload before opening the HTTP boundary.
        projected=tuple(projection(c) for c in cases)
        for p in projected:local.request_payload(p,policy,'flat-domain',model)
        transport=transport or local.LocalOllama(model)
        deadline=time.monotonic()+local.RUN_SECONDS
        model_digest=transport.installed_digest(deadline=deadline)
        runtime=transport.runtime_version(deadline=deadline)
    except Exception:
        raise local.BenchmarkError() from None
    manifest=dict(engine_version=ENGINE_VERSION,metrics_version='action-dev-metrics-v1',model=model,
        model_digest=model_digest,ollama_version=runtime,variant='flat-domain',
        prompt_digest=local.digest(local.system_prompt(policy,'flat-domain')),
        schema_digest=local.digest(local.schema(policy,'flat-domain')),options_digest=local.digest(local.OPTIONS),
        thinking={'top_level':False} if model==local.CANDIDATE_MODEL else {'top_level':'not-specified'},
        projection_schema=corpus['projection_schema'],projection_engine=corpus['projection_engine'],
        projection_contract_digest=local.digest({'schema':'metadata_only_v1','engine':corpus['projection_engine'],'input_bytes':16384}),
        generation_endpoint='/api/generate',wire_schema='three-label-domain-path-v1',
        taxonomy_version=policy.taxonomy_version,taxonomy_digest=corpus['taxonomy_sha256'],
        threshold_policy_version=policy.threshold_policy_version,threshold_digest=local.digest(policy.thresholds.__dict__),
        rules_version=rules.version,rules_fingerprint=rules.ruleset.fingerprint,
        dataset_version=corpus['dataset_version'],rubric_version=corpus['rubric_version'],rubric_digest=corpus['rubric_sha256'],
        corpus_manifest_digest=dataset.FROZEN_MANIFEST_SHA256,split='development',development_case_count=60,
        development_annotated_digest=corpus['splits']['development']['annotated_sha256'],
        development_input_digest=corpus['splits']['development']['input_sha256'],
        development_projection_digest=DEVELOPMENT_PROJECTION_SHA256,
        selection='full' if full else 'smoke',selected_count=len(cases),selection_digest=local.digest([c.id for c in cases]),
        selected_projection_digest=local.digest([p.fields for p in projected]),score_policy='uncalibrated-zero-v1')
    counts=Counter(selected=len(cases),attempted=0,projected=0,sent=0,envelopes_valid=0,json_valid=0,valid=0,
                   model_invalid=0,projection_failed=0,infrastructure_failed=0)
    reasons=Counter(dict.fromkeys(local.FAILURE_REASONS,0))
    outputs=[None]*len(cases);statuses=['not_attempted']*len(cases)
    timings=[];walls=[];abort=None
    for i,c in enumerate(cases):
        counts['attempted']+=1
        try:
            # Guard again at dispatch. Never construct a payload from holdout or a whole case.
            if c.split!='development':raise local.BenchmarkError()
            counts['projected']+=1
            payload=_checked_payload(projected[i],transport,policy,model,model_digest,deadline)
            started=time.monotonic();counts['sent']+=1
            try:
                response=transport._request('POST','/api/generate',payload,deadline=deadline)
            finally:
                walls.append(time.monotonic()-started)
            telemetry=local.envelope(response,model)
            counts['envelopes_valid']+=1
            timings.append(telemetry)
            try:
                local.strict_json(response['response']);counts['json_valid']+=1
            except local.BenchmarkError:
                pass
            outputs[i]=local.labels(response['response'],c.input,policy,'flat-domain')
            counts['valid']+=1;statuses[i]='valid'
        except local.ModelPredictionError as error:
            counts['model_invalid']+=1;statuses[i]='model_invalid';reasons[error.reason]+=1
        except Exception as error:
            counts['infrastructure_failed']+=1;statuses[i]='infrastructure_failed'
            reasons['protocol' if isinstance(error,local.ProtocolError) else 'request_identity_or_resource']+=1
            abort='local_request_or_output_rejected';break
    counts['not_attempted']=statuses.count('not_attempted')
    try:
        if time.monotonic()>=deadline or transport.installed_digest(deadline=deadline)!=model_digest:
            raise local.BenchmarkError()
    except Exception:
        return dict(notice='SYNTHETIC DEVELOPMENT ONLY / NOT PRODUCTION ACCURACY',completed=False,
            abort_reason='final_model_identity_unverified',final_model_identity_verified=False,
            counts=dict(counts),failure_reasons=dict(reasons),holdout_inference=False)
    try:
        residency=transport.residency(model_digest,deadline=deadline) if time.monotonic()<deadline else None
    except Exception:
        residency=None  # Optional aggregate observation cannot replace the primary failure.
    baseline=tuple(rules.analyze(c.input,policy) for c in cases)
    token_rows=[r for r in timings if r['eval_count'] is not None and r['eval_duration']]
    return dict(notice='SYNTHETIC DEVELOPMENT ONLY / NOT PRODUCTION ACCURACY',completed=abort is None,
        abort_reason=abort,final_model_identity_verified=True,holdout_inference=False,persistence_exercised=False,
        metrics_scope='all_selected' if abort is None else 'partial_observed',counts=dict(counts),failure_reasons=dict(reasons),
        json_validity_rate=ratio(counts['json_valid'],counts['envelopes_valid']),
        label_validity_rate=ratio(counts['valid'],counts['envelopes_valid']),
        manifest=manifest,manifest_fingerprint=local.digest(manifest),
        definition=dict(analyzer_name='action_development_model',analyzer_version='action-dev-v1-'+local.digest(manifest)[:32],
            definition_fingerprint=policy.fingerprint('action_development_model','action-dev-v1-'+local.digest(manifest)[:32])),
        distributions=dataset.distribution(cases),
        metrics={'model':metrics(cases,tuple(outputs),tuple(statuses),policy),
                 'rules':metrics(cases,baseline,('valid',)*len(cases),policy)},
        performance=dict(request_wall_seconds=local.distribution(walls),first_request_wall_seconds=walls[0] if walls else None,
            later_request_wall_seconds=local.distribution(walls[1:]),generation_envelopes_with_telemetry=len(timings),
            **{key+'_seconds':local.distribution([r[key]/1e9 if r[key] is not None else None for r in timings])
               for key in ('total_duration','load_duration','prompt_eval_duration','eval_duration')},
            generated_tokens_observed=sum(r['eval_count'] or 0 for r in timings),throughput_denominator_requests=len(token_rows),
            generated_tokens_per_second=ratio(sum(r['eval_count'] for r in token_rows),sum(r['eval_duration']/1e9 for r in token_rows)),
            residency_observation=residency),
        budgets=dict(connect_seconds=local.CONNECT_SECONDS,request_seconds=local.REQUEST_SECONDS,run_seconds=local.RUN_SECONDS,
            prompt_max_bytes=local.PROMPT_BYTES,context_tokens=local.OPTIONS['num_ctx'],output_token_cap=local.OPTIONS['num_predict']))


def main(argv=None):
    parser=argparse.ArgumentParser(description='Manual synthetic Action development benchmark; no holdout or household data')
    parser.add_argument('--full',action='store_true',help='explicitly run all 60 frozen development cases; default fixed five-case smoke')
    parser.add_argument('--model',choices=local.MODELS,default=local.MODEL,help='installed allowlisted local model only')
    args=parser.parse_args(argv)
    try:
        result=benchmark(full=args.full,model=args.model)
        print(canonical_json(result))
        return 0 if result['completed'] else 1
    except KeyboardInterrupt:
        print('Synthetic development benchmark stopped; no state persisted.')
        return 130
    except Exception:
        print('Synthetic development benchmark failed; no source content or state persisted. Check documented setup/budgets.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
