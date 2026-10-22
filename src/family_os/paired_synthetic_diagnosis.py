"""Manual in-memory paired diagnosis; only pinned synthetic development inputs.

No historical aggregate is converted into a case prediction. All four unchanged
Phase 2S prompts run serially under one existing run budget; output is aggregate-only.
"""
import argparse
from collections import Counter
from itertools import combinations
import time

from . import qwen3_prompt_experiment as experiment
from .analysis import canonical_json
from .audit import ratio
from .metadata_classifier import MetadataRulesAnalyzer, load_rules

control=experiment.control
local=experiment.local
dataset=experiment.dataset
VARIANTS=experiment.VARIANTS
ENGINE_VERSION='paired-synthetic-diagnosis-e1'
METRICS_VERSION='paired-transitions-v1'
RELEVANCE=('relevant','irrelevant','uncertain')


class _IdentityMismatch(local.BenchmarkError):
    pass


def matrix(labels):
    return {left:dict.fromkeys(labels,0) for left in labels}


def triad_transitions(cases,baseline,candidate):
    groups={}
    for c,a,b in zip(cases,baseline,candidate):
        group=c.annotations['counterfactual_group']
        if group:groups.setdefault(group,[]).append((c,a,b))
    def summarize(groups):
        triads=matrix(('incorrect','correct'));pairs=matrix(('incorrect','correct'))
        sensitivity=matrix(('same','changed'))
        selected_triads=scored_triads=selected_pairs=scored_pairs=0
        for members in groups:
            if len(members)==3:
                selected_triads+=1
                if all(a is not None and b is not None for _,a,b in members):
                    scored_triads+=1
                    a=all(a.action_label==c.expected.action_label for c,a,_ in members)
                    b=all(b.action_label==c.expected.action_label for c,_,b in members)
                    triads['correct' if a else 'incorrect']['correct' if b else 'incorrect']+=1
            for (c,a,b),(d,x,y) in combinations(members,2):
                selected_pairs+=1
                if any(out is None for out in (a,b,x,y)):continue
                scored_pairs+=1
                left=a.action_label==c.expected.action_label and x.action_label==d.expected.action_label
                right=b.action_label==c.expected.action_label and y.action_label==d.expected.action_label
                pairs['correct' if left else 'incorrect']['correct' if right else 'incorrect']+=1
                sensitivity['changed' if a.action_label!=x.action_label else 'same'][
                    'changed' if b.action_label!=y.action_label else 'same']+=1
        return dict(selected_triads=selected_triads,paired_valid_triads=scored_triads,
            triad_correctness_transitions=triads,selected_pairs=selected_pairs,paired_valid_pairs=scored_pairs,
            pair_correctness_transitions=pairs,pair_sensitivity_transitions=sensitivity,
            candidate_pair_correct_rate=ratio(sum(row['correct'] for row in pairs.values()),scored_pairs))
    return dict(summarize(groups.values()),by_cue={cue:summarize(members for members in groups.values()
        if members[0][0].annotations['cue_field']==cue) for cue in ('subject','raw_metadata.status')})


