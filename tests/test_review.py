"""Synthetic-only local terminal review, exact display/save races and selection."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from io import StringIO
from threading import Barrier
import json
import socket

import pytest
from sqlalchemy import update, event

from family_os import review_services as services, review_terminal as terminal
from family_os.analysis import AnalysisValidationError, AnalysisPersistenceError, load_classification
from family_os.audit import HumanLabels
from family_os.audit_services import append_label, audit_metrics
from family_os.cli import main
from family_os.schema import source_record, source_analysis, analysis_evaluation_label, raw_source_record, source_sync_state, analysis_fact
from test_coverage import build
from test_analysis import rows, POLICY, ROOT

LABEL = HumanLabels('uncertain',None,None,'uncertain')
OPTIONS = dict(since='2026-01-01',until='2027-01-01')

class TTY(StringIO):
    def isatty(self): return True


def cohort(engine, *, subject='SYNTHETIC PRIVATE TITLE', provider='gmail', account='a', unanalyzed=False, **options):
    analysis=build(engine, provider=provider,subject=subject,account=account,**options)
    if unanalyzed:
        with engine.begin() as connection: connection.execute(source_analysis.delete().where(source_analysis.c.id==analysis.id))
    return analysis


def select(engine, **options):
    return services.select_review(engine,'home',**(OPTIONS | options))


def run(engine, answers, **options):
    output=TTY()
    summary=terminal.run_review(engine,'home',input_stream=TTY(answers),output_stream=output,**(OPTIONS | options))
    return summary,output.getvalue()


def history(engine):
    return [rows(engine, table) for table in (source_record,raw_source_record,source_analysis,analysis_fact,analysis_evaluation_label,source_sync_state)]


@pytest.mark.parametrize('timestamp,included',[
    (datetime(2025,12,31,23,59,59,tzinfo=timezone.utc),False),
    (datetime(2026,1,1,tzinfo=timezone.utc),True),
    (datetime(2026,1,1,23,59,59,tzinfo=timezone.utc),True),
    (datetime(2026,1,2,tzinfo=timezone.utc),False),
    (datetime(1900,1,1,tzinfo=timezone.utc),False),(None,False)])
def test_utc_half_open_date_window_missing_and_placeholder(engine,timestamp,included):
    analysis=cohort(engine)
    with engine.begin() as connection: connection.execute(update(source_record).where(source_record.c.id==analysis.source_record_id).values(occurred_at=timestamp))
    selection=select(engine,until='2026-01-02')
    assert bool(selection.items)==included


@pytest.mark.parametrize('options', [dict(since='2026-1-01'),dict(since='2026-02-30'),dict(since='private'),
    dict(until='2026-01-01'),dict(until='2025-01-01'),dict(since=None),dict(limit=0),dict(limit=51),dict(limit=True),
    dict(limit=1.5),dict(provider='private@example.invalid'),dict(include_labeled=1)])
def test_invalid_selection_fails_closed(engine,options):
    with pytest.raises(AnalysisValidationError): select(engine,**options)


def test_default_until_is_tomorrow_utc(engine):
    cohort(engine)
    selection=services.select_review(engine,'home',since='2026-01-01')
    from datetime import timedelta
    assert selection.until==(datetime.now(timezone.utc).date()+timedelta(days=1)).isoformat()


def test_recent_provider_type_fairness_multiple_accounts_and_sparse_redistribution(engine):
    for i in range(5): cohort(engine,account=f'g{i}',month=i+1)
    newest=cohort(engine,account='latest',month=12)
    type2=cohort(engine,account='type2',record_type='document',month=11)
    for provider in ('outlook','google_drive','google_calendar'):
        cohort(engine,provider=provider,account=provider,month=10)
    first=select(engine,limit=5)
    assert first==select(engine,limit=5)
    assert {item.provider for item in first.items}=={'gmail','outlook','google_drive','google_calendar'}
    gmail=[item for item in first.items if item.provider=='gmail']
    assert {item.ticket.source_record_id for item in gmail}=={newest.source_record_id,type2.source_record_id}
    assert len(select(engine,limit=9).items)==9


def test_ties_have_stable_id_order_and_provider_filter(engine):
    a=cohort(engine,account='a')
    b=cohort(engine,account='b')
    cohort(engine,provider='outlook',account='o')
    sample=select(engine,provider='gmail')
    assert [item.ticket.source_record_id for item in sample.items]==sorted((a.source_record_id,b.source_record_id))


def test_skip_labeled_only_exact_current_snapshot_definition(engine):
    analysis=cohort(engine)
    append_label(engine,'home',analysis.id,LABEL)
    assert not select(engine).items
    shown=select(engine,include_labeled=True).items[0]
    assert shown.latest_human_revision==1 and shown.human_labels['relevance_label']=='uncertain'
    with engine.begin() as connection:
        connection.execute(update(source_analysis).where(source_analysis.c.id==analysis.id).values(analyzer_version='old-version'))
    new=select(engine).items[0]
    assert new.prediction_origin=='dry_run' and new.latest_human_revision is None


@pytest.mark.parametrize('answers', ['s\n','q\n','', 'l\nq\n','l\n1\nunknown\n3\nno\n',
                                    'l\n1\nunknown\n3\nyes\n'])
def test_skip_quit_eof_and_unconfirmed_input_write_nothing(engine,answers):
    cohort(engine,unanalyzed=True)
    before=history(engine)
    summary,output=run(engine,answers)
    assert history(engine)==before
    assert summary['labeled']==0
    assert summary['displayed']==1
    aggregate=output.split('Session summary: ')[1]
    assert 'SYNTHETIC PRIVATE' not in aggregate and 'source_record_id' not in aggregate


def test_confirm_complete_label_analyzes_and_appends_atomically(engine):
    cohort(engine,unanalyzed=True)
    summary,output=run(engine,'l\n1\nhome\nutility\n1\nsave\n')
    assert summary['labeled']==1 and 'Saved an append-only' in output
    assert len(rows(engine,source_analysis))==len(rows(engine,analysis_evaluation_label))==1
    label=rows(engine,analysis_evaluation_label)[0]
    assert (label['relevance_label'],label['domain_category'],label['domain_subcategory'],label['action_label'])==('relevant','home','utility','required')
    assert not select(engine).items
    assert audit_metrics(engine,'home')['labeled_count']==1


def test_correction_reuses_analysis_and_appends_revision(engine):
    analysis=cohort(engine)
    before=rows(engine,source_analysis)
    ticket=select(engine).items[0].ticket
    a=services.save_review(engine,ticket,LABEL,confirmed=True)
    b=services.save_review(engine,ticket,HumanLabels('irrelevant','ignore','newsletter','not_required'),confirmed=True)
    assert (a.revision,b.revision)==(1,2)
    assert a.analysis_id==b.analysis_id==analysis.id
    assert rows(engine,source_analysis)==before
    assert not select(engine).items


def test_invalid_prompt_choices_never_inherit_predictions(engine):
    cohort(engine)
    summary,output=run(engine,'bad\nl\n99\n3\nunknown\ninvalid\n3\nsave\n')
    assert summary['labeled']==1 and output.count('Invalid choice')==3
    label=rows(engine,analysis_evaluation_label)[0]
    assert label['relevance_label']==label['action_label']=='uncertain'
    assert label['domain_category'] is label['domain_subcategory'] is None


@pytest.mark.parametrize('confirmed',[False,None,'save',1])
def test_service_requires_explicit_boolean_confirmation(engine,confirmed):
    cohort(engine,unanalyzed=True)
    item=select(engine).items[0]
    before=history(engine)
    with pytest.raises(AnalysisValidationError): services.save_review(engine,item.ticket,LABEL,confirmed=confirmed)
    assert history(engine)==before


@pytest.mark.parametrize('labels',[HumanLabels('bad',None,None,'uncertain'),HumanLabels('relevant','home',None,'required'),
                                  HumanLabels('relevant','home','hotel','required')])
def test_invalid_labels_cannot_create_dry_run_analysis(engine,labels):
    cohort(engine,unanalyzed=True)
    ticket=select(engine).items[0].ticket
    with pytest.raises(AnalysisValidationError): services.save_review(engine,ticket,labels,confirmed=True)
    assert not rows(engine,source_analysis) and not rows(engine,analysis_evaluation_label)


def change_snapshot(engine,source_id):
    from uuid import uuid4
    source=next(row for row in rows(engine,source_record) if row['id']==source_id)
    raw=next(row for row in rows(engine,raw_source_record) if row['id']==source['raw_record_id'])
    raw=dict(raw,id=str(uuid4()),payload_hash=str(uuid4()))
    with engine.begin() as connection:
        connection.execute(raw_source_record.insert().values(**raw))
        connection.execute(update(source_record).where(source_record.c.id==source_id).values(raw_record_id=raw['id']))


@pytest.mark.parametrize('when',['after_display','during_inference','before_final_transaction'])
def test_snapshot_race_zero_analysis_and_label_writes(engine,monkeypatch,when):
    analysis=cohort(engine,unanalyzed=True)
    ticket=select(engine).items[0].ticket
    if when=='after_display': change_snapshot(engine,analysis.source_record_id)
    elif when=='during_inference':
        from family_os.metadata_classifier import MetadataRulesAnalyzer
        analyze=MetadataRulesAnalyzer.analyze
        def racing(self,input,policy):
            assert engine.pool.checkedout()==0
            change_snapshot(engine,analysis.source_record_id)
            return analyze(self,input,policy)
        monkeypatch.setattr(MetadataRulesAnalyzer,'analyze',racing)
    else:
        persist=services._persist_analysis
        def racing(connection,household,prepared):
            change_snapshot(engine,analysis.source_record_id)
            return persist(connection,household,prepared)
        monkeypatch.setattr(services,'_persist_analysis',racing)
    with pytest.raises(services.ReviewChangedError): services.save_review(engine,ticket,LABEL,confirmed=True)
    assert not rows(engine,source_analysis) and not rows(engine,analysis_evaluation_label)


def test_input_change_without_raw_pointer_change_also_rejected(engine):
    analysis=cohort(engine,unanalyzed=True)
    ticket=select(engine).items[0].ticket
    with engine.begin() as connection:
        connection.execute(update(source_record).where(source_record.c.id==analysis.source_record_id).values(subject='OTHER PRIVATE INPUT'))
    with pytest.raises(services.ReviewChangedError): services.save_review(engine,ticket,LABEL,confirmed=True)
    assert not rows(engine,source_analysis)


@pytest.mark.parametrize('config_kind',['rules','taxonomy','threshold'])
def test_definition_changed_after_display_rejected(engine,tmp_path,config_kind):
    import yaml
    cohort(engine,unanalyzed=True)
    classification=tmp_path/'classification.yaml'
    rules=tmp_path/'rules.yaml'
    classification.write_text((ROOT/'config/classification.yaml').read_text())
    rules.write_text((ROOT/'config/metadata-classifier.yaml').read_text())
    options=dict(classification_path=classification,rules_path=rules)
    ticket=select(engine,**options).items[0].ticket
    path=rules if config_kind=='rules' else classification
    data=yaml.safe_load(path.read_text())
    if config_kind=='rules': data['ruleset_version']='changed-version'
    elif config_kind=='taxonomy': data['taxonomy_version']='changed-version'
    else: data['threshold_policy_version']='changed-version'
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(services.ReviewChangedError): services.save_review(engine,ticket,LABEL,confirmed=True,**options)
    assert not rows(engine,source_analysis) and not rows(engine,analysis_evaluation_label)


def test_label_insert_failure_rolls_back_new_analysis(engine,monkeypatch):
    cohort(engine,unanalyzed=True)
    ticket=select(engine).items[0].ticket
    def fail(*args): raise RuntimeError('PRIVATE MESSAGE https://secret.invalid')
    monkeypatch.setattr(services,'_append_label',fail)
    with pytest.raises(AnalysisPersistenceError) as error: services.save_review(engine,ticket,LABEL,confirmed=True)
    assert 'PRIVATE' not in str(error.value)
    assert not rows(engine,source_analysis) and not rows(engine,analysis_evaluation_label)


def test_true_concurrent_confirmation_converges_analysis_and_allocates_revisions(engine,monkeypatch):
    cohort(engine,unanalyzed=True)
    ticket=select(engine).items[0].ticket
    barrier=Barrier(2)
    prepare=services._prepare_analysis
    def synchronized(*args,**kwargs):
        prepared=prepare(*args,**kwargs)
        barrier.wait(timeout=15)
        return prepared
    monkeypatch.setattr(services,'_prepare_analysis',synchronized)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:services.save_review(engine,ticket,LABEL,confirmed=True),range(2)))
    assert sorted(result.revision for result in results)==[1,2]
    assert len({result.analysis_id for result in results})==1
    assert len(rows(engine,source_analysis))==1 and len(rows(engine,analysis_evaluation_label))==2


def test_non_tty_cli_fails_before_database_creation(monkeypatch,caplog):
    monkeypatch.setattr('family_os.review_terminal.sys.stdin',StringIO('l\n1\nunknown\n1\nsave\n'))
    monkeypatch.setattr('family_os.cli.create_db',lambda _:pytest.fail('database touched'))
    assert main(['metadata-review','--household','home','--since','2026-01-01'])==1
    assert 'requires interactive stdin and stdout' in caplog.text


def test_local_display_allowlist_and_aggregate_privacy_no_network(engine,monkeypatch):
    cohort(engine)
    monkeypatch.setattr(socket,'socket',lambda *args,**kwargs:pytest.fail('network'))
    summary,output=run(engine,'s\n')
    assert 'SYNTHETIC PRIVATE TITLE' in output and 'SENSITIVE LOCAL OUTPUT' in output
    assert 'DO NOT DISPLAY' not in output and 'PRIVATE BODY' not in output
    assert 'source_record_id' not in output and 'raw_record_id' not in output
    assert 'SYNTHETIC PRIVATE' not in json.dumps(summary)


def test_terminal_control_characters_are_escaped(engine):
    cohort(engine,subject='TITLE\x1b[2J\rFake prompt')
    _,output=run(engine,'s\n')
    assert '\x1b' not in output and '\r' not in output


def test_empty_cohort_and_immediate_quit_are_safe(engine):
    cohort(engine)
    summary,_=run(engine,'q\n',since='2026-02-01')
    assert summary['displayed']==0 and summary['labeled']==0


def test_current_snapshot_with_old_label_remains_eligible(engine):
    analysis=cohort(engine)
    append_label(engine,'home',analysis.id,LABEL)
    change_snapshot(engine,analysis.source_record_id)
    item=select(engine).items[0]
    assert item.ticket.raw_record_id!=analysis.raw_record_id
    assert item.prediction_origin=='dry_run' and item.latest_human_revision is None
    assert rows(engine,analysis_evaluation_label)[0]['analysis_id']==analysis.id


def test_version_change_during_preparation_rejects_before_any_insert(engine,monkeypatch,tmp_path):
    import yaml
    cohort(engine,unanalyzed=True)
    path=tmp_path/'rules.yaml'
    path.write_text((ROOT/'config/metadata-classifier.yaml').read_text())
    ticket=select(engine,rules_path=path).items[0].ticket
    prepare=services._prepare_analysis
    def changing(*args,**kwargs):
        prepared=prepare(*args,**kwargs)
        data=yaml.safe_load(path.read_text());data['ruleset_version']='changed'
        path.write_text(yaml.safe_dump(data))
        return prepared
    monkeypatch.setattr(services,'_prepare_analysis',changing)
    with pytest.raises(services.ReviewChangedError): services.save_review(engine,ticket,LABEL,confirmed=True,rules_path=path)
    assert not rows(engine,source_analysis) and not rows(engine,analysis_evaluation_label)


def test_changed_displayed_existing_analysis_does_not_get_a_label(engine):
    analysis=cohort(engine)
    ticket=select(engine).items[0].ticket
    before=rows(engine,source_analysis)
    change_snapshot(engine,analysis.source_record_id)
    with pytest.raises(services.ReviewChangedError): services.save_review(engine,ticket,LABEL,confirmed=True)
    assert rows(engine,source_analysis)==before and not rows(engine,analysis_evaluation_label)


def test_keyboard_interrupt_during_prompt_writes_nothing(engine):
    cohort(engine,unanalyzed=True)
    class Interrupted(TTY):
        def readline(self,*args): raise KeyboardInterrupt()
    output=TTY()
    summary=terminal.run_review(engine,'home',input_stream=Interrupted(),output_stream=output,**OPTIONS)
    assert summary['aborted']==1
    assert not rows(engine,source_analysis) and not rows(engine,analysis_evaluation_label)


def test_keyboard_interrupt_during_atomic_save_rolls_back(engine,monkeypatch):
    cohort(engine,unanalyzed=True)
    def interrupted(*args): raise KeyboardInterrupt()
    monkeypatch.setattr(services,'_append_label',interrupted)
    summary,_=run(engine,'l\n3\nunknown\n3\nsave\n')
    assert summary['aborted']==1
    assert not rows(engine,source_analysis) and not rows(engine,analysis_evaluation_label)


def test_typed_conflict_can_be_explicitly_retried_without_orphan_analysis(engine,monkeypatch):
    from family_os.audit_services import EvaluationRevisionConflictError
    cohort(engine,unanalyzed=True)
    ticket=select(engine).items[0].ticket
    append=services._append_label
    def conflict(*args): raise EvaluationRevisionConflictError()
    monkeypatch.setattr(services,'_append_label',conflict)
    with pytest.raises(EvaluationRevisionConflictError): services.save_review(engine,ticket,LABEL,confirmed=True)
    assert not rows(engine,source_analysis) and not rows(engine,analysis_evaluation_label)
    monkeypatch.setattr(services,'_append_label',append)
    assert services.save_review(engine,ticket,LABEL,confirmed=True).revision==1


@pytest.mark.parametrize('condition',['changed','conflict','failure'])
def test_terminal_safe_failure_counters_and_no_private_error_text(engine,monkeypatch,condition):
    cohort(engine,unanalyzed=True)
    from family_os.audit_services import EvaluationRevisionConflictError
    def fail(*args,**kwargs):
        if condition=='changed': raise services.ReviewChangedError()
        if condition=='conflict': raise EvaluationRevisionConflictError()
        raise AnalysisPersistenceError()
    monkeypatch.setattr(terminal,'save_review',fail)
    summary,output=run(engine,'l\n3\nunknown\n3\nsave\n')
    assert summary['changed_source' if condition=='changed' else 'failed']==1
    assert summary['labeled']==0
    assert 'PRIVATE' not in output.split('Session summary: ')[1]
    assert not rows(engine,source_analysis)


def test_no_transactions_during_human_prompts_or_inference_and_no_secret_reads(engine,monkeypatch):
    cohort(engine,unanalyzed=True)
    from family_os.metadata_classifier import MetadataRulesAnalyzer
    from family_os import gmail_auth, outlook_auth, google_calendar_auth, google_drive_auth
    import keyring
    for module in (gmail_auth,outlook_auth,google_calendar_auth,google_drive_auth):
        monkeypatch.setattr(module,'load_client',lambda *args,**kwargs:pytest.fail('provider client'))
    monkeypatch.setattr(keyring,'get_password',lambda *args,**kwargs:pytest.fail('keyring'))
    analyze=MetadataRulesAnalyzer.analyze
    def checked(self,input,policy):
        assert engine.pool.checkedout()==0
        return analyze(self,input,policy)
    monkeypatch.setattr(MetadataRulesAnalyzer,'analyze',checked)
    class Checked(TTY):
        def readline(self,*args):
            assert engine.pool.checkedout()==0
            return super().readline(*args)
    statements=[]
    def guard(conn,cursor,statement,params,context,many):
        statements.append(statement)
        assert 'raw_source_record.payload' not in statement
        assert 'source_account.metadata' not in statement and 'external_account' not in statement
        assert 'source_sync_state' not in statement
    event.listen(engine,'before_cursor_execute',guard)
    try:
        result=terminal.run_review(engine,'home',input_stream=Checked('l\n3\nunknown\n3\nsave\n'),output_stream=TTY(),**OPTIONS)
    finally: event.remove(engine,'before_cursor_execute',guard)
    assert result['labeled']==1 and statements


def test_service_suppresses_display_metadata_repr_and_bounds(engine):
    analysis=cohort(engine,subject='PRIVATE SUBJECT')
    with engine.begin() as connection:
        connection.execute(update(source_record).where(source_record.c.id==analysis.source_record_id).values(
            sender='S'*321,subject='X'*8193,raw_metadata={'status':'X'*257,'removed':True,'unexpected':'PRIVATE'}))
    item=select(engine).items[0]
    assert item.subject is None and item.sender is None
    assert item.display_metadata=={'removed':True}
    assert 'PRIVATE' not in repr(item)


def test_cross_household_ticket_never_labels_or_inserts(engine):
    from family_os.schema import household
    cohort(engine,unanalyzed=True)
    ticket=select(engine).items[0].ticket
    with engine.begin() as connection: connection.execute(household.insert().values(id='other',name='Synthetic'))
    assert not services.select_review(engine,'other',**OPTIONS).items
    with pytest.raises(services.ReviewChangedError): services.save_review(engine,replace(ticket,household_id='other'),LABEL,confirmed=True)
    assert not rows(engine,source_analysis)


def test_terminal_cli_runs_one_local_command_and_summary_has_no_content(engine,monkeypatch,capsys):
    cohort(engine)
    output=TTY()
    monkeypatch.setattr(terminal.sys,'stdin',TTY('s\n'))
    monkeypatch.setattr(terminal.sys,'stdout',output)
    monkeypatch.setattr('family_os.cli.create_db',lambda _:engine)
    assert main(['metadata-review','--household','home','--since','2026-01-01','--until','2027-01-01','--limit','1'])==0
    summary=json.loads(output.getvalue().split('Session summary: ')[1])
    assert summary['skipped']==1 and 'PRIVATE' not in json.dumps(summary)


def test_redirected_stdout_is_refused_before_selection(engine,monkeypatch):
    monkeypatch.setattr(terminal,'select_review',lambda *args,**kwargs:pytest.fail('selected private records'))
    with pytest.raises(terminal.ReviewTerminalError):
        terminal.run_review(engine,'home',input_stream=TTY('s\n'),output_stream=StringIO(),**OPTIONS)


def test_definition_change_while_waiting_for_final_lock_rolls_back_analysis(engine,tmp_path,monkeypatch):
    import yaml
    cohort(engine,unanalyzed=True)
    path=tmp_path/'rules.yaml'
    path.write_text((ROOT/'config/metadata-classifier.yaml').read_text())
    ticket=select(engine,rules_path=path).items[0].ticket
    persist=services._persist_analysis
    def changing(*args):
        result=persist(*args)
        data=yaml.safe_load(path.read_text());data['ruleset_version']='changed-after-persist'
        path.write_text(yaml.safe_dump(data))
        return result
    monkeypatch.setattr(services,'_persist_analysis',changing)
    with pytest.raises(services.ReviewChangedError): services.save_review(engine,ticket,LABEL,confirmed=True,rules_path=path)
    assert not rows(engine,source_analysis) and not rows(engine,analysis_evaluation_label)


def test_source_lock_covers_analysis_to_label_gap_against_external_writer(engine,monkeypatch):
    from threading import Event
    cohort(engine,unanalyzed=True)
    ticket=select(engine).items[0].ticket
    started=Event()
    append=services._append_label
    futures=[]
    # The source row/writer reservation must remain held through label insertion.
    # Writer may finish only after the confirmed transaction releases its lock.
    with ThreadPoolExecutor(max_workers=1) as pool:
        def writer():
            started.set()
            change_snapshot(engine,ticket.source_record_id)
        def concurrent(*args):
            futures.append(pool.submit(writer))
            assert started.wait(10)
            assert not futures[0].done()
            return append(*args)
        monkeypatch.setattr(services,'_append_label',concurrent)
        revision=services.save_review(engine,ticket,LABEL,confirmed=True)
        futures[0].result(timeout=15)
    analysis=next(row for row in rows(engine,source_analysis) if row['id']==revision.analysis_id)
    assert analysis['raw_record_id']==ticket.raw_record_id
    current=rows(engine,source_record)[0]
    assert current['raw_record_id']!=ticket.raw_record_id
    assert len(rows(engine,analysis_evaluation_label))==1
    assert audit_metrics(engine,'home')['eligible_count']==0


def test_interrupt_while_printing_saved_message_keeps_committed_label_statistics(engine):
    cohort(engine,unanalyzed=True)
    class InterruptedOutput(TTY):
        def write(self,value):
            if value.startswith('Saved an append-only'): raise KeyboardInterrupt()
            return super().write(value)
    output=InterruptedOutput()
    summary=terminal.run_review(engine,'home',input_stream=TTY('l\n3\nunknown\n3\nsave\n'),output_stream=output,**OPTIONS)
    assert summary['labeled']==1 and summary['aborted']==0
    assert len(rows(engine,source_analysis))==len(rows(engine,analysis_evaluation_label))==1
