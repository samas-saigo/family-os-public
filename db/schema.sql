-- Family OS starter schema (PostgreSQL-style)

create table household (
  id text primary key,
  name text not null
);

create table person (
  id text primary key,
  household_id text not null references household(id),
  display_name text not null,
  metadata jsonb not null default '{}'::jsonb
);

create table source_account (
  id text primary key,
  household_id text not null references household(id),
  provider text not null,
  owner_type text not null check (owner_type in ('person','household','unknown')),
  owner_id text,
  external_account text,
  enabled boolean not null default true,
  metadata jsonb not null default '{}'::jsonb
);

create table source_record (
  id text primary key,
  household_id text not null references household(id),
  source_account_id text not null references source_account(id),
  provider_object_id text not null,
  record_type text not null,
  provider_thread_id text,
  occurred_at timestamptz,
  subject text,
  sender text,
  recipients jsonb,
  content_hash text,
  raw_metadata jsonb not null default '{}'::jsonb,
  ingested_at timestamptz not null default now(),
  unique(source_account_id, provider_object_id)
);

create index idx_source_record_hash
  on source_record(household_id, content_hash);

create table canonical_entity (
  id text primary key,
  household_id text not null references household(id),
  entity_type text not null,
  canonical_key text,
  status text not null default 'active',
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table entity_source_link (
  entity_id text not null references canonical_entity(id),
  source_record_id text not null references source_record(id),
  match_type text not null,
  confidence numeric,
  primary key(entity_id, source_record_id)
);

create table extracted_fact (
  id text primary key,
  entity_id text references canonical_entity(id),
  source_record_id text not null references source_record(id),
  fact_name text not null,
  fact_value jsonb not null,
  confidence numeric,
  extractor_version text,
  created_at timestamptz not null default now()
);

create table task (
  id text primary key,
  household_id text not null references household(id),
  title text not null,
  status text not null default 'open',
  due_at timestamptz,
  priority text,
  related_entity_id text references canonical_entity(id),
  source_record_id text references source_record(id),
  action_policy text,
  metadata jsonb not null default '{}'::jsonb
);

create table review_queue (
  id text primary key,
  household_id text not null references household(id),
  review_type text not null,
  source_record_id text references source_record(id),
  entity_id text references canonical_entity(id),
  reason text not null,
  proposed_data jsonb,
  confidence numeric,
  status text not null default 'open',
  created_at timestamptz not null default now()
);

create table relationship (
  id text primary key,
  household_id text not null references household(id),
  subject_type text not null,
  subject_id text not null,
  predicate text not null,
  object_type text not null,
  object_id text not null,
  metadata jsonb not null default '{}'::jsonb
);
