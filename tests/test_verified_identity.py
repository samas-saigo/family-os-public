"""New fictional signed assertions; disposable DBs, no IDP/provider/data access."""
import ast
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from time import time

from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import jwt
import pytest
from sqlalchemy import event, insert, select, update, inspect
from sqlalchemy.exc import IntegrityError

from family_os import _verified_identity as v
from family_os.schema import (external_identity_binding as binding, household, person,
    household_membership as membership, source_read_grant, authorization_audit)

ROOT = Path(__file__).parents[1]
ISSUER = 'https://identity.example.invalid/tenant'
AUDIENCE = 'fictional-family-client'
HOME = 'wren-household'


@pytest.fixture(scope='module')
def keys():
    return tuple(rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2))


def pem(key):
    return key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)


def future_claim(field):
    # Collection creates a factory, not a timestamp that can age into validity.
    return lambda now: {field: now + 600}


@pytest.fixture
def verifier(keys):
    return v.OfflineIdentityVerifier(issuer=ISSUER, audience=AUDIENCE, public_keys={'key-one': pem(keys[0])})


def signed(verifier, keys, *, changes=None, headers=None, key=0, raw=None):
    challenge = verifier.challenge()
    now = int(time())
    claims = dict(iss=ISSUER, sub='fictional-wren-one', aud=AUDIENCE, iat=now-1,
                  nbf=now-1, exp=now+120, nonce=challenge.nonce)
    claims.update(changes(now) if callable(changes) else (changes or {}))
    header = dict(typ='JWT', kid='key-one'); header.update(headers or {})
    token = (jwt.encode(claims, keys[key], algorithm='RS256', headers=header) if raw is None else
             jwt.PyJWS().encode(raw(challenge), keys[key], algorithm='RS256', headers=header))
    return token, challenge


def proof(verifier, keys, **kwargs):
    token, challenge = signed(verifier, keys, **kwargs)
    return verifier.verify(token, challenge)


def test_valid_signed_identity_uses_exact_profile_and_minimized_result(verifier, keys):
    p = proof(verifier, keys, changes={'email': 'fictional-ignored@example.invalid', 'name': 'Ignored'})
    assert p.issuer == ISSUER and p.subject == 'fictional-wren-one'
    assert set(vars(p)) == {'issuer', 'subject', 'expires_at'}
    assert repr(p) == '<VerifiedIdentity>'
    assert 'fictional-wren' not in repr(p)


@pytest.mark.parametrize('change', [
    {'iss':'https://other.example.invalid'}, {'iss':ISSUER+'/'},
    {'aud':'another-client'}, {'aud':[AUDIENCE]}, {'azp':'other-client'},
    {'sub':''}, {'sub':7}, {'sub':'x'*256}, {'sub':'two identities'},
    {'exp':0}, lambda now: {'exp':now+999999},
    pytest.param(future_claim('iat'), id='future-iat'),
    pytest.param(future_claim('nbf'), id='future-nbf'),
    {'iat':True}, lambda now: {'exp':float(now+120)},
    lambda now: {'nbf':str(now-1)}, {'nonce':'caller-replacement'},
])
def test_wrong_or_malformed_claims_fail_closed(verifier, keys, change):
    token, challenge = signed(verifier, keys, changes=change)
    with pytest.raises(v.IdentityError, match='^Identity verification unavailable$'):
        verifier.verify(token, challenge)


@pytest.mark.parametrize('field', ['iat', 'nbf'])
@pytest.mark.parametrize('collection_delay', [0, 601, 3600])
def test_future_claim_rejection_is_independent_of_collection_delay(verifier, keys, monkeypatch, field, collection_delay):
    clock = [2000000000]
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromtimestamp(clock[0], tz=tz)
    # Freeze signing, challenge/profile and PyJWT clocks together, without sleeping.
    monkeypatch.setitem(globals(), 'time', lambda: clock[0])
    monkeypatch.setattr(v, 'time', lambda: clock[0])
    monkeypatch.setattr(jwt.api_jwt, 'datetime', FrozenDatetime)
    change = future_claim(field)  # The same factory used by the collected cases.
    clock[0] += collection_delay
    token, challenge = signed(verifier, keys, changes=change)
    claims = jwt.decode(token, options={'verify_signature':False})
    assert claims[field] == clock[0] + 600
    assert proof(verifier, keys).subject == 'fictional-wren-one'  # Valid control.
    with pytest.raises(v.IdentityError, match='^Identity verification unavailable$'):
        verifier.verify(token, challenge)