def paired_metrics(cases,baseline,baseline_status,candidate,candidate_status,policy):
    # This also enforces exact length/status/output consistency and shared validation.
    if any(out is not None and (out.relevance_confidence!=0 or out.action_confidence!=0 or
        out.domain_confidence!=0 or out.facts) for out in (*baseline,*candidate)):
        raise local.BenchmarkError()
    control.metrics(cases,baseline,baseline_status,policy,providers=False)
    control.metrics(cases,candidate,candidate_status,policy,providers=False)
    def cohort(indices):
        actions=matrix(dataset.ACTIONS);relevance=matrix(RELEVANCE)
        statuses=matrix(control.STATUSES);false_irrelevant=matrix(('no','yes'))
        recovery_relevance=matrix(RELEVANCE);new_miss_relevance=matrix(RELEVANCE)
        required=Counter(paired=0,baseline_missed=0,baseline_correct=0,recovered=0,newly_missed=0,
            both_missed=0,both_correct=0,recovered_from_not_required=0,recovered_from_uncertain=0,
            newly_not_required=0,newly_uncertain=0,recovered_but_candidate_irrelevant=0)
        uncertain=Counter(paired=0,preserved_both=0,newly_concrete=0,recovered_uncertainty=0,
                          concrete_both=0,newly_required=0,newly_not_required=0)
        domains=Counter(known_truth_paired=0,unknown_truth_paired=0,recovered_correct=0,newly_wrong=0,
            baseline_abstained=0,candidate_abstained=0)
        paired=0;review=0
        subset=tuple(cases[i] for i in indices)
        left=tuple(baseline[i] for i in indices);right=tuple(candidate[i] for i in indices)
        for i in indices:
            statuses[baseline_status[i]][candidate_status[i]]+=1
            a,b=baseline[i],candidate[i];c=cases[i]
            if a is None or b is None:continue
            paired+=1;review+=1  # zero-confidence model suggestions never authorize actions
            actions[a.action_label][b.action_label]+=1
            relevance[a.relevance_label][b.relevance_label]+=1
            ai=c.expected.relevance_label=='relevant' and a.relevance_label=='irrelevant'
            bi=c.expected.relevance_label=='relevant' and b.relevance_label=='irrelevant'
            false_irrelevant['yes' if ai else 'no']['yes' if bi else 'no']+=1
            if c.expected.action_label=='required':
                ac=a.action_label=='required';bc=b.action_label=='required'
                required['paired']+=1;required['baseline_missed']+=int(not ac);required['baseline_correct']+=int(ac)
                required['recovered']+=int(not ac and bc);required['newly_missed']+=int(ac and not bc)
                required['both_missed']+=int(not ac and not bc);required['both_correct']+=int(ac and bc)
                required['recovered_from_not_required']+=int(a.action_label=='not_required' and bc)
                required['recovered_from_uncertain']+=int(a.action_label=='uncertain' and bc)
                required['newly_not_required']+=int(ac and b.action_label=='not_required')
                required['newly_uncertain']+=int(ac and b.action_label=='uncertain')
                required['recovered_but_candidate_irrelevant']+=int(not ac and bc and b.relevance_label=='irrelevant')
                if not ac and bc:recovery_relevance[a.relevance_label][b.relevance_label]+=1
                if ac and not bc:new_miss_relevance[a.relevance_label][b.relevance_label]+=1
            if c.expected.action_label=='uncertain':
                au=a.action_label=='uncertain';bu=b.action_label=='uncertain'
                uncertain['paired']+=1;uncertain['preserved_both']+=int(au and bu)
                uncertain['newly_concrete']+=int(au and not bu);uncertain['recovered_uncertainty']+=int(not au and bu)
                uncertain['concrete_both']+=int(not au and not bu)
                uncertain['newly_required']+=int(au and b.action_label=='required')
                uncertain['newly_not_required']+=int(au and b.action_label=='not_required')
            if c.expected.domain_category is None:domains['unknown_truth_paired']+=1
            else:
                truth=(c.expected.domain_category,c.expected.domain_subcategory)
                ac=(a.category,a.subcategory)==truth;bc=(b.category,b.subcategory)==truth
                domains['known_truth_paired']+=1;domains['recovered_correct']+=int(not ac and bc)
                domains['newly_wrong']+=int(ac and not bc)
                domains['baseline_abstained']+=int(a.category is None);domains['candidate_abstained']+=int(b.category is None)
        return dict(selected_count=len(indices),paired_valid_count=paired,unpaired_count=len(indices)-paired,
            paired_valid_coverage=ratio(paired,len(indices)),status_transitions=statuses,
            action_transitions=actions,relevance_transitions=relevance,false_irrelevant_transitions=false_irrelevant,
            required=dict(required,recovery_rate=ratio(required['recovered'],required['baseline_missed']),
                new_miss_rate=ratio(required['newly_missed'],required['baseline_correct'])),
            required_recovery_relevance_transitions=recovery_relevance,
            required_new_miss_relevance_transitions=new_miss_relevance,
            uncertain=dict(uncertain),domain=dict(domains),human_review_only_count=review,
            triads=triad_transitions(subset,left,right))
    all_indices=tuple(range(len(cases)))
    result=cohort(all_indices)
    result['by_provider']={p:cohort(tuple(i for i,c in enumerate(cases) if c.input.provider==p))
                          for p in sorted({c.input.provider for c in cases})}
    result['by_truth_action']={a:cohort(tuple(i for i,c in enumerate(cases) if c.expected.action_label==a)) for a in dataset.ACTIONS}
    result['by_truth_relevance']={r:cohort(tuple(i for i,c in enumerate(cases) if c.expected.relevance_label==r)) for r in RELEVANCE}
    result['by_calendar_status']={status:cohort(tuple(i for i,c in enumerate(cases)
        if c.input.provider=='google_calendar' and c.input.raw_metadata.get('status','missing')==status))
        for status in ('confirmed','cancelled','tentative','missing')}
    result['by_cue_family']={cue:cohort(tuple(i for i,c in enumerate(cases)
        if (c.annotations['cue_field'] or 'standalone')==cue)) for cue in ('subject','raw_metadata.status','standalone')}
    return result


