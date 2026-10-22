"""I9 opt-in adapter: fixed endpoint, minimized exact fields, existing session boundary."""
import importlib.util
from pathlib import Path
import sys
import pytest
from sqlalchemy import select, update
from test_i8_workbench import i8, preview, confirm
from test_i7_reviews import i5, i2, t, login, request, val, save, rows
from family_os.schema import (household_task as task, household_pending_item as pending,
    pending_member_right as rights, task_domain_event as events, source_read_grant as sources,
    task_member_grant as grants, household_membership as members)

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('i9_workbench', ROOT/'prototypes/i9-workbench/serve_home.py')
i9=importlib.util.module_from_spec(spec);sys.modules[spec.name]=i9;spec.loader.exec_module(i9)


@pytest.fixture
def lab(engine):
    owner=i2.Lab(engine, synthetic_only=True);producer=i5.initialize(owner);app=i9.Workbench(owner,38199)
    yield app, producer
    app.close();owner.close()


def get(app, jar, **changes):
    options=dict(method='GET',body=b'',CONTENT_TYPE='',HTTP_ACCEPT='application/json');options.update(changes)
    return request(app, '/api/action-home', cookies=jar, **options)


def section(app, jar, key):return val(get(app,jar))['sections'][key]


def snapshot(engine):
    with engine.connect() as c:return [list(c.execute(select(table)).mappings()) for table in (task,pending,rights,events,grants)]


def test_two_peers_minimum_fields_read_only_no_private_state(lab, engine):
    app,producer=lab;a,b=login(app),login(app,'devon')
    pid=producer.process(i5.cases()[0]).pending_id
    before=snapshot(engine)
    for jar in (a,b):
        status,headers,raw=get(app,jar);value=val((status,headers,raw))
        assert value['schema']==i9.SCHEMA and value['synthetic_only'] is True
        assert len(raw)<=16384 and dict(headers)['Cache-Control'].startswith('no-store')
        assert set(value)=={'schema','synthetic_only','member','sections'}
        for name,s in value['sections'].items():
            assert set(s)=={'total','items'} and len(s['items'])==min(3,s['total'])
            for card in s['items']:
                assert set(card)=={'reason','item'}
                assert set(card['item'])==({'id','step','assignee','status','approved_date','revision','can_edit'}
                    if name in ('mine','collaboration') else {'id','revision','step','supported_date','can_accept','can_review','can_resume','reviewed','disposition'})
        assert pid in {c['item']['id'] for c in value['sections']['decisions']['items']}
        for forbidden in ('source_account','rights_revision','fingerprint','personal_reason','secret','binding'):
            assert forbidden not in raw.decode()
    assert before==snapshot(engine)
    save(app,a,pid)
    assert any(c['reason']=='viewed-undecided' for c in section(app,a,'decisions')['items'])
    assert all(c['reason']=='undecided' for c in section(app,b,'decisions')['items'])


def test_i8_not_applicable_resume_and_original_all(lab):
    app,producer=lab;a,b=login(app),login(app,'devon');pid=producer.process(i5.cases()[0]).pending_id
    before=section(app,a,'decisions')['total']
    val(confirm(app,a,val(preview(app,a,pid))))
    assert section(app,a,'decisions')['total']==before-1
    assert pid in {r['id'] for r in rows(app,a,'not-applicable')['items']}
    assert section(app,b,'decisions')['total']==before
    val(confirm(app,a,val(preview(app,a,pid,'resume'))))
    assert section(app,a,'decisions')['total']==before
    assert any(c['item']['id']==pid and c['reason']=='viewed-undecided' for c in section(app,a,'decisions')['items'])


@pytest.mark.parametrize('changes',[
    {'QUERY_STRING':'member=i2-devon'}, {'QUERY_STRING':'limit=20'}, {'QUERY_STRING':'x=1&x=2'},
    {'QUERY_STRING':'%61=1'}, {'HTTP_ORIGIN':'https://outside.invalid'}, {'HTTP_HOST':'outside.invalid'},
    {'HTTP_SEC_FETCH_SITE':'cross-site'}, {'HTTP_X_SAMAS_INTENT':'anything'},
    {'HTTP_ACCEPT':'*/*'}, {'CONTENT_LENGTH':'1'}, {'HTTP_TRANSFER_ENCODING':'chunked'},
    {'HTTP_CONTENT_ENCODING':'gzip'}, {'HTTP_X_PERSON':'i2-devon'}, {'REQUEST_URI':'/api/action-home?'},
])
def test_rejects_noncontract_requests(lab,changes):
    app,_=lab;a=login(app)
    assert get(app,a,**changes)[0]=='400 Bad Request'