@pytest.mark.parametrize('field', ['iss','sub','aud','exp','iat','nbf','nonce'])
def test_missing_required_claims_fail_closed(verifier, keys, field):
    token, c = signed(verifier, keys)
    claims = jwt.decode(token, options={'verify_signature':False}); claims.pop(field)
    token = jwt.encode(claims, keys[0], algorithm='RS256', headers={'kid':'key-one'})
    with pytest.raises(v.IdentityError): verifier.verify(token,c)


@pytest.mark.parametrize('headers', [{'typ':'at+jwt'}, {'kid':'missing'}, {'jku':'https://attacker.invalid'},
    {'jwk':{'kty':'RSA'}}, {'crit':['anything']}, {'kid':''}])
def test_untrusted_token_type_key_and_jose_fields_rejected(verifier, keys, headers):
    token,c=signed(verifier,keys,headers=headers)
    with pytest.raises(v.IdentityError): verifier.verify(token,c)


def test_wrong_key_unsigned_and_hmac_substitution_rejected(verifier, keys):
    token,c=signed(verifier,keys,key=1)
    with pytest.raises(v.IdentityError):verifier.verify(token,c)
    claims=jwt.decode(token,options={'verify_signature':False})
    for alg,key in [('none',None),('HS256',b'fictional-secret'*4),('RS512',keys[0])]:
        alternate=jwt.encode(claims,key,algorithm=alg,headers={'kid':'key-one'})
        with pytest.raises(v.IdentityError):verifier.verify(alternate,c)


@pytest.mark.parametrize('token', [None, b'bytes', '', 'not.jwt', 'x'*16385, 'é.jwt.token'])
def test_malformed_and_oversized_tokens_never_expose_private_errors(verifier, token, caplog):
    with pytest.raises(v.IdentityError) as caught:verifier.verify(token,verifier.challenge())
    assert str(caught.value)=='Identity verification unavailable'
    assert not caplog.text


def test_nonce_replay_wrong_receipt_and_cross_verifier_rejected(verifier, keys):
    token,c=signed(verifier,keys)
    other=verifier.challenge()
    with pytest.raises(v.IdentityError):verifier.verify(token,other)
    with pytest.raises(v.IdentityError):verifier.verify(token,replace(c))
    p=verifier.verify(token,c)
    with pytest.raises(v.IdentityError):verifier.verify(token,c)
    replacement=v.OfflineIdentityVerifier(issuer=ISSUER,audience=AUDIENCE,public_keys={'key-one':pem(keys[0])})
    with pytest.raises(v.IdentityError):replacement._current(p)
    with pytest.raises(v.IdentityError):verifier._current(replace(p))
    assert repr(c)=='<IdentityChallenge>'


def test_expired_challenge_and_proof_are_not_leases(verifier, keys, monkeypatch):
    token,c=signed(verifier,keys)
    with monkeypatch.context() as m:
        m.setattr(v,'time',lambda:c.expires_at+1)
        with pytest.raises(v.IdentityError):verifier.verify(token,c)
    p=verifier.verify(token,c)
    monkeypatch.setattr(v,'time',lambda:p.expires_at)
    with pytest.raises(v.IdentityError):verifier._current(p)


