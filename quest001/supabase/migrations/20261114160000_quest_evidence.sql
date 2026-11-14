-- QUEST seal-drop + append-only chronicle (QUEST-001-SPEC.md §5, §8).
-- Public read; writes ONLY via quest_append_seal()/quest_register_manifest(),
-- executable by service_role (the quest-evidence edge function) alone.
-- Nothing here moves HHC.

create table if not exists public.quest_manifests (
  quest_id        text primary key,
  version         int  not null,
  manifest_text   text not null,              -- exact served bytes (UTF-8)
  manifest        jsonb not null,
  manifest_sha256 text not null check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  valid_from      timestamptz not null,
  deadline        timestamptz not null,
  is_test         boolean not null default false,
  registered_at   timestamptz not null default now()
);

create table if not exists public.quest_seals (
  id                bigint generated always as identity primary key,
  quest_id          text not null references public.quest_manifests(quest_id),
  request_id        text not null,
  nonce             text not null check (nonce ~ '^[0-9a-f]{64}$'),
  key_id            text not null check (key_id ~ '^[0-9a-f]{64}$'),
  pubkey            text not null check (pubkey ~ '^[0-9a-f]{64}$'),
  operator          text not null,
  operator_norm     text not null,
  failure_mode      text not null,
  failure_mode_norm text not null,
  sealed_output     text not null check (sealed_output ~ '^[0-9a-f]{64}$'),
  envelope          jsonb not null,
  envelope_sha256   text not null check (envelope_sha256 ~ '^[0-9a-f]{64}$'),
  received_at       text not null,
  chronicle_seq     int  not null,
  is_test           boolean not null,
  constraint quest_seals_nonce_uniq    unique (nonce),
  constraint quest_seals_request_uniq  unique (quest_id, request_id),
  constraint quest_seals_pubkey_uniq   unique (quest_id, pubkey),
  constraint quest_seals_operator_uniq unique (quest_id, operator_norm)
);

create table if not exists public.quest_chronicle (
  quest_id    text not null references public.quest_manifests(quest_id),
  seq         int  not null check (seq >= 0),
  event       text not null,
  payload     jsonb not null,
  prev_hash   text not null check (prev_hash ~ '^[0-9a-f]{64}$'),
  record_hash text not null unique check (record_hash ~ '^[0-9a-f]{64}$'),
  created_at  text not null,
  is_test     boolean not null,
  primary key (quest_id, seq)
);

-- Append-only: no UPDATE / DELETE / TRUNCATE on seals or chronicle.
create or replace function public.quest_block_mutation() returns trigger
language plpgsql set search_path = '' as $$
begin
  raise exception 'append-only table %: % is not allowed', tg_table_name, tg_op;
end $$;

drop trigger if exists quest_seals_append_only on public.quest_seals;
create trigger quest_seals_append_only before update or delete on public.quest_seals
  for each row execute function public.quest_block_mutation();
drop trigger if exists quest_seals_no_truncate on public.quest_seals;
create trigger quest_seals_no_truncate before truncate on public.quest_seals
  for each statement execute function public.quest_block_mutation();
drop trigger if exists quest_chronicle_append_only on public.quest_chronicle;
create trigger quest_chronicle_append_only before update or delete on public.quest_chronicle
  for each row execute function public.quest_block_mutation();
drop trigger if exists quest_chronicle_no_truncate on public.quest_chronicle;
create trigger quest_chronicle_no_truncate before truncate on public.quest_chronicle
  for each statement execute function public.quest_block_mutation();

alter table public.quest_manifests enable row level security;
alter table public.quest_seals     enable row level security;
alter table public.quest_chronicle enable row level security;

drop policy if exists quest_manifests_public_read on public.quest_manifests;
create policy quest_manifests_public_read on public.quest_manifests for select to anon, authenticated using (true);
drop policy if exists quest_seals_public_read on public.quest_seals;
create policy quest_seals_public_read on public.quest_seals for select to anon, authenticated using (true);
drop policy if exists quest_chronicle_public_read on public.quest_chronicle;
create policy quest_chronicle_public_read on public.quest_chronicle for select to anon, authenticated using (true);

revoke insert, update, delete, truncate on public.quest_manifests, public.quest_seals, public.quest_chronicle from anon, authenticated;
grant select on public.quest_manifests, public.quest_seals, public.quest_chronicle to anon, authenticated;

-- Atomic append: seal row (optional) + chronicle record, under a per-quest
-- advisory lock; caller supplies the hash it computed over the same fields
-- and the prev_hash it expects (compare-and-swap on the chain tip).
create or replace function public.quest_append(
  p_quest_id text, p_seq int, p_event text, p_payload jsonb, p_prev_hash text,
  p_record_hash text, p_created_at text, p_seal jsonb
) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  v_tip_seq int; v_tip_hash text; v_is_test boolean;
begin
  perform pg_advisory_xact_lock(hashtextextended('quest_chronicle:' || p_quest_id, 0));
  select is_test into v_is_test from public.quest_manifests where quest_id = p_quest_id;
  if not found then raise exception 'unknown_quest' using errcode = 'P0002'; end if;
  select seq, record_hash into v_tip_seq, v_tip_hash from public.quest_chronicle
    where quest_id = p_quest_id order by seq desc limit 1;
  if not found then v_tip_seq := -1; v_tip_hash := repeat('0', 64); end if;
  if p_seq <> v_tip_seq + 1 or p_prev_hash <> v_tip_hash then
    raise exception 'chain_conflict' using errcode = '40001';
  end if;
  if p_seal is not null then
    insert into public.quest_seals (quest_id, request_id, nonce, key_id, pubkey, operator, operator_norm,
      failure_mode, failure_mode_norm, sealed_output, envelope, envelope_sha256, received_at, chronicle_seq, is_test)
    values (p_quest_id, p_seal->>'request_id', p_seal->>'nonce', p_seal->>'key_id', p_seal->>'pubkey',
      p_seal->>'operator', p_seal->>'operator_norm', p_seal->>'failure_mode', p_seal->>'failure_mode_norm',
      p_seal->>'sealed_output', p_seal->'envelope', p_seal->>'envelope_sha256', p_created_at, p_seq, v_is_test);
  end if;
  insert into public.quest_chronicle (quest_id, seq, event, payload, prev_hash, record_hash, created_at, is_test)
  values (p_quest_id, p_seq, p_event, p_payload, p_prev_hash, p_record_hash, p_created_at, v_is_test);
  return jsonb_build_object('quest_id', p_quest_id, 'seq', p_seq, 'record_hash', p_record_hash);
end $$;

create or replace function public.quest_tip(p_quest_id text) returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(
    (select jsonb_build_object('seq', seq, 'record_hash', record_hash) from public.quest_chronicle
      where quest_id = p_quest_id order by seq desc limit 1),
    jsonb_build_object('seq', -1, 'record_hash', repeat('0', 64)));
$$;

revoke all on function public.quest_append(text,int,text,jsonb,text,text,text,jsonb) from public, anon, authenticated;
revoke all on function public.quest_tip(text) from public, anon, authenticated;
revoke all on function public.quest_block_mutation() from public, anon, authenticated;
grant execute on function public.quest_append(text,int,text,jsonb,text,text,text,jsonb) to service_role;
grant execute on function public.quest_tip(text) to service_role;
