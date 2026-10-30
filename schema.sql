-- Paste into Supabase: SQL Editor -> New query -> Run

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text unique not null,
  profile_name text not null
);

create table public.todos (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  text text not null,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.todos enable row level security;

-- Profiles: a user can read only their own profile
create policy "read own profile" on public.profiles
  for select using (auth.uid() = id);

-- Todos: a user can read, add, and delete only their own
create policy "read own todos" on public.todos
  for select using (auth.uid() = user_id);
create policy "add own todos" on public.todos
  for insert with check (auth.uid() = user_id);
create policy "delete own todos" on public.todos
  for delete using (auth.uid() = user_id);

-- Create the profile automatically when a user signs up
-- (username and profile_name come from the sign-up metadata)
create function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, username, profile_name)
  values (new.id, new.raw_user_meta_data->>'username', new.raw_user_meta_data->>'profile_name');
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