@pytest.mark.parametrize('part',['payload','header'])
def test_duplicate_json_identity_or_header_names_rejected(verifier, keys, part):
    token,c=signed(verifier,keys)
    if part=='payload':
        claims=jwt.decode(token,options={'verify_signature':False})
        raw=json.dumps(claims)[:-1]+',"sub":"fictional-wren-two"}'
        token=jwt.PyJWS().encode(raw.encode(),keys[0],algorithm='RS256',headers={'kid':'key-one'})
    else:
        # PyJWT owns decoding; a signed duplicate header tests the extension hook.
        from jwt.utils import base64url_encode
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        payload=token.split('.')[1].encode()
        h=base64url_encode(b'{"alg":"RS256","typ":"JWT","kid":"missing","kid":"key-one"}')
        content=h+b'.'+payload
        sig=keys[0].sign(content,padding.PKCS1v15(),hashes.SHA256())
        token=(content+b'.'+base64url_encode(sig)).decode()
    with pytest.raises(v.IdentityError):verifier.verify(token,c)


def test_trusted_rotation_accepts_only_explicit_keys_and_old_handles_do_not_transfer(verifier, keys):
    p=proof(verifier,keys)
    rotated=v.OfflineIdentityVerifier(issuer=ISSUER,audience=AUDIENCE,
        public_keys={'key-one':pem(keys[0]),'key-two':pem(keys[1])})
    assert proof(rotated,keys,key=1,headers={'kid':'key-two'}).subject==p.subject
    removed=v.OfflineIdentityVerifier(issuer=ISSUER,audience=AUDIENCE,public_keys={'key-two':pem(keys[1])})
    token,c=signed(removed,keys)
    with pytest.raises(v.IdentityError):removed.verify(token,c)
    with pytest.raises(v.IdentityError):removed._current(p)


@pytest.mark.parametrize('config',[{'issuer':'http://identity.example.invalid'}, {'issuer':'https://user@identity.example.invalid'},
    {'issuer':ISSUER+'?override=1'}, {'audience':''}, {'public_keys':{}}, {'public_keys':{'key':b'invalid-pem'}}])
def test_bad_trust_configuration_is_safe(keys, config):
    kwargs=dict(issuer=ISSUER,audience=AUDIENCE,public_keys={'key-one':pem(keys[0])});kwargs.update(config)
    with pytest.raises(v.IdentityError):v.OfflineIdentityVerifier(**kwargs)


def seed(engine):
    with engine.begin() as c:
        c.execute(insert(household),[dict(id=HOME,name='Fictional Wren'),dict(id='elm-household',name='Fictional Elm')])
        c.execute(insert(person),[dict(id='ada',household_id=HOME,display_name='Fictional Ada',metadata={}),
            dict(id='ben',household_id=HOME,display_name='Fictional Ben',metadata={}),
            dict(id='cy',household_id='elm-household',display_name='Fictional Cy',metadata={})])
        c.execute(insert(membership),[dict(household_id=HOME,person_id=p,state='allowed',revision=1) for p in ('ada','ben')])
        c.execute(insert(binding),[dict(issuer=ISSUER,subject=s,household_id=HOME,person_id=p,state='allowed',revision=1)
            for s,p in [('fictional-wren-one','ada'),('fictional-wren-two','ben')]])


def test_verified_subject_resolves_existing_person_not_email_or_client_person(engine, verifier, keys):
    seed(engine);resolver=v.IdentityBindingResolver(engine,verifier,synthetic_only=True)
    one=proof(verifier,keys,changes={'email':'ben@example.invalid','person_id':'ben','household_id':'elm-household'})
    two=proof(verifier,keys,changes={'sub':'fictional-wren-two','email':'ada@example.invalid'})
    assert resolver.resolve(one,HOME)==v.ResolvedMember(HOME,'ada',1,1)
    assert resolver.resolve(two,HOME)==v.ResolvedMember(HOME,'ben',1,1)
    for bad in [replace(one),v.VerifiedIdentity(ISSUER,'fictional-wren-two',int(time())+120),None]:
        with pytest.raises(v.IdentityError):resolver.resolve(bad,HOME)
    assert not hasattr(resolver,'harness_context')
    assert not hasattr(resolver.resolve(one,HOME),'manage_membership')


