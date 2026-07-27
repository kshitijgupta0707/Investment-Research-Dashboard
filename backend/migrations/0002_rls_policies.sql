-- Row-Level Security.
--
-- This is a backstop. The primary tenant defence is the FastAPI dependency that
-- resolves org_id from the verified JWT and filters every query by it, because
-- the API connects with a privileged role that RLS does not constrain. These
-- policies catch anything reaching Postgres over a user JWT instead.

-- Helpers resolve the caller's application identity from the Supabase auth uid.
-- security definer is required: they read users, which is itself under RLS.

create function public.current_app_user_id() returns uuid
language sql stable security definer set search_path = public
as $$
    select id from users where supabase_auth_id = auth.uid();
$$;

create function public.current_org_id() returns uuid
language sql stable security definer set search_path = public
as $$
    select org_id from users where supabase_auth_id = auth.uid();
$$;

create function public.current_app_role() returns text
language sql stable security definer set search_path = public
as $$
    select role from users where supabase_auth_id = auth.uid();
$$;


alter table organizations    enable row level security;
alter table users            enable row level security;
alter table org_invites      enable row level security;
alter table research_queries enable row level security;
alter table research_reports enable row level security;
alter table watchlist        enable row level security;
alter table audit_logs       enable row level security;
alter table kb_documents     enable row level security;


-- A member sees only their own organization.
create policy organizations_same_org on organizations
    for select to authenticated
    using (id = public.current_org_id());

create policy users_same_org on users
    for select to authenticated
    using (org_id = public.current_org_id());


-- Invite codes are org-visible but admin-managed.
create policy org_invites_same_org on org_invites
    for select to authenticated
    using (org_id = public.current_org_id());

create policy org_invites_admin_write on org_invites
    for all to authenticated
    using (org_id = public.current_org_id() and public.current_app_role() = 'admin')
    with check (org_id = public.current_org_id() and public.current_app_role() = 'admin');


-- History is per-user within an org.
create policy research_queries_own on research_queries
    for all to authenticated
    using (org_id = public.current_org_id() and user_id = public.current_app_user_id())
    with check (org_id = public.current_org_id() and user_id = public.current_app_user_id());


-- Reports are a shared org workspace: any member reads, only the creator or an
-- admin may modify. This mirrors the ownership check enforced in the API.
create policy research_reports_org_read on research_reports
    for select to authenticated
    using (org_id = public.current_org_id());

create policy research_reports_insert on research_reports
    for insert to authenticated
    with check (
        org_id = public.current_org_id()
        and created_by = public.current_app_user_id()
    );

create policy research_reports_owner_or_admin_update on research_reports
    for update to authenticated
    using (
        org_id = public.current_org_id()
        and (created_by = public.current_app_user_id() or public.current_app_role() = 'admin')
    )
    with check (org_id = public.current_org_id());

create policy research_reports_owner_or_admin_delete on research_reports
    for delete to authenticated
    using (
        org_id = public.current_org_id()
        and (created_by = public.current_app_user_id() or public.current_app_role() = 'admin')
    );


create policy watchlist_own on watchlist
    for all to authenticated
    using (org_id = public.current_org_id() and user_id = public.current_app_user_id())
    with check (org_id = public.current_org_id() and user_id = public.current_app_user_id());


-- Audit entries are readable org-wide and written only by the API's privileged
-- connection, so no insert policy is granted to end users.
create policy audit_logs_org_read on audit_logs
    for select to authenticated
    using (org_id = public.current_org_id());


-- Shared reference corpus: readable by any authenticated user, never written
-- through the API.
create policy kb_documents_read on kb_documents
    for select to authenticated
    using (true);


grant usage on schema public to authenticated;
grant select on organizations, users, org_invites, audit_logs, kb_documents to authenticated;
grant select, insert, update, delete on research_queries, research_reports, watchlist to authenticated;
