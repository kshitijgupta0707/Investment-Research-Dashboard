-- Core schema: organizations, membership, research artefacts and the shared
-- knowledge-base corpus.
--
-- Every table except kb_documents carries org_id and is tenant-scoped.
-- kb_documents is a shared reference corpus with no tenant column.

create extension if not exists pgcrypto;


create table organizations (
    id          uuid primary key default gen_random_uuid(),
    name        text not null,
    created_at  timestamptz not null default now()
);


-- supabase_auth_id mirrors auth.users(id). No foreign key: keeping this table
-- free of the auth schema lets the migrations run against a plain Postgres.
create table users (
    id                uuid primary key default gen_random_uuid(),
    supabase_auth_id  uuid not null unique,
    email             text not null,
    name              text,
    org_id            uuid not null references organizations (id) on delete cascade,
    role              text not null check (role in ('admin', 'analyst')),
    created_at        timestamptz not null default now()
);

create index users_org_id_idx on users (org_id);


create table org_invites (
    id          uuid primary key default gen_random_uuid(),
    org_id      uuid not null references organizations (id) on delete cascade,
    code        text not null unique,
    created_by  uuid not null references users (id) on delete cascade,
    status      text not null default 'active' check (status in ('active', 'revoked', 'expired')),
    expires_at  timestamptz,
    created_at  timestamptz not null default now()
);


-- Query history, including queries the user never saved as a report.
create table research_queries (
    id              uuid primary key default gen_random_uuid(),
    org_id          uuid not null references organizations (id) on delete cascade,
    user_id         uuid not null references users (id) on delete cascade,
    query_text      text not null,
    tools_selected  text[] not null default '{}',
    status          text not null check (status in ('success', 'partial', 'failed')),
    latency_ms      integer,
    created_at      timestamptz not null default now()
);

create index research_queries_org_user_created_idx
    on research_queries (org_id, user_id, created_at desc);


create table research_reports (
    id                 uuid primary key default gen_random_uuid(),
    org_id             uuid not null references organizations (id) on delete cascade,
    created_by         uuid not null references users (id) on delete cascade,
    query_text         text not null,
    structured_result  jsonb not null,
    tags               text[] not null default '{}',
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);

create index research_reports_org_created_idx
    on research_reports (org_id, created_at desc);

create index research_reports_tags_idx
    on research_reports using gin (tags);

create index research_reports_query_text_idx
    on research_reports using gin (to_tsvector('english', query_text));


create table watchlist (
    id            uuid primary key default gen_random_uuid(),
    org_id        uuid not null references organizations (id) on delete cascade,
    user_id       uuid not null references users (id) on delete cascade,
    ticker        text not null,
    company_name  text,
    created_at    timestamptz not null default now(),
    unique (org_id, user_id, ticker)
);

create index watchlist_org_user_idx on watchlist (org_id, user_id);


-- user_id is nullable so deleting a user does not erase the audit trail.
create table audit_logs (
    id           uuid primary key default gen_random_uuid(),
    org_id       uuid not null references organizations (id) on delete cascade,
    user_id      uuid references users (id) on delete set null,
    action       text not null,
    entity_type  text,
    entity_id    uuid,
    metadata     jsonb not null default '{}',
    created_at   timestamptz not null default now()
);

create index audit_logs_org_created_idx on audit_logs (org_id, created_at desc);


create table kb_documents (
    id            uuid primary key default gen_random_uuid(),
    ticker        text not null,
    doc_type      text not null,
    chunk_text    text not null,
    chunk_index   integer not null,
    source_label  text not null,
    created_at    timestamptz not null default now()
);

create index kb_documents_ticker_idx on kb_documents (ticker);


create function set_updated_at() returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger research_reports_set_updated_at
    before update on research_reports
    for each row execute function set_updated_at();