def test_unbound_cross_household_and_revoked_bindings_have_identical_denial(engine, verifier, keys):
    seed(engine);r=v.IdentityBindingResolver(engine,verifier,synthetic_only=True);p=proof(verifier,keys)
    with pytest.raises(v.IdentityError):r.resolve(p,'elm-household')
    with pytest.raises(v.IdentityError):r.resolve(proof(verifier,keys,changes={'sub':'unbound'}),HOME)
    with engine.begin() as c:c.execute(update(binding).where(binding.c.person_id=='ada').values(state='revoked',revision=2))
    with pytest.raises(v.IdentityError):r.resolve(p,HOME)


def test_current_membership_revocation_and_reenrollment_never_grant_access(engine, verifier, keys):
    seed(engine);r=v.IdentityBindingResolver(engine,verifier,synthetic_only=True);p=proof(verifier,keys)
    assert r.resolve(p,HOME).membership_revision==1
    with engine.begin() as c:c.execute(update(membership).where(membership.c.person_id=='ada').values(state='revoked',revision=2))
    with pytest.raises(v.IdentityError):r.resolve(p,HOME)
    with engine.begin() as c:c.execute(update(membership).where(membership.c.person_id=='ada').values(state='allowed',revision=3))
    assert r.resolve(p,HOME).membership_revision==3
    # No source, publication or management capability is provisioned by identity resolution.
    with engine.connect() as c:
        assert c.execute(select(source_read_grant)).all()==[]
        assert c.execute(select(authorization_audit)).all()==[]


def test_multiple_bindings_require_separate_setup_not_email_auto_linking(engine, verifier, keys):
    seed(engine)
    with engine.begin() as c:c.execute(insert(binding).values(issuer=ISSUER,subject='separately-linked',
        household_id=HOME,person_id='ada',state='allowed',revision=1))
    r=v.IdentityBindingResolver(engine,verifier,synthetic_only=True)
    assert r.resolve(proof(verifier,keys,changes={'sub':'separately-linked'}),HOME).person_id=='ada'
    with pytest.raises(v.IdentityError):r.resolve(proof(verifier,keys,changes={'sub':'not-linked','email':'ada@example.invalid'}),HOME)


@pytest.mark.parametrize('bad',[
    {'subject':'fictional-wren-one','person_id':'ben'},
    {'subject':'new-sub','person_id':'cy'},
    {'subject':'new-sub','revision':0},
    {'subject':'new-sub','state':'unknown'},
    {'subject':'','person_id':'ada'},
])
def test_db_uniqueness_and_tenancy_reject_conflicting_bindings(engine, bad):
    seed(engine);row=dict(issuer=ISSUER,subject='fresh-sub',household_id=HOME,person_id='ada',state='allowed',revision=1);row.update(bad)
    with pytest.raises(IntegrityError):
        with engine.begin() as c:c.execute(insert(binding).values(**row))
    with engine.connect() as c:assert len(c.execute(select(binding)).all())==2


def test_ambiguous_binding_query_fails_closed(engine, verifier, keys, monkeypatch):
    seed(engine);r=v.IdentityBindingResolver(engine,verifier,synthetic_only=True);p=proof(verifier,keys)
    # PK prevents this normally; defense-in-depth exercises an inconsistent repository result.
    original=engine.connect
    class BadConnection:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,*args):return self
        def mappings(self):return self
        def all(self):return [dict(person_id='ada'),dict(person_id='ben')]
    monkeypatch.setattr(engine,'connect',BadConnection)
    with pytest.raises(v.IdentityError):r.resolve(p,HOME)
    monkeypatch.setattr(engine,'connect',original)


def test_database_unavailable_error_and_logs_contain_no_token_or_driver_text(engine, verifier, keys, monkeypatch, caplog):
    seed(engine);r=v.IdentityBindingResolver(engine,verifier,synthetic_only=True);p=proof(verifier,keys)
    def fail():raise RuntimeError('fictional-private-driver-token')
    monkeypatch.setattr(engine,'connect',fail)
    with pytest.raises(v.IdentityError) as caught:r.resolve(p,HOME)
    assert str(caught.value)=='Identity verification unavailable' and caplog.text==''
    assert 'fictional-private' not in repr(caught.value)