def test_no_write_method_and_no_session(lab):
    app,_=lab
    assert get(app,{})[0]=='400 Bad Request'
    a=login(app)
    assert request(app,'/api/action-home',cookies=a)[0]=='400 Bad Request'


def test_i8_does_not_expose_i9_route_or_assets(engine):
    owner=i2.Lab(engine,synthetic_only=True);i5.initialize(owner);app=i8.Workbench(owner,38199)
    try:
        a=login(app)
        assert get(app,a)[0]=='400 Bad Request'
        assert '/home.js' not in app.assets and '/home.css' not in app.assets
    finally:app.close();owner.close()


def test_current_source_task_grants_and_errors_clear_boundary(lab,engine,monkeypatch):
    app,producer=lab;a=login(app);pid=producer.process(i5.cases()[0]).pending_id
    before=section(app,a,'decisions')['total'];mine=section(app,a,'mine')
    with i2.a.authorization_transaction(engine,i2.HOME) as c:
        c.execute(update(sources).where(sources.c.household_id==i2.HOME,sources.c.person_id=='i2-clara',
            sources.c.source_account_id==i5.Source.SHARED.value).values(security=False,revision=sources.c.revision+1))
    assert section(app,a,'decisions')['total']==before-1
    assert section(app,a,'mine')==mine
    with i2.a.authorization_transaction(engine,i2.HOME) as c:
        c.execute(update(grants).where(grants.c.person_id=='i2-clara').values(state='revoked',revision=grants.c.revision+1))
    assert section(app,a,'mine')['total']==0
    def failure(*args):raise RuntimeError('synthetic secret must not escape')
    monkeypatch.setattr(app.tasks,'action_home',failure)
    response=get(app,a);assert response[0]=='400 Bad Request' and b'secret' not in response[2]


def test_new_generation_invalidates_decision_and_no_safety_upgrade(lab):
    from dataclasses import replace
    app,producer=lab;a=login(app);case=i5.cases()[0];pid=producer.process(case).pending_id
    save(app,a,pid,'defer');assert section(app,a,'followup')['total']==1
    producer.process(replace(case,generation=2,safety=i5.r.Safety.UNAVAILABLE))
    assert section(app,a,'followup')['total']==0
    assert all(c['item']['id']!=pid for c in section(app,a,'decisions')['items'])
    producer.process(replace(case,generation=3))
    assert section(app,a,'followup')['total']==0
    assert any(c['item']['id']==pid and c['reason']=='undecided' for c in section(app,a,'decisions')['items'])


def test_node_contract_and_opt_in_only():
    import subprocess
    result=subprocess.run(['node','tests/browser/i9-contract.test.js'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    result=subprocess.run(['node','tests/browser/i9-action-home.js'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert result.returncode!=0 and 'Exact synthetic opt-in required' in result.stderr


def test_assets_reuse_connected_renderer_without_fixture_payload(lab):
    app,_=lab
    html=app.assets['/'][0]
    assert b'data-i9="true"' in html and b'/home.js' in html
    assert b'/workbench.js' in html and b'/editing.js' in html and b'/personal.js' in html
    assert app.assets['/home.css'][0].decode().count('html[data-i9]')>15
    assert 'fixtures' not in app.assets['/home.js'][0].decode()
    renderer=app.assets['/workbench.js'][0].decode()
    assert "document.documentElement.dataset.i9==='true'" in renderer
    assert "if(!globalThis.SamasActionHome)throw Error('contract')" in renderer


def test_revoked_session_cannot_consume_prepared_home(lab):
    app,_=lab;a=login(app)
    assert get(app,a)[0]=='200 OK'
    assert request(app,'/api/logout',cookies=a)[0]=='200 OK'
    assert get(app,a)[0]=='400 Bad Request'
