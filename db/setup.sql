-- PR Goeroes monitor — databasestructuur (idempotent: veilig om opnieuw te draaien)

create table if not exists clients (
  id            bigint generated always as identity primary key,
  name          text not null unique,
  list          text not null default 'vast',          -- vast | los | eigen | oud
  match         text[] not null default '{}',           -- zoekwoorden (bedrijfsnaam + varianten)
  spokespersons text[] not null default '{}',           -- voor- en achternaam woordvoerders
  exclude       text[] not null default '{}',           -- uitsluitwoorden tegen naamsverwarring
  website       text,                                   -- voor foto's/huisstijl in het rapport
  brand_color   text,                                   -- hex, bv. #1F6FEB
  logo_url      text,
  active        boolean not null default true,
  created_at    timestamptz not null default now()
);

create table if not exists sources (
  id          bigint generated always as identity primary key,
  outlet      text not null,
  type        text not null check (type in ('wordpress','rss','sitemap','handmatig')),
  url         text not null unique,                    -- basis-URL, feed-URL of sitemap-index
  domain      text not null,
  active      boolean not null default true,
  notes       text,
  added_by    text not null default 'systeem',
  created_at  timestamptz not null default now()
);

create table if not exists media (
  id               bigint generated always as identity primary key,
  outlet           text not null unique,
  domain           text unique,
  monthly_visitors integer,                             -- unieke bezoekers per maand (online)
  article_reach    integer,                             -- geschat bereik per artikel
  reach_basis      text,                                -- hoe article_reach is bepaald
  cpm_eur          numeric(10,2),                       -- advertentietarief per 1.000 vertoningen
  advertorial_eur  numeric(10,2),                       -- prijs gesponsord artikel (indien bekend)
  ave_eur          numeric(10,2),                       -- vaste AVE per artikel (overschrijft formule)
  confidence       text check (confidence in ('hoog','middel','laag')),
  source_urls      text,
  notes            text,
  updated_at       timestamptz not null default now()
);

create table if not exists mentions (
  id          bigint generated always as identity primary key,
  client_id   bigint not null references clients(id) on delete cascade,
  outlet      text not null,
  title       text not null,
  url         text not null,
  published   date,
  method      text not null,                            -- wordpress | rss | sitemap | google_news | handmatig
  kind        text,                                     -- press_release | news | post | ...
  matched_on  text,
  status      text not null default 'nieuw' check (status in ('nieuw','relevant','ruis')),
  reach       integer,                                  -- handmatige overschrijving
  ave_eur     numeric(10,2),                            -- handmatige overschrijving
  notes       text,
  found_at    timestamptz not null default now(),
  unique (client_id, url)
);
create index if not exists mentions_client_published on mentions (client_id, published desc);
create index if not exists mentions_found_at on mentions (found_at desc);

-- Publicaties met bereik en AVE uit de mediatabel.
-- Bereik per artikel: handmatig > vast bereik medium > unieke bezoekers per maand / 30 (gemiddeld dagbereik).
-- AVE: handmatig > vaste AVE medium > bereik x CPM / 1000 (CPM uit mediakit, anders standaard EUR 25), met een minimum van EUR 500 per publicatie.
create or replace view mentions_enriched as
select
  m.*,
  c.name as client,
  c.list as client_list,
  md.id is not null and (md.article_reach is not null or md.monthly_visitors is not null or md.ave_eur is not null) as media_known,
  coalesce(m.reach, md.article_reach, round(md.monthly_visitors / 30.0)::int) as reach_est,
  -- Jennifer (mail 3 nov 2026): elke publicatie minimaal EUR 500 mediawaarde.
  greatest(coalesce(m.ave_eur, md.ave_eur,
           round(coalesce(md.article_reach, md.monthly_visitors / 30.0) * coalesce(md.cpm_eur, 25) / 1000.0, 2), 0), 500) as ave_est,
  md.confidence as media_confidence,
  coalesce(m.published, (m.found_at at time zone 'Europe/Amsterdam')::date) as pub_date
from mentions m
join clients c on c.id = m.client_id
left join media md
  on lower(md.outlet) = lower(m.outlet)
  or lower(regexp_replace(md.outlet, '\.(nl|com)$', '')) = lower(regexp_replace(m.outlet, '\.(nl|com)$', ''));

-- Alleen de server (service role) mag erbij; geen publieke toegang.
-- Alleen Nederlandstalige vermeldingen tellen (tegen ruis bij generieke namen zoals "Doors Open"); woordvoerder telt altijd.
alter table clients add column if not exists only_dutch boolean not null default false;

alter table clients  enable row level security;
alter table sources  enable row level security;
alter table media    enable row level security;
alter table mentions enable row level security;
revoke all on mentions_enriched from anon, authenticated;

-- Stijlregels voor presentaties en rapporten: Jennifer traint ze via de chat.
create table if not exists style_rules (
  id          bigint generated always as identity primary key,
  client_id   bigint references clients(id) on delete cascade,   -- null = geldt voor alle klanten
  rule        text not null,
  created_at  timestamptz not null default now()
);
alter table style_rules enable row level security;

insert into style_rules (rule)
select r from (values
  ('Opbouw: titel met klantnaam en periode, daarna doelstellingen, kerncijfers (publicaties, bereik, advertentiewaarde), highlights, alle publicaties, en tot slot conclusie en volgende stappen.'),
  ('Gebruik beeld van de klant zelf (foto''s van hun website) zodat de klant zichzelf terugziet.'),
  ('Toon bij elke publicatie het logo of de naam van het medium; redactionele artikelen gaan voor persberichten.'),
  ('Toon publicaties en cijfers als bewijs: link naar het artikel erbij, bereik en waarde alleen als ze in de monitor bekend zijn.'),
  ('Toon: zakelijk, positief en beknopt; maximaal één kernboodschap per dia.')
) v(r)
where not exists (select 1 from style_rules);
