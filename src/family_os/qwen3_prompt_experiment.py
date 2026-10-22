"""Manual Qwen3 prompt experiments on pinned synthetic development cases only.

The historical runners are unchanged. Only named generic prompt additions vary;
answers stay evaluation-side and no aggregate report selects a winner.
"""
import argparse
from collections import Counter
import json
import time

from . import action_model_benchmark as control
from .analysis import canonical_json
from .audit import ratio
from .metadata_classifier import MetadataRulesAnalyzer, load_rules

local=control.local
dataset=control.dataset
ENGINE_VERSION='qwen3-prompt-experiment-e1'
PLAN_VERSION='qwen3-prompt-plan-v1'
VARIANTS=('baseline','relevance-clarified','action-evidence','calendar-status')
EDITS={
    'baseline':'',
    'relevance-clarified':(
        ' Relevance clarification: household relevance is not urgency, action-needed or marketing interest. '
        'Genuine household information can remain relevant when paid, cancelled, routine or requiring no current step. '
        'Judge relevance independently of action; unsupported household connection stays uncertain.'),
    'action-evidence':(
        ' Action clarification: required needs an explicit outstanding recipient step in visible metadata. '
        'not_required needs explicit completion or confirmed no-response/informational status. '
        'Missing or ambiguous state stays uncertain. Age, benign category, silence or unclear account state do not prove completion. '
        'Bill, renewal or PDF alone do not prove an obligation; do not mark everything required.'),
    'calendar-status':(
        ' Calendar clarification: interpret visible status together with conditional instructions. '
        'Confirmed can require preparation or attendance; cancelled may clear only the event-specific step, '
        'while explicit refund/rebooking instructions can still require action. Tentative unresolved conditions stay uncertain. '
        'Status alone proves neither an obligation nor its completion; never invent hidden body or account state.'),
}
PLAN={
    'version':PLAN_VERSION,'control':'unchanged-phase-2r-qwen3-flat-domain',
    'hypotheses':{
        'relevance-clarified':'separate-household-relevance-from-urgency-and-action',
        'action-evidence':'distinguish-outstanding-completed-and-missing-visible-state',
        'calendar-status':'interpret-visible-status-with-conditional-instructions',
    },
    'tradeoffs':['required-recall','false-irrelevant','false-required-not-required',
                'false-required-uncertain','preserved-uncertainty','relevance-domain-regressions','latency'],
    'decision':'human-review-no-winner-no-further-tuning-no-holdout',
}


EDIT_SHA256={
    'baseline':'12ae32cb1ec02d01eda3581b127c1fee3b0dc53572ed6baf239721a03d82e126',
    'relevance-clarified':'4e8850c79d40cd5b311b3b0d992764709454e0f9db8f878b603d92ec1c26c12e',
    'action-evidence':'e916cfa5d031b47ce881a113221d11afed03d35f13453ace25614fae89e1cf12',
    'calendar-status':'76e824aed42f63bda682332b079c92d98d3b6eaf3f15a063a6de0a96354fcce4',
}
PROMPT_SHA256={
    'baseline':'ce795381831bceed14df9ca29a30135d0b1293d1060e6a510208925bf5fac14e',
    'relevance-clarified':'ffa86c21d6993fe79afad31a9dec569ea5e405996c2cd6f3eb30a7402061d2e7',
    'action-evidence':'17b9ebaba795938a405652993950ea983c45938b1fbebd53aea1b717a2a6f0d8',
    'calendar-status':'9a6f3a95e18cc90f0587f41a79070db986e287141697b4f129b94cef2d20873c',
}


def system_prompt(policy,variant='baseline'):
    if type(variant) is not str or variant not in VARIANTS:
        raise local.BenchmarkError()
    prompt=local.system_prompt(policy,'flat-domain')+EDITS[variant]
    if local.digest(EDITS[variant])!=EDIT_SHA256[variant] or local.digest(prompt)!=PROMPT_SHA256[variant]:
        raise local.BenchmarkError()
    return prompt