def test_identity_seam_never_reads_providers_grants_or_secrets(engine, verifier, keys, monkeypatch):
    seed(engine);r=v.IdentityBindingResolver(engine,verifier,synthetic_only=True)
    def inspect_query(c,cursor,sql,parameters,ctx,many):
        assert not any(name in sql for name in ('source_account','raw_source_record','source_record',
             'source_sync_state','source_read_grant','publication_read_grant','authorization_audit'))
    event.listen(engine,'before_cursor_execute',inspect_query)
    try:
        monkeypatch.setattr('socket.socket',lambda *a,**k:pytest.fail('network forbidden'))
        p=proof(verifier,keys)
        assert r.resolve(p,HOME).person_id=='ada'
    finally:event.remove(engine,'before_cursor_execute',inspect_query)
    path=ROOT/'src/family_os/_verified_identity.py';tree=ast.parse(path.read_text())
    imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    imports|={x.name for n in ast.walk(tree) if isinstance(n,ast.Import) for x in n.names}
    assert imports <= {'dataclasses','json','secrets','threading','time','urllib.parse','jwt',
         'cryptography.hazmat.primitives.serialization','cryptography.hazmat.primitives.asymmetric.rsa',
         'sqlalchemy','family_os.schema'}
    for other in (ROOT/'src').rglob('*.py'):
        if other not in (path, ROOT/'src/family_os/_household_sessions.py', ROOT/'src/family_os/_oidc_login.py'):assert '_verified_identity' not in other.read_text()


def test_identity_migration_roundtrip_preserves_existing_authorization(engine):
    seed(engine)
    with engine.connect() as c:
        before=tuple(dict(x) for x in c.execute(select(membership)).mappings())
        persons=tuple(dict(x) for x in c.execute(select(person)).mappings())
    config=Config(str(ROOT/'alembic.ini'));command.check(config)
    command.downgrade(config,'4e82a1c70d39')
    assert 'external_identity_binding' not in inspect(engine).get_table_names()
    command.upgrade(config,'head');command.check(config)
    with engine.connect() as c:
        assert c.execute(select(binding)).all()==[]
        assert tuple(dict(x) for x in c.execute(select(membership)).mappings())==before
        assert tuple(dict(x) for x in c.execute(select(person)).mappings())==persons


def test_reenrollment_cannot_revive_existing_source_grant(engine, verifier, keys):
    from family_os.schema import source_account
    seed(engine)
    with engine.begin() as c:
        c.execute(insert(source_account).values(id='fictional-ada-mail',household_id=HOME,
            provider='fixture',owner_type='person',owner_id='ada',person_owner_id='ada',
            external_account=None,enabled=True,metadata={}))
        c.execute(insert(source_read_grant).values(household_id=HOME,source_account_id='fictional-ada-mail',
            person_id='ada',state='allowed',observations=True,security=True,revision=1,membership_revision=1))
    r=v.IdentityBindingResolver(engine,verifier,synthetic_only=True);p=proof(verifier,keys)
    assert r.resolve(p,HOME).membership_revision==1
    with engine.begin() as c:c.execute(update(membership).where(membership.c.person_id=='ada').values(state='revoked',revision=2))
    with pytest.raises(v.IdentityError):r.resolve(p,HOME)
    with engine.begin() as c:c.execute(update(membership).where(membership.c.person_id=='ada').values(state='allowed',revision=3))
    current=r.resolve(p,HOME)
    with engine.connect() as c:
        grant=c.execute(select(source_read_grant)).mappings().one()
        assert grant['revision']==1 and grant['membership_revision']==1
        effective=c.execute(select(source_read_grant).where(source_read_grant.c.state=='allowed',
            source_read_grant.c.membership_revision==current.membership_revision)).all()
        assert effective==[]  # Same G2a epoch contract, never automatically renewed by identity.


