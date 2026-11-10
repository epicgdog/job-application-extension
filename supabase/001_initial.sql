-- Apply once in Supabase SQL Editor. No service-role key is needed by the app.
create table public.af_sources (
  id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  source_hash text not null,
  library jsonb not null,
  profile jsonb not null,
  original_path text,
  created_at timestamptz not null default now(),
  unique (user_id,source_hash),
  unique (user_id,id)
);
create table public.af_resumes (
  id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  source_id uuid not null,
  request_key text not null,
  job jsonb not null,
  state text not null check (state in ('queued','generating','uploading','complete','failed')),
  result jsonb,
  object_path text,
  error text,
  created_at timestamptz not null default now(),
  unique (user_id,request_key),
  foreign key (user_id,source_id) references public.af_sources(user_id,id),
  check (state <> 'complete' or (object_path is not null and result is not null and coalesce((result->>'page_count')::int = 1,false) and split_part(object_path,'/',1) = user_id::text))
);
create index af_resumes_owner_created on public.af_resumes(user_id,created_at desc);
alter table public.af_sources enable row level security;
alter table public.af_resumes enable row level security;
-- Immutable source imports: insert and read only. New edits create a new version.
create policy af_source_select on public.af_sources for select to authenticated using ((select auth.uid())=user_id);
create policy af_source_insert on public.af_sources for insert to authenticated with check ((select auth.uid())=user_id);
create policy af_resume_select on public.af_resumes for select to authenticated using ((select auth.uid())=user_id);
create policy af_resume_insert on public.af_resumes for insert to authenticated with check ((select auth.uid())=user_id);
create policy af_resume_update on public.af_resumes for update to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
grant select,insert on public.af_sources to authenticated;
grant select,insert,update on public.af_resumes to authenticated;
revoke all on public.af_sources,public.af_resumes from anon;

insert into storage.buckets (id,name,public,file_size_limit,allowed_mime_types)
values ('resumes','resumes',false,5242880,array['application/pdf']),
       ('resume-sources','resume-sources',false,10485760,array['application/pdf'])
on conflict (id) do nothing;
-- Assert privacy even if the buckets already existed.
update storage.buckets set public=false where id in ('resumes','resume-sources');
create policy af_files_select on storage.objects for select to authenticated
using (bucket_id in ('resumes','resume-sources') and (storage.foldername(name))[1]=(select auth.uid())::text);
create policy af_files_insert on storage.objects for insert to authenticated
with check (bucket_id in ('resumes','resume-sources') and (storage.foldername(name))[1]=(select auth.uid())::text);
-- Required to remove orphaned PDFs after a failed metadata write. No overwrite policy.
create policy af_files_delete on storage.objects for delete to authenticated
using (bucket_id in ('resumes','resume-sources') and (storage.foldername(name))[1]=(select auth.uid())::text);