def request_payload(projected,policy,variant='baseline'):
    """No whole cases, answers, IDs or open prompt text accepted at this boundary."""
    if type(projected) is not dataset.MetadataProjection:
        raise local.BenchmarkError()
    original=local.request_payload(projected,policy,'flat-domain',local.MODEL)
    prompt=system_prompt(policy,variant)+'\nUNTRUSTED_METADATA_JSON:\n'+projected.canonical()
    payload=original|{'prompt':prompt}
    if len(prompt.encode())>local.PROMPT_BYTES or len(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode())>local.REQUEST_BYTES:
        raise local.BenchmarkError()
    return payload


def _checked_payload(projected,transport,policy,variant,model_digest,deadline):
    if time.monotonic()>=deadline:
        raise local.BenchmarkError()
    payload=request_payload(projected,policy,variant)
    if transport.installed_digest(deadline=deadline)!=model_digest:
        raise local.BenchmarkError()
    return payload


def diagnostics(cases,outputs,statuses,policy):
    # Reuse Phase 2R validation and cohort accounting, never invent missing predictions.
    def cohort(indices):
        selected=tuple(cases[i] for i in indices)
        predicted=tuple(outputs[i] for i in indices)
        states=tuple(statuses[i] for i in indices)
        base=control.metrics(selected,predicted,states,policy,providers=False)
        required=base['action_confusion']['required']
        valid_required=base['action_cohorts']['required']['valid']
        cross={r:dict.fromkeys(dataset.ACTIONS,0) for r in ('relevant','irrelevant','uncertain')}
        required_cross={r:dict.fromkeys(dataset.ACTIONS,0) for r in cross}
        known=abstained=wrong=unknown=0
        for c,out in zip(selected,predicted):
            if out is None:continue
            cross[out.relevance_label][out.action_label]+=1
            if c.expected.action_label=='required':required_cross[out.relevance_label][out.action_label]+=1
            if c.expected.domain_category is None:unknown+=1
            else:
                known+=1
                abstained+=int(out.category is None)
                wrong+=int(out.category is not None and (out.category,out.subcategory)!=(c.expected.domain_category,c.expected.domain_subcategory))
        return dict(selected_count=len(selected),status_counts=base['status_counts'],
            action_cohorts=base['action_cohorts'],action_confusion=base['action_confusion'],
            required_to_not_required_count=required['not_required'],required_to_not_required_rate=ratio(required['not_required'],valid_required),
            required_to_uncertain_count=required['uncertain'],required_to_uncertain_rate=ratio(required['uncertain'],valid_required),
            required_recall=base['required_recall'],required_miss_count=base['required_miss_count'],
            required_false_irrelevant_count=base['required_false_irrelevant_count'],false_irrelevant_count=base['false_irrelevant_count'],
            uncertain_to_required_count=base['action_confusion']['uncertain']['required'],
            uncertain_to_required_rate=ratio(base['action_confusion']['uncertain']['required'],base['action_cohorts']['uncertain']['valid']),
            prediction_relevance_by_action=cross,required_truth_relevance_by_action=required_cross,
            predicted_required_and_irrelevant_count=cross['irrelevant']['required'],
            domain_known_valid_count=known,domain_unknown_truth_valid_count=unknown,
            domain_abstained_on_known_truth=abstained,domain_wrong_on_known_truth=wrong,
            domain_undercoverage_rate=ratio(abstained,known),triads=base['triads'])
    all_indices=tuple(range(len(cases)))
    result=cohort(all_indices)
    result['providers']={p:cohort(tuple(i for i,c in enumerate(cases) if c.input.provider==p))
                         for p in sorted({c.input.provider for c in cases})}
    result['calendar_status']={status:cohort(tuple(i for i,c in enumerate(cases)
        if c.input.provider=='google_calendar' and c.input.raw_metadata.get('status','missing')==status))
        for status in ('confirmed','cancelled','tentative','missing')}
    result['cue_family']={cue:cohort(tuple(i for i,c in enumerate(cases)
        if (c.annotations['cue_field'] or 'standalone')==cue))
        for cue in ('subject','raw_metadata.status','standalone')}
    return result