def test_unknown_membership_is_not_enrolled_by_valid_identity(engine, verifier, keys):
    seed(engine)
    with engine.begin() as c:c.execute(insert(binding).values(issuer=ISSUER,subject='fictional-elm',
        household_id='elm-household',person_id='cy',state='allowed',revision=1))
    r=v.IdentityBindingResolver(engine,verifier,synthetic_only=True)
    with pytest.raises(v.IdentityError):r.resolve(proof(verifier,keys,changes={'sub':'fictional-elm'}),'elm-household')
    with engine.connect() as c:assert len(c.execute(select(membership)).all())==2


def test_nonce_and_proof_caps_are_bounded_and_no_real_session_is_created(verifier, keys):
    receipts=[verifier.challenge() for _ in range(32)]
    with pytest.raises(v.IdentityError):verifier.challenge()
    # Use one valid token per issued receipt, all within the short offline profile.
    for c in receipts:
        now=int(time())
        token=jwt.encode(dict(iss=ISSUER,sub='fictional-sub',aud=AUDIENCE,iat=now-1,nbf=now-1,
             exp=now+120,nonce=c.nonce),keys[0],algorithm='RS256',headers={'kid':'key-one'})
        verifier.verify(token,c)
    token,c=signed(verifier,keys)
    with pytest.raises(v.IdentityError):verifier.verify(token,c)


def test_missing_header_and_tampered_signed_payload_rejected(verifier, keys):
    token,c=signed(verifier,keys)
    claims=jwt.decode(token,options={'verify_signature':False})
    missing=jwt.encode(claims,keys[0],algorithm='RS256')
    with pytest.raises(v.IdentityError):verifier.verify(missing,c)
    from jwt.utils import base64url_encode
    claims['sub']='fictional-wren-two'
    header,_,signature=token.split('.')
    tampered=header+'.'+base64url_encode(json.dumps(claims).encode()).decode()+'.'+signature
    with pytest.raises(v.IdentityError):verifier.verify(tampered,c)


def test_exact_subject_case_does_not_alias_existing_person(engine, verifier, keys):
    seed(engine);r=v.IdentityBindingResolver(engine,verifier,synthetic_only=True)
    with pytest.raises(v.IdentityError):r.resolve(proof(verifier,keys,changes={'sub':'Fictional-wren-one'}),HOME)


def test_required_identity_dependency_is_explicit_and_existing_lock_is_used():
    import tomllib
    project=tomllib.loads((ROOT/'pyproject.toml').read_text())
    assert project['project']['optional-dependencies']['identity']==[
        'PyJWT[crypto]>=2.15.1,<3','cryptography>=50.0.2,<51']
    locked=(ROOT/'requirements-dev.lock').read_text()
    assert 'PyJWT==2.15.1' in locked and 'cryptography==50.0.2' in locked


@pytest.mark.parametrize('flag',[False,1,'true'])
def test_binding_resolver_requires_exact_synthetic_opt_in(engine, verifier, flag):
    with pytest.raises(v.IdentityError):v.IdentityBindingResolver(engine,verifier,synthetic_only=flag)


def test_nonfinite_json_and_invalid_time_chronology_rejected(verifier, keys):
    for changes in [{'unused':float('nan')}, {'unused':float('inf')},
                    {'iat':int(time())-600,'nbf':int(time())-600,'exp':int(time())+120},
                    {'nbf':int(time())-120}]:
        token,c=signed(verifier,keys,changes=changes)
        with pytest.raises(v.IdentityError):verifier.verify(token,c)


def test_private_weak_and_nonrsa_trusted_keys_rejected(keys):
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import PrivateFormat, NoEncryption
    private=keys[0].private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption())
    weak=pem(rsa.generate_private_key(public_exponent=65537,key_size=1024))
    other=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(Encoding.PEM,PublicFormat.SubjectPublicKeyInfo)
    for bad in [private,weak,other]:
        with pytest.raises(v.IdentityError):v.OfflineIdentityVerifier(issuer=ISSUER,audience=AUDIENCE,public_keys={'key-one':bad})
