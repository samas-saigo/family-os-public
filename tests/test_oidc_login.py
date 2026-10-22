"""New fictional Sable identities, direct in-process IDP, disposable DB engines."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import ast
import json
from pathlib import Path
from secrets import token_urlsafe
from threading import Barrier
from time import time
from urllib.parse import parse_qsl, urlsplit, urlencode

from authlib.oauth2.rfc7636 import CodeChallenge
from authlib.oidc.core.util import create_half_hash
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import jwt
import pytest
from sqlalchemy import insert, select, update

from family_os import _oidc_login as o, _household_sessions as s, _household_authorization as a, _verified_identity as v
from family_os.schema import household,person,household_membership as member,external_identity_binding as binding,source_account,source_read_grant as grant,household_session,session_audit,authorization_audit

ROOT=Path(__file__).parents[1]
ISSUER='https://sable-id.example.invalid/issuer';CLIENT='sable-fictional-client';HOME='sable'
CONFIG=o.Configuration(ISSUER,CLIENT,'https://sable-id.example.invalid/authorize','https://sable-id.example.invalid/token','https://sable-client.example.invalid/callback')


class FictionalProvider:
    """Test-only protocol endpoint simulator: no socket/server or real accounts."""
    def __init__(self,key):
        self.key=key;self.codes={};self.calls=[];self.changes={};self.header={};self.reply_transform=None

    def authorize(self,attempt,subject='ivy'):
        params=dict(parse_qsl(urlsplit(attempt.authorization_url).query))
        assert params['client_id']==CLIENT and params['redirect_uri']==CONFIG.redirect_uri
        assert params['scope']=='openid' and params['response_type']=='code' and params['code_challenge_method']=='S256'
        code=token_urlsafe(24);self.codes[code]=(params,subject)
        return CONFIG.redirect_uri+'?'+urlencode({'state':params['state'],'code':code,'iss':ISSUER})

    def exchange(self,uri,form):
        self.calls.append((uri,dict(form)))
        assert uri==CONFIG.token_endpoint
        entry=self.codes.pop(form['code'],None)
        if entry is None:raise RuntimeError('fictional private invalid code')
        params,subject=entry
        if (form['client_id']!=params['client_id'] or form['redirect_uri']!=params['redirect_uri']
                or not CodeChallenge.CODE_CHALLENGE_METHODS['S256'](form['code_verifier'],params['code_challenge'])):
            raise RuntimeError('fictional private PKCE rejection')
        now=int(time());access=token_urlsafe(24)
        claims=dict(iss=ISSUER,sub=subject,aud=CLIENT,iat=now-1,nbf=now-1,exp=now+120,nonce=params['nonce'],
                    at_hash=create_half_hash(access,'RS256').decode())
        claims.update(self.changes)
        token=jwt.encode(claims,self.key,algorithm='RS256',headers={'kid':'sable-key',**self.header})
        body=dict(id_token=token,access_token=access,token_type='Bearer',scope='openid',expires_in=120)
        if self.reply_transform:body=self.reply_transform(body)
        return o.TokenReply(200,json.dumps(body).encode())


@pytest.fixture(scope='module')
def keys():return [rsa.generate_private_key(public_exponent=65537,key_size=2048) for _ in range(2)]


@pytest.fixture
def setup(engine,keys):
    verifier=v.OfflineIdentityVerifier(issuer=ISSUER,audience=CLIENT,public_keys={'sable-key':keys[0].public_key().public_bytes(Encoding.PEM,PublicFormat.SubjectPublicKeyInfo)})
    with engine.begin() as c:
        c.execute(insert(household).values(id=HOME,name='Fictional Sable'))
        c.execute(insert(person),[dict(id=p,household_id=HOME,display_name='Fictional '+p,metadata={}) for p in ['ivy','roan']])
        c.execute(insert(member),[dict(household_id=HOME,person_id=p,state='allowed',revision=1) for p in ['ivy','roan']])
        c.execute(insert(binding),[dict(issuer=ISSUER,subject=p,household_id=HOME,person_id=p,state='allowed',revision=1) for p in ['ivy','roan']])
        c.execute(insert(source_account),[dict(id=x,household_id=HOME,provider='fixture',owner_type='person',owner_id='ivy',person_owner_id='ivy',enabled=True,external_account=None,metadata={}) for x in ['sable-shared','sable-private']])
        c.execute(insert(grant),[dict(household_id=HOME,source_account_id='sable-shared',person_id=p,state='allowed',observations=True,security=True,revision=1,membership_revision=1) for p in ['ivy','roan']])
    repo=a.FixtureRepository(tuple(a.FixtureObservation(src,a.Object.SCHOOL,1,a.Topic.SCHOOL,a.Safety.HIGH_RISK) for src in ['sable-shared','sable-private']),())
    sessions=s.SessionService(engine,verifier,repo,synthetic_only=True)
    provider=FictionalProvider(keys[0]);clock=[100.0]
    flow=o.LoginFlow(CONFIG,verifier,sessions,exchange=provider.exchange,synthetic_only=True,clock=lambda:clock[0])
    return flow,provider,sessions,clock


def login(setup,subject='ivy'):
    flow,idp,_,_=setup;attempt=flow.begin(HOME);callback=idp.authorize(attempt,subject)
    return flow.complete(attempt,callback)


def count(engine,table):
    with engine.connect() as c:return len(c.execute(select(table)).all())


def test_valid_code_pkce_nonce_existing_binding_session_and_authorized_read(setup,engine):
    flow,idp,service,_=setup;result=login(setup)
    assert result.session.outcome is s.Outcome.COMMITTED
    assert service.resolve(result.session.bearer,HOME).person_id=='ivy'
    projection=service.read(result.session.bearer,HOME)
    assert projection.source_count==projection.security_count==1 and projection.publication_count==0
    assert idp.calls[0][1]['grant_type']=='authorization_code'
    assert len(idp.calls[0][1]['code_verifier'])==43
    assert count(engine,session_audit)==1 and count(engine,authorization_audit)==0
    assert not any(hasattr(flow,x) for x in ['harness_context','grant','quarantine','restore','reconcile'])


def test_two_peer_logins_have_distinct_sessions_and_one_shared_view(setup):
    _,_,svc,_=setup;left=login(setup,'ivy');right=login(setup,'roan')
    assert left.session.session_id!=right.session.session_id and left.session.bearer!=right.session.bearer
    assert svc.read(left.session.bearer,HOME)==svc.read(right.session.bearer,HOME)


@pytest.mark.parametrize('change',['missing','different','duplicate','empty','fragment','extra-token','issuer','redirect','same-origin-path','encoded-path'])
def test_callback_rejections_consume_attempt_without_exchange_or_session(setup,engine,change):
    flow,idp,_,_=setup;attempt=flow.begin(HOME);callback=idp.authorize(attempt)
    base,query=callback.split('?');params=dict(parse_qsl(query))
    if change=='missing':params.pop('state')
    elif change=='different':params['state']=token_urlsafe(32)
    elif change=='empty':params['state']=''
    elif change=='extra-token':params['id_token']='untrusted-client-token'
    elif change=='issuer':params['iss']='https://other.example.invalid/issuer'
    if change=='duplicate':callback+='&state='+params['state']
    elif change=='fragment':callback+='#code=other'
    else:callback=base+'?'+urlencode(params)
    if change=='redirect':callback=callback.replace('sable-client','other-client')
    if change=='same-origin-path':callback=callback.replace('/callback','/other')
    if change=='encoded-path':callback=callback.replace('/callback','/%63allback')
    with pytest.raises(o.LoginError,match='^Login unavailable$'):flow.complete(attempt,callback)
    with pytest.raises(o.LoginError):flow.complete(attempt,idp.authorize(attempt))
    assert idp.calls==[] and count(engine,household_session)==0


def test_expired_canceled_copied_cross_flow_and_consumed_receipts_fail_closed(setup):
    flow,idp,svc,clock=setup;attempt=flow.begin(HOME);callback=idp.authorize(attempt)
    with pytest.raises(o.LoginError):flow.complete(replace(attempt),callback)
    other=o.LoginFlow(CONFIG,svc._verifier,svc,exchange=idp.exchange,synthetic_only=True)
    with pytest.raises(o.LoginError):other.complete(attempt,callback)
    flow.cancel(attempt)
    with pytest.raises(o.LoginError):flow.complete(attempt,callback)
    attempt=flow.begin(HOME);callback=idp.authorize(attempt);clock[0]+=300
    with pytest.raises(o.LoginError):flow.complete(attempt,callback)
    clock[0]+=1;attempt=flow.begin(HOME);callback=idp.authorize(attempt);flow.complete(attempt,callback)
    with pytest.raises(o.LoginError):flow.complete(attempt,callback)


def test_wrong_pkce_verifier_is_rejected_by_library_supported_provider(setup,engine):
    flow,idp,_,_=setup;original=flow._exchange
    def tamper(uri,form):return original(uri,{**form,'code_verifier':token_urlsafe(32)})
    flow._exchange=tamper;attempt=flow.begin(HOME)
    with pytest.raises(o.LoginError):flow.complete(attempt,idp.authorize(attempt))
    assert count(engine,household_session)==0


@pytest.mark.parametrize('claims',[
    {'iss':'https://other.example.invalid/issuer'}, {'aud':'mail-resource'}, {'aud':[CLIENT,'mail-resource']},
    {'nonce':'wrong-nonce'}, {'azp':'other-client'}, {'exp':1}, {'iat':1}, {'nbf':None},
    {'at_hash':'wrong-hash'}, {'at_hash':''}, {'at_hash':None}, {'c_hash':'unsupported-profile'}, {'sub':'unbound-subject'},
])
def test_token_claim_substitution_or_unbound_identity_never_issues_session(setup,engine,claims):
    flow,idp,_,_=setup;idp.changes=claims;attempt=flow.begin(HOME)
    try:result=flow.complete(attempt,idp.authorize(attempt))
    except o.LoginError:pass
    else:assert result.session.outcome is s.Outcome.UNAVAILABLE
    assert count(engine,household_session)==count(engine,session_audit)==0


def test_wrong_signing_key_and_untrusted_header_rejected(setup,keys,engine):
    flow,idp,_,_=setup;idp.key=keys[1];attempt=flow.begin(HOME)
    with pytest.raises(o.LoginError):flow.complete(attempt,idp.authorize(attempt))
    idp.key=keys[0];idp.header={'jku':'https://untrusted.example.invalid/key'};attempt=flow.begin(HOME)
    with pytest.raises(o.LoginError):flow.complete(attempt,idp.authorize(attempt))
    assert count(engine,household_session)==0


def test_substituted_code_from_another_attempt_fails_nonce_binding(setup,engine):
    flow,idp,_,_=setup;one=flow.begin(HOME);two=flow.begin(HOME)
    callback=idp.authorize(one);other=dict(parse_qsl(urlsplit(idp.authorize(two,'roan')).query))
    params=dict(parse_qsl(urlsplit(callback).query));params['code']=other['code']
    with pytest.raises(o.LoginError):flow.complete(one,CONFIG.redirect_uri+'?'+urlencode(params))
    assert count(engine,household_session)==0


def test_id_token_substitution_between_exchange_responses_rejects(setup,engine):
    flow,idp,_,_=setup;one=flow.begin(HOME);one_callback=idp.authorize(one)
    # Capture an authentic token for another attempt, not an invented verification proof.
    two=flow.begin(HOME);other=idp.authorize(two);second=flow._attempts[two]
    params=dict(parse_qsl(urlsplit(other).query));response=idp.exchange(CONFIG.token_endpoint,dict(client_id=CLIENT,redirect_uri=CONFIG.redirect_uri,grant_type='authorization_code',code=params['code'],code_verifier=second.verifier))
    replacement=json.loads(response.body)['id_token'];idp.reply_transform=lambda body:{**body,'id_token':replacement}
    with pytest.raises(o.LoginError):flow.complete(one,one_callback)
    assert count(engine,household_session)==0


def test_email_name_and_role_claims_cannot_take_over_peer_or_enroll(setup,engine):
    _,idp,svc,_=setup;idp.changes={'email':'roan@example.invalid','email_verified':False,'name':'Roan','person_id':'roan','roles':['admin'],'household_id':'another'}
    result=login(setup);assert svc.resolve(result.session.bearer,HOME).person_id=='ivy'
    assert count(engine,person)==2 and count(engine,grant)==2 and count(engine,authorization_audit)==0


@pytest.mark.parametrize('table',[binding,member])
def test_revoked_binding_or_membership_between_begin_and_completion_blocks_session(setup,engine,table):
    flow,idp,_,_=setup;attempt=flow.begin(HOME);callback=idp.authorize(attempt)
    with engine.begin() as c:c.execute(update(table).where(table.c.person_id=='ivy').values(state='revoked',revision=2))
    result=flow.complete(attempt,callback);assert result.session.outcome is s.Outcome.UNAVAILABLE
    assert count(engine,household_session)==0


def test_login_without_source_grant_or_wrong_household_never_gains_access(setup,engine):
    flow,idp,svc,_=setup
    with engine.begin() as c:c.execute(update(grant).where(grant.c.person_id=='ivy').values(state='revoked',revision=2))
    result=login(setup);assert result.session.outcome is s.Outcome.COMMITTED
    assert svc.read(result.session.bearer,HOME).source_count==0
    attempt=flow.begin('unknown-household');result=flow.complete(attempt,idp.authorize(attempt));assert result.session.outcome is s.Outcome.UNAVAILABLE


def test_concurrent_duplicate_callback_exactly_one_completes(setup,engine):
    flow,idp,_,_=setup;attempt=flow.begin(HOME);callback=idp.authorize(attempt);barrier=Barrier(2)
    def complete():
        barrier.wait(5)
        try:return flow.complete(attempt,callback).session.outcome
        except o.LoginError:return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:complete(),range(2)))
    assert results.count(s.Outcome.COMMITTED)==1 and results.count('rejected')==1
    assert len(idp.calls)==count(engine,household_session)==count(engine,session_audit)==1


@pytest.mark.parametrize('bad',[o.TokenReply(403,b'private error'),o.TokenReply(200,b'nonjson'),o.TokenReply(200,b'{"id_token":"a","id_token":"b"}'),o.TokenReply(200,b'x'*32769),o.TokenReply(200,b'{"expires_in":NaN}'),None])
def test_malformed_endpoint_response_has_safe_errors_no_logs_or_audit(setup,engine,bad,caplog):
    flow,idp,_,_=setup;flow._exchange=lambda *args:bad;attempt=flow.begin(HOME)
    with pytest.raises(o.LoginError) as error:flow.complete(attempt,idp.authorize(attempt))
    assert str(error.value)=='Login unavailable' and caplog.text==''
    assert count(engine,household_session)==count(engine,session_audit)==0


@pytest.mark.parametrize('change',[{'token_type':'MAC'},{'scope':'openid email'},{'refresh_token':'secret'}, {'expires_in':False},{'id_token':'not-a-jwt'},{'access_token':''}])
def test_unsupported_token_envelopes_fail_closed(setup,engine,change):
    flow,idp,_,_=setup;idp.reply_transform=lambda body:{**body,**change};attempt=flow.begin(HOME)
    with pytest.raises(o.LoginError):flow.complete(attempt,idp.authorize(attempt))
    assert count(engine,household_session)==0


def test_attempt_limits_and_clock_rollback_are_bounded(setup):
    flow,_,_,clock=setup
    receipts=[flow.begin(HOME) for _ in range(o.MAX_ATTEMPTS)]
    with pytest.raises(o.LoginError):flow.begin(HOME)
    assert len(flow._attempts)==16
    clock[0]-=1
    with pytest.raises(o.LoginError):flow.complete(receipts[0],'invalid')


@pytest.mark.parametrize('config',[replace(CONFIG,issuer='https://live-provider.invalid/issuer'),replace(CONFIG,client_id='different'),replace(CONFIG,redirect_uri=CONFIG.redirect_uri+'?override=yes'),replace(CONFIG,token_endpoint='https://other.example.invalid/token'),replace(CONFIG,authorization_endpoint='http://sable-id.example.invalid/authorize')])
def test_exact_fictional_trust_config_rejects_unsupported_endpoints(setup,config):
    _,idp,svc,_=setup
    with pytest.raises(o.LoginError):o.LoginFlow(config,svc._verifier,svc,exchange=idp.exchange,synthetic_only=True)


def test_redacted_values_and_database_never_contain_tokens_or_nonce(setup,engine,caplog):
    flow,idp,_,_=setup;attempt=flow.begin(HOME);pending=flow._attempts[attempt];callback=idp.authorize(attempt);result=flow.complete(attempt,callback)
    assert repr(attempt)=='<LoginAttempt>' and pending.verifier not in repr(pending)
    assert result.session.bearer not in repr(result)
    with engine.connect() as c:data=repr(c.execute(select(household_session)).mappings().all())+repr(c.execute(select(session_audit)).mappings().all())
    for secret in [pending.state,pending.verifier,pending.challenge.nonce,result.session.bearer]:assert secret not in data
    assert caplog.text==''


def test_unknown_database_outcome_is_preserved_without_callback_retry(setup,monkeypatch):
    flow,idp,svc,_=setup
    monkeypatch.setattr(svc,'establish',lambda *args,**kwargs:s.Result(s.Outcome.UNKNOWN,intent_hash='a'*64))
    attempt=flow.begin(HOME);callback=idp.authorize(attempt);result=flow.complete(attempt,callback)
    assert result.session.outcome is s.Outcome.UNKNOWN and result.request_id.startswith('login_')
    with pytest.raises(o.LoginError):flow.complete(attempt,callback)
    assert len(idp.calls)==1


def test_no_network_harness_public_wiring_or_provider_authority(setup,monkeypatch):
    flow,_,svc,_=setup
    monkeypatch.setattr(a.AuthorizationService,'harness_context',lambda *args,**kwargs:pytest.fail('privileged harness handoff'))
    monkeypatch.setattr('socket.socket',lambda *args,**kwargs:pytest.fail('unexpected network listener/call'))
    result=login(setup);assert svc.read(result.session.bearer,HOME).source_count==1
    source=(ROOT/'src/family_os/_oidc_login.py').read_text();tree=ast.parse(source)
    imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}|{x.name for n in ast.walk(tree) if isinstance(n,ast.Import) for x in n.names}
    assert imports <= {'dataclasses','json','math','re','secrets','threading','time','urllib.parse','uuid','authlib.common.urls','authlib.oauth2.client','authlib.oidc.core','jwt','family_os._verified_identity','family_os._household_sessions'}
    for other in (ROOT/'src').rglob('*.py'):
        if other.name!='_oidc_login.py':assert '_oidc_login' not in other.read_text()
    for flag in [False,1,'true']:
        with pytest.raises(o.LoginError):o.LoginFlow(CONFIG,svc._verifier,svc,exchange=lambda *args:None,synthetic_only=flag)


@pytest.mark.parametrize('callback',[None,b'bytes',{},'x'*4097,'https://sable-client.example.invalid/callback?state=bad\n'])
def test_malformed_callback_values_are_generic_and_consumed(setup,callback):
    flow,_,_,_=setup;attempt=flow.begin(HOME)
    with pytest.raises(o.LoginError,match='^Login unavailable$'):flow.complete(attempt,callback)
    assert attempt not in flow._attempts


def test_configuration_change_after_begin_invalidates_exact_attempt(setup,engine):
    flow,idp,_,_=setup;attempt=flow.begin(HOME);callback=idp.authorize(attempt)
    flow._config=replace(CONFIG,redirect_uri='https://sable-client.example.invalid/changed')
    with pytest.raises(o.LoginError):flow.complete(attempt,callback)
    assert idp.calls==[] and count(engine,household_session)==0


def test_transport_failure_does_not_leak_provider_message_or_retry(setup,engine,caplog):
    flow,idp,_,_=setup;attempt=flow.begin(HOME);callback=idp.authorize(attempt)
    def fail(*args):raise RuntimeError('fictional-private-provider-token-and-url')
    flow._exchange=fail
    with pytest.raises(o.LoginError) as caught:flow.complete(attempt,callback)
    assert str(caught.value)=='Login unavailable' and caplog.text==''
    assert count(engine,household_session)==0
    with pytest.raises(o.LoginError):flow.complete(attempt,callback)


@pytest.mark.parametrize('header',[{'typ':'at+jwt'},{'kid':'unknown'},{'crit':['extra']}])
def test_access_token_or_unsupported_jose_header_cannot_substitute_for_id_token(setup,engine,header):
    flow,idp,_,_=setup;idp.header=header;attempt=flow.begin(HOME)
    with pytest.raises(o.LoginError):flow.complete(attempt,idp.authorize(attempt))
    assert count(engine,household_session)==0