def benchmark(*,variant="baseline",full=False,model=local.MODEL,transport=None):
    if type(full) is not bool or type(model) is not str or model!=local.MODEL or type(variant) is not str or variant not in VARIANTS:
        raise local.BenchmarkError()
    if transport is not None and (type(transport) is not local.LocalOllama or transport.model!=model):
        raise local.BenchmarkError()
    try:
        all_cases,policy,corpus=dataset.load_dataset()
        if dataset.digest(corpus)!=dataset.FROZEN_MANIFEST_SHA256:
            raise local.BenchmarkError()
        cases=control.select_development(all_cases,full=full)
        rules=MetadataRulesAnalyzer(load_rules(dataset.ROOT/'config/metadata-classifier.yaml',policy))
        # Preflight every selected payload before opening the HTTP boundary.
        projected=tuple(control.projection(c) for c in cases)
        for p in projected:request_payload(p,policy,variant)
        transport=transport or local.LocalOllama(model)
        deadline=time.monotonic()+local.RUN_SECONDS
        model_digest=transport.installed_digest(deadline=deadline)
        runtime=transport.runtime_version(deadline=deadline)
    except Exception:
        raise local.BenchmarkError() from None
    manifest=dict(engine_version=ENGINE_VERSION,metrics_version='qwen3-prompt-diagnostics-v1',experiment_plan_version=PLAN_VERSION,experiment_plan_digest=local.digest(PLAN),
        experiment_variant=variant,prompt_edit_digest=local.digest(EDITS[variant]),model=model,
        model_digest=model_digest,ollama_version=runtime,variant='flat-domain',
        prompt_digest=local.digest(system_prompt(policy,variant)),
        schema_digest=local.digest(local.schema(policy,'flat-domain')),options_digest=local.digest(local.OPTIONS),
        thinking={'top_level':'not-specified'},
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
        development_projection_digest=control.DEVELOPMENT_PROJECTION_SHA256,
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
            payload=_checked_payload(projected[i],transport,policy,variant,model_digest,deadline)
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
        definition=dict(analyzer_name='qwen3_prompt_experiment',analyzer_version='qwen3-prompt-v1-'+local.digest(manifest)[:32],
            definition_fingerprint=policy.fingerprint('qwen3_prompt_experiment','qwen3-prompt-v1-'+local.digest(manifest)[:32])),
        distributions=dataset.distribution(cases),
        diagnostics=diagnostics(cases,tuple(outputs),tuple(statuses),policy),
        metrics={'model':control.metrics(cases,tuple(outputs),tuple(statuses),policy),
                 'rules':control.metrics(cases,baseline,('valid',)*len(cases),policy)},
        performance=dict(request_wall_seconds=local.distribution(walls),first_request_wall_seconds=walls[0] if walls else None,
            later_request_wall_seconds=local.distribution(walls[1:]),generation_envelopes_with_telemetry=len(timings),
            **{key+'_seconds':local.distribution([r[key]/1e9 if r[key] is not None else None for r in timings])
               for key in ('total_duration','load_duration','prompt_eval_duration','eval_duration')},
            generated_tokens_observed=sum(r['eval_count'] or 0 for r in timings),throughput_denominator_requests=len(token_rows),
            generated_tokens_per_second=ratio(sum(r['eval_count'] for r in token_rows),sum(r['eval_duration']/1e9 for r in token_rows)),
            residency_observation=residency),
        budgets=dict(connect_seconds=local.CONNECT_SECONDS,request_seconds=local.REQUEST_SECONDS,run_seconds=local.RUN_SECONDS,
            prompt_max_bytes=local.PROMPT_BYTES,context_tokens=local.OPTIONS['num_ctx'],output_token_cap=local.OPTIONS['num_predict']))



def _verified_complete(report):
    """Aggregate reference integrity, not proof against fabricated reports."""
    try:
        m=report['manifest'];variant=m['experiment_variant']
        counts=report['counts'];selected=m['selected_count']
        if (report['completed'] is not True or report['final_model_identity_verified'] is not True or
            report['holdout_inference'] is not False or report['metrics_scope']!='all_selected' or
            m['engine_version']!=ENGINE_VERSION or m['experiment_plan_digest']!=local.digest(PLAN) or
            m['metrics_version']!='qwen3-prompt-diagnostics-v1' or m['model']!=local.MODEL or
            m['split']!='development' or m['prompt_digest']!=PROMPT_SHA256[variant] or
            m['prompt_edit_digest']!=EDIT_SHA256[variant] or
            report['manifest_fingerprint']!=local.digest(m) or
            selected not in (5,60) or counts['selected']!=selected or
            any(counts[k]!=selected for k in ('attempted','projected','sent','envelopes_valid','json_valid','valid')) or
            any(counts[k]!=0 for k in ('model_invalid','projection_failed','infrastructure_failed','not_attempted'))):
            raise local.BenchmarkError()
        return m
    except Exception:
        raise local.BenchmarkError() from None