def ensure_comparable(identities):
    """Reject even one variant with different version/configuration before pairing."""
    try:
        if type(identities) is not dict or set(identities)!=set(VARIANTS):raise local.BenchmarkError()
        common=None
        for variant in VARIANTS:
            identity=identities[variant]
            if (identity['engine']!=ENGINE_VERSION or identity['metrics_version']!=METRICS_VERSION or
                identity['split']!='development' or identity['corpus_manifest_digest']!=dataset.FROZEN_MANIFEST_SHA256 or
                identity['development_projection_digest']!=control.DEVELOPMENT_PROJECTION_SHA256 or
                identity['experiment_variant']!=variant or identity['model']!=local.MODEL or
                identity['prompt_digest']!=experiment.PROMPT_SHA256[variant] or
                identity['prompt_edit_digest']!=experiment.EDIT_SHA256[variant]):raise local.BenchmarkError()
            core={k:v for k,v in identity.items() if k not in {'experiment_variant','prompt_digest','prompt_edit_digest'}}
            if common is not None and core!=common:raise local.BenchmarkError()
            common=core
    except Exception:
        raise local.BenchmarkError() from None


def benchmark(*,full=False,transport=None):
    if type(full) is not bool or (transport is not None and
        (type(transport) is not local.LocalOllama or transport.model!=local.MODEL)):raise local.BenchmarkError()
    try:
        all_cases,policy,corpus=dataset.load_dataset()
        if dataset.digest(corpus)!=dataset.FROZEN_MANIFEST_SHA256:raise local.BenchmarkError()
        cases=control.select_development(all_cases,full=full)
        projected=tuple(control.projection(c) for c in cases)
        # Every one of all four variants is preflighted before any network activity.
        for variant in VARIANTS:
            for p in projected:experiment.request_payload(p,policy,variant)
        rules=MetadataRulesAnalyzer(load_rules(dataset.ROOT/'config/metadata-classifier.yaml',policy))
        transport=transport or local.LocalOllama()
        deadline=time.monotonic()+local.RUN_SECONDS
        model_digest=transport.installed_digest(deadline=deadline)
        runtime=transport.runtime_version(deadline=deadline)
    except Exception:
        raise local.BenchmarkError() from None
    common=dict(engine=ENGINE_VERSION,metrics_version=METRICS_VERSION,model=local.MODEL,model_digest=model_digest,
        ollama_version=runtime,schema_digest=local.digest(local.schema(policy,'flat-domain')),
        options_digest=local.digest(local.OPTIONS),thinking='not-specified',wire_variant='flat-domain',
        projection_schema=corpus['projection_schema'],projection_engine=corpus['projection_engine'],
        development_projection_digest=control.DEVELOPMENT_PROJECTION_SHA256,
        corpus_manifest_digest=dataset.FROZEN_MANIFEST_SHA256,rubric_digest=corpus['rubric_sha256'],
        development_input_digest=corpus['splits']['development']['input_sha256'],
        development_annotated_digest=corpus['splits']['development']['annotated_sha256'],
        taxonomy_version=policy.taxonomy_version,taxonomy_digest=corpus['taxonomy_sha256'],
        threshold_policy_version=policy.threshold_policy_version,threshold_digest=local.digest(policy.thresholds.__dict__),
        rules_version=rules.version,rules_fingerprint=rules.ruleset.fingerprint,
        experiment_plan_digest=local.digest(experiment.PLAN),split='development',selection='full' if full else 'smoke',
        selected_count=len(cases),selection_digest=local.digest([c.id for c in cases]),
        selected_projection_digest=local.digest([p.fields for p in projected]),
        schedule='variant-major-frozen-order',global_run_seconds=local.RUN_SECONDS,score_policy='uncalibrated-zero-v1')
    identities={v:common|dict(experiment_variant=v,prompt_digest=local.digest(experiment.system_prompt(policy,v)),
        prompt_edit_digest=local.digest(experiment.EDITS[v])) for v in VARIANTS}
    ensure_comparable(identities)
    counts={v:Counter(selected=len(cases),attempted=0,sent=0,envelopes_valid=0,json_valid=0,valid=0,model_invalid=0,
        infrastructure_failed=0,projection_failed=0) for v in VARIANTS}
    outputs={v:[None]*len(cases) for v in VARIANTS}
    statuses={v:['not_attempted']*len(cases) for v in VARIANTS}
    reasons={v:Counter(dict.fromkeys(local.FAILURE_REASONS,0)) for v in VARIANTS}
    walls={v:[] for v in VARIANTS};telemetry={v:[] for v in VARIANTS}
    abort=None;identity_rejected=False
    for variant in VARIANTS:
        try:
            if transport.runtime_version(deadline=deadline)!=runtime:raise _IdentityMismatch()
            for i,c in enumerate(cases):
                counts[variant]['attempted']+=1
                try:
                    if c.split!='development':raise local.BenchmarkError()
                    payload=experiment.request_payload(projected[i],policy,variant)
                    if time.monotonic()>=deadline:raise local.BenchmarkError()
                    if transport.installed_digest(deadline=deadline)!=model_digest:raise _IdentityMismatch()
                    start=time.monotonic();counts[variant]['sent']+=1
                    try:response=transport._request('POST','/api/generate',payload,deadline=deadline)
                    finally:walls[variant].append(time.monotonic()-start)
                    envelope=local.envelope(response)
                    counts[variant]['envelopes_valid']+=1;telemetry[variant].append(envelope)
                    try:local.strict_json(response['response']);counts[variant]['json_valid']+=1
                    except local.BenchmarkError:pass
                    outputs[variant][i]=local.labels(response['response'],c.input,policy,'flat-domain')
                    counts[variant]['valid']+=1;statuses[variant][i]='valid'
                except local.ModelPredictionError as error:
                    counts[variant]['model_invalid']+=1;statuses[variant][i]='model_invalid';reasons[variant][error.reason]+=1
                except Exception as error:
                    identity_rejected=isinstance(error,_IdentityMismatch)
                    counts[variant]['infrastructure_failed']+=1;statuses[variant][i]='infrastructure_failed'
                    reasons[variant]['protocol' if isinstance(error,local.ProtocolError) else 'request_identity_or_resource']+=1
                    abort='local_request_or_output_rejected';break
        except Exception as error:
            identity_rejected=isinstance(error,_IdentityMismatch)
            abort='runtime_identity_rejected'
        if abort:break
    for v in VARIANTS:counts[v]['not_attempted']=statuses[v].count('not_attempted')
    verified=True
    try:
        if (identity_rejected or time.monotonic()>=deadline or transport.installed_digest(deadline=deadline)!=model_digest or
            transport.runtime_version(deadline=deadline)!=runtime):raise local.BenchmarkError()
    except Exception:verified=False
    base=dict(notice='SYNTHETIC DEVELOPMENT ONLY / NOT PRODUCTION ACCURACY',completed=abort is None and verified,
        abort_reason=abort if verified else 'final_identity_or_configuration_unverified',
        final_model_identity_verified=verified,configuration_comparable=verified,
        warning=None if verified else 'runs_differ_or_identity_unverifiable_no_paired_attribution',
        counts={v:dict(counts[v]) for v in VARIANTS},failure_reasons={v:dict(reasons[v]) for v in VARIANTS},
        holdout_inference=False,persistence_exercised=False,automatic_promotion=False)
    if not verified:return base
    ensure_comparable(identities)
    base.update(manifest=common,variant_identities=identities,manifest_fingerprint=local.digest(identities),
        metrics_scope='partial_observed' if abort else 'all_selected',
        variants={v:dict(metrics=control.metrics(cases,tuple(outputs[v]),tuple(statuses[v]),policy),
            diagnostics=experiment.diagnostics(cases,tuple(outputs[v]),tuple(statuses[v]),policy),
            json_validity_rate=ratio(counts[v]['json_valid'],counts[v]['envelopes_valid']),
            label_validity_rate=ratio(counts[v]['valid'],counts[v]['envelopes_valid'])) for v in VARIANTS},
        comparisons={v:paired_metrics(cases,outputs['baseline'],statuses['baseline'],outputs[v],statuses[v],policy)
                     for v in VARIANTS if v!='baseline'},
        performance={v:dict(request_wall_seconds=local.distribution(walls[v]),
            generated_tokens_per_second=ratio(sum(r['eval_count'] for r in telemetry[v] if r['eval_count'] is not None and r['eval_duration']),
                sum(r['eval_duration']/1e9 for r in telemetry[v] if r['eval_count'] is not None and r['eval_duration']))) for v in VARIANTS},
        budgets=dict(connect_seconds=local.CONNECT_SECONDS,request_seconds=local.REQUEST_SECONDS,
            run_seconds=local.RUN_SECONDS,prompt_bytes=local.PROMPT_BYTES,output_tokens=local.OPTIONS['num_predict']))
    return base


def main(argv=None):
    parser=argparse.ArgumentParser(description='Manual paired synthetic development diagnosis; all four fixed prompts, no holdout')
    parser.add_argument('--full',action='store_true',help='60 development cases per variant; default fixed five per variant')
    args=parser.parse_args(argv)
    try:
        report=benchmark(full=args.full)
        print(canonical_json(report))
        return 0 if report['completed'] else 1
    except KeyboardInterrupt:
        print('Synthetic paired diagnosis stopped; no state persisted.')
        return 130
    except Exception:
        print('Synthetic paired diagnosis failed; no source content or state persisted. Check documented setup/budgets.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