def _compare_reports(reference,candidate):
    """Pure manual comparison; never loads files, starts a model or selects a winner.

    Only complete label-valid runs of this experiment can supply paired deltas.
    Invalid/partial runs retain their own reports, but cannot establish improvement.
    """
    a,b=_verified_complete(reference),_verified_complete(candidate)
    exclusions={'experiment_variant','prompt_edit_digest','prompt_digest'}
    if a['experiment_variant']!='baseline' or {k:v for k,v in a.items() if k not in exclusions}!={k:v for k,v in b.items() if k not in exclusions}:
        raise local.BenchmarkError()
    if reference['metrics']['model']['action_cohorts']!=candidate['metrics']['model']['action_cohorts']:
        raise local.BenchmarkError()
    fields=('required_recall','required_miss_count','false_irrelevant_count','required_false_irrelevant_count',
            'not_required_false_positive_count','uncertain_concrete_count','uncertainty_preserved_rate',
            'relevance_accuracy','decisive_domain_coverage','domain_selective_accuracy')
    rows={}
    for field in fields:
        left,right=reference['metrics']['model'][field],candidate['metrics']['model'][field]
        matched_denominator=field!='domain_selective_accuracy' or reference['metrics']['model']['domain_selective_count']==candidate['metrics']['model']['domain_selective_count']
        rows[field]={'baseline':left,'candidate':right,'delta_comparable':matched_denominator,
            'delta':None if not matched_denominator or left is None or right is None else right-left}
    for field in ('required_to_not_required_count','required_to_uncertain_count','uncertain_to_required_count'):
        left,right=reference['diagnostics'][field],candidate['diagnostics'][field]
        rows[field]={'baseline':left,'candidate':right,'delta':right-left}
    # Preserve conditional-metric denominators rather than hiding changed coverage.
    return dict(comparison='baseline-only',selection=a['selection'],selected_count=a['selected_count'],
        candidate_variant=b['experiment_variant'],baseline_manifest=reference['manifest_fingerprint'],
        candidate_manifest=candidate['manifest_fingerprint'],tradeoffs=rows,
        observed_denominators={'baseline':{k:reference['metrics']['model'][k] for k in
            ('relevance_decisive_count','domain_selective_count','domain_truth_valid_count')},
            'candidate':{k:candidate['metrics']['model'][k] for k in
            ('relevance_decisive_count','domain_selective_count','domain_truth_valid_count')}},
        latency={'baseline':reference['performance']['request_wall_seconds'],
                 'candidate':candidate['performance']['request_wall_seconds']},winner=None)


def _check_reproducibility(first,second):
    a,b=_verified_complete(first),_verified_complete(second)
    if a!=b:
        raise local.BenchmarkError()
    return dict(manifest_fingerprint=first['manifest_fingerprint'],same_configuration=True,
        aggregate_metrics_equal=first['metrics']==second['metrics'],
        aggregate_diagnostics_equal=first['diagnostics']==second['diagnostics'],
        per_case_determinism_established=False)


def compare_reports(reference,candidate):
    try:
        return _compare_reports(reference,candidate)
    except Exception:
        raise local.BenchmarkError() from None


def check_reproducibility(first,second):
    try:
        return _check_reproducibility(first,second)
    except Exception:
        raise local.BenchmarkError() from None


def main(argv=None):
    parser=argparse.ArgumentParser(description='Manual Qwen3 synthetic development prompt experiments; no holdout')
    parser.add_argument('--variant',choices=VARIANTS,default='baseline')
    parser.add_argument('--full',action='store_true',help='explicit 60-case development run; default fixed five-case smoke')
    parser.add_argument('--model',choices=(local.MODEL,),default=local.MODEL)
    args=parser.parse_args(argv)
    try:
        report=benchmark(variant=args.variant,full=args.full,model=args.model)
        print(canonical_json(report))
        return 0 if report['completed'] else 1
    except KeyboardInterrupt:
        print('Synthetic prompt experiment stopped; no state persisted.')
        return 130
    except Exception:
        print('Synthetic prompt experiment failed; no content or state persisted. Check documented setup/budgets.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
