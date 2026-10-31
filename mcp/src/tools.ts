// De gereedschappen die Claude via MCP kan gebruiken.
import { Db, enc, findClient } from "./db";

const UA = "PRGoeroesMonitor/0.2 (+https://2cre8.eu)";

type Tool = {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  run: (db: Db, args: any, ctx: { reportBase: string }) => Promise<unknown>;
};

const str = (description: string) => ({ type: "string", description });
const int = (description: string) => ({ type: "integer", description });
const strList = (description: string) => ({ type: "array", items: { type: "string" }, description });

function isoDaysAgo(days: number) {
  return new Date(Date.now() - days * 86400_000).toISOString();
}

function domainOf(url: string) {
  try {
    return new URL(url.startsWith("http") ? url : `https://${url}`).hostname.replace(/^www\./, "").toLowerCase();
  } catch {
    return "";
  }
}

function fmtEur(n: number | null | undefined) {
  return n == null ? null : Math.round(Number(n));
}

function shape(m: any) {
  return {
    id: m.id,
    klant: m.client,
    medium: m.outlet,
    titel: m.title,
    url: m.url,
    datum: m.published,
    soort: m.kind === "press_release" ? "persbericht" : m.kind ? "artikel" : null,
    gevonden_via: m.method,
    status: m.status,
    bereik: m.reach_est,
    ave_eur: fmtEur(m.ave_est),
    medium_in_mediatabel: m.media_known,
  };
}

function totals(rows: any[]) {
  const rel = rows.filter((r) => r.status !== "ruis");
  return {
    publicaties: rel.length,
    bereik: rel.reduce((s, r) => s + (r.reach_est || 0), 0),
    ave_eur: Math.round(rel.reduce((s, r) => s + Number(r.ave_est || 0), 0)),
    zonder_mediawaarde: rel.filter((r) => !r.media_known).map((r) => r.outlet),
  };
}

async function fetchText(url: string, timeoutMs = 12000): Promise<{ status: number; text: string; type: string }> {
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": UA, Accept: "*/*" },
      redirect: "follow",
      signal: AbortSignal.timeout(timeoutMs),
    });
    return { status: res.status, text: await res.text(), type: res.headers.get("content-type") || "" };
  } catch {
    return { status: 0, text: "", type: "" };
  }
}

function meta(html: string, prop: string) {
  const re = new RegExp(`<meta[^>]+(?:property|name)=["']${prop}["'][^>]+content=["']([^"']+)["']`, "i");
  const re2 = new RegExp(`<meta[^>]+content=["']([^"']+)["'][^>]+(?:property|name)=["']${prop}["']`, "i");
  const m = html.match(re) || html.match(re2);
  return m ? decode(m[1]) : "";
}

function decode(s: string) {
  return s
    .replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#039;|&#39;|&#8217;/g, "'")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&#8211;/g, "–").trim();
}

function robotsDisallows(robots: string, path: string) {
  // Eenvoudige check van regels onder "User-agent: *"
  let applies = false;
  for (const raw of robots.split("\n")) {
    const line = raw.split("#")[0].trim();
    if (/^user-agent:/i.test(line)) applies = line.split(":")[1].trim() === "*";
    else if (applies && /^disallow:/i.test(line)) {
      const rule = line.slice(9).trim();
      if (rule && path.startsWith(rule.replace(/\*.*$/, ""))) return true;
    }
  }
  return false;
}

export async function detectSource(input: string) {
  const domain = domainOf(input);
  if (!domain) return { ok: false, reden: "Ongeldige link of domein" };
  let base = `https://www.${domain}`;
  let home = await fetchText(base);
  if (home.status !== 200) {
    base = `https://${domain}`;
    home = await fetchText(base);
  }
  if (home.status === 403 || /leastFactor|cf-challenge|captcha/i.test(home.text.slice(0, 3000))) {
    return { ok: true, type: "handmatig", url: base, domain, reden: "De site houdt robots tegen (botcontrole); publicaties hier handmatig toevoegen." };
  }
  const robots = (await fetchText(`${base}/robots.txt`)).text;
  const outlet = meta(home.text, "og:site_name") || domain;

  if (!robotsDisallows(robots, "/wp-json/")) {
    const wp = await fetchText(`${base}/wp-json/wp/v2/search?search=nieuws&per_page=1`);
    if (wp.status === 200 && wp.text.trim().startsWith("[")) {
      return { ok: true, type: "wordpress", url: base, domain, outlet, reden: "WordPress-zoekfunctie werkt" };
    }
  }
  const feeds: string[] = [];
  const alt = home.text.match(/<link[^>]+type=["']application\/(?:rss|atom)\+xml["'][^>]*>/gi) || [];
  for (const tag of alt) {
    const href = tag.match(/href=["']([^"']+)["']/i)?.[1];
    if (href) feeds.push(new URL(href, base).toString());
  }
  feeds.push(`${base}/feed/`, `${base}/rss.xml`, `${base}/rss`, `${base}/feed.xml`);
  for (const f of feeds) {
    if (robotsDisallows(robots, new URL(f).pathname)) continue;
    const r = await fetchText(f);
    if (r.status === 200 && /<(rss|feed)[\s>]/i.test(r.text.slice(0, 2000))) {
      const items = (r.text.match(/<item[\s>]|<entry[\s>]/gi) || []).length;
      return { ok: true, type: "rss", url: f, domain, outlet, reden: `RSS-feed gevonden (${items} items)` };
    }
  }
  const sm = robots.match(/^sitemap:\s*(\S+)/im)?.[1] || `${base}/sitemap.xml`;
  const s = await fetchText(sm);
  if (s.status === 200 && /<(sitemapindex|urlset)/i.test(s.text.slice(0, 2000))) {
    return { ok: true, type: "sitemap", url: sm, domain, outlet, reden: "Sitemap gevonden; zoekt op klantnaam in de link" };
  }
  return { ok: true, type: "handmatig", url: base, domain, outlet, reden: "Geen zoekfunctie, feed of sitemap gevonden; publicaties hier handmatig toevoegen." };
}

export const tools: Tool[] = [
  {
    name: "klanten_lijst",
    description: "Lijst van alle klanten die gemonitord worden, met lijst (vast/los/eigen/oud), zoekwoorden en woordvoerders.",
    inputSchema: { type: "object", properties: { lijst: str("Optioneel: vast, los, eigen of oud") } },
    async run(db, a) {
      const f = a.lijst ? `&list=eq.${enc(a.lijst)}` : "";
      const rows = await db.get(`clients?select=name,list,match,spokespersons,exclude,website,active&order=list,name${f}`);
      return rows.map((c: any) => ({ klant: c.name, lijst: c.list, zoekwoorden: c.match, woordvoerders: c.spokespersons, uitsluitwoorden: c.exclude, website: c.website, actief: c.active }));
    },
  },
  {
    name: "briefing",
    description: "Dagelijkse of wekelijkse briefing: alle nieuw gevonden publicaties van de afgelopen dagen, per klant, met bereik en advertentiewaarde (AVE). Gebruik dit voor 'wat is er gisteren verschenen'.",
    inputSchema: {
      type: "object",
      properties: { dagen: int("Aantal dagen terug (standaard 1)"), lijst: str("Optioneel: vast, los, eigen of oud") },
    },
    async run(db, a) {
      const days = a.dagen || 1;
      const f = a.lijst ? `&client_list=eq.${enc(a.lijst)}` : "";
      const rows = await db.get(`mentions_enriched?found_at=gte.${isoDaysAgo(days)}&status=neq.ruis&order=client,published.desc${f}`);
      const per: Record<string, any[]> = {};
      for (const r of rows) (per[r.client] ||= []).push(shape(r));
      return { periode_dagen: days, totaal: totals(rows), per_klant: per };
    },
  },
  {
    name: "publicaties_zoeken",
    description: "Alle publicaties van één klant in een periode, met bereik, AVE en hoe ze gevonden zijn.",
    inputSchema: {
      type: "object",
      required: ["klant"],
      properties: {
        klant: str("Naam van de klant"),
        van: str("Begindatum JJJJ-MM-DD (standaard 30 dagen terug)"),
        tot: str("Einddatum JJJJ-MM-DD (standaard vandaag)"),
        inclusief_ruis: { type: "boolean", description: "Ook publicaties tonen die als ruis zijn gemarkeerd" },
      },
    },
    async run(db, a) {
      const c = await findClient(db, a.klant);
      if (!c) return { fout: `Klant '${a.klant}' niet gevonden. Gebruik klanten_lijst.` };
      const van = a.van || isoDaysAgo(30).slice(0, 10);
      const tot = a.tot || new Date().toISOString().slice(0, 10);
      const ruis = a.inclusief_ruis ? "" : "&status=neq.ruis";
      const rows = await db.get(`mentions_enriched?client_id=eq.${c.id}&published=gte.${van}&published=lte.${tot}${ruis}&order=published.desc`);
      return { klant: c.name, van, tot, totaal: totals(rows), publicaties: rows.map(shape) };
    },
  },
  {
    name: "publicatie_toevoegen",
    description: "Voeg een publicatie toe die handmatig gevonden is (link plakken). Titel, medium en datum worden van de pagina gehaald als ze niet zijn opgegeven. Meldt ook of het medium al gevolgd wordt.",
    inputSchema: {
      type: "object",
      required: ["klant", "url"],
      properties: {
        klant: str("Naam van de klant"),
        url: str("Link naar de publicatie"),
        titel: str("Optioneel"),
        medium: str("Optioneel, bv. AD of Computable"),
        datum: str("Optioneel, JJJJ-MM-DD"),
        offline: { type: "boolean", description: "Print, radio of tv (geen werkende link nodig)" },
      },
    },
    async run(db, a) {
      const c = await findClient(db, a.klant);
      if (!c) return { fout: `Klant '${a.klant}' niet gevonden.` };
      let title = a.titel || "", outlet = a.medium || "", date = a.datum || "";
      if (!a.offline && (!title || !outlet || !date)) {
        const p = await fetchText(a.url);
        if (p.status === 200) {
          title ||= meta(p.text, "og:title") || decode(p.text.match(/<title>([^<]+)<\/title>/i)?.[1] || "");
          outlet ||= meta(p.text, "og:site_name");
          date ||= (meta(p.text, "article:published_time") || p.text.match(/"datePublished"\s*:\s*"([^"]+)"/)?.[1] || "").slice(0, 10);
        }
      }
      const domain = domainOf(a.url);
      outlet ||= domain;
      title ||= decodeURIComponent(new URL(a.url).pathname.split("/").filter(Boolean).pop() || a.url).replace(/-/g, " ");
      const [row] = await db.insert("mentions", [{
        client_id: c.id, outlet, title, url: a.url, published: date || null,
        method: "handmatig", kind: a.offline ? "offline" : null, status: "relevant", notes: "Handmatig toegevoegd via chat",
      }], "client_id,url", "merge");
      const src = await db.get(`sources?domain=eq.${enc(domain)}&select=type,active`);
      return {
        toegevoegd: shape({ ...row, client: c.name }),
        medium_gevolgd: src.length ? `ja (${src[0].type})` : "nee — gebruik bron_toevoegen om dit medium voortaan automatisch te doorzoeken",
      };
    },
  },
  {
    name: "publicatie_beoordelen",
    description: "Markeer een publicatie als relevant of als ruis (bv. naamsverwarring). Ruis telt niet mee in briefings en rapporten.",
    inputSchema: {
      type: "object",
      required: ["id", "status"],
      properties: { id: int("Id van de publicatie"), status: { type: "string", enum: ["relevant", "ruis"] }, opmerking: str("Optioneel") },
    },
    async run(db, a) {
      const r = await db.update("mentions", `id=eq.${a.id}`, { status: a.status, ...(a.opmerking ? { notes: a.opmerking } : {}) });
      return r.length ? { bijgewerkt: r[0].id, status: r[0].status } : { fout: "Publicatie niet gevonden" };
    },
  },
  {
    name: "bron_toevoegen",
    description: "Laat een nieuw medium (website) voortaan automatisch doorzoeken. Onderzoekt zelf de beste route: WordPress-zoekfunctie, RSS-feed of sitemap, en respecteert robots.txt.",
    inputSchema: { type: "object", required: ["url"], properties: { url: str("Link naar de site of een artikel erop"), naam: str("Optioneel: naam van het medium") } },
    async run(db, a) {
      const d = await detectSource(a.url);
      if (!d.ok) return d;
      const existing = await db.get(`sources?domain=eq.${enc(d.domain!)}&select=*`);
      if (existing.length) return { al_gevolgd: true, medium: existing[0].outlet, route: existing[0].type };
      const [row] = await db.insert("sources", [{
        outlet: a.naam || (d as any).outlet || d.domain, type: d.type, url: d.url, domain: d.domain,
        notes: d.reden, added_by: "chat",
      }], "url", "ignore");
      return { toegevoegd: row?.outlet || d.domain, route: d.type, uitleg: d.reden, actief_vanaf: "de volgende monitorrun" };
    },
  },
  {
    name: "bronnen_lijst",
    description: "Alle media die gevolgd worden en via welke route (wordpress, rss, sitemap of handmatig).",
    inputSchema: { type: "object", properties: {} },
    async run(db) {
      const rows = await db.get("sources?select=outlet,domain,type,active,notes,added_by&order=outlet");
      return rows.map((s: any) => ({ medium: s.outlet, domein: s.domain, route: s.type, actief: s.active, toelichting: s.notes, toegevoegd_door: s.added_by }));
    },
  },
  {
    name: "klant_beheren",
    description: "Voeg een klant toe of werk hem bij: zoekwoorden, woordvoerders (maakt zoeken preciezer), uitsluitwoorden tegen naamsverwarring, website en huisstijlkleur voor het rapport.",
    inputSchema: {
      type: "object",
      required: ["naam"],
      properties: {
        naam: str("Naam van de klant"),
        lijst: { type: "string", enum: ["vast", "los", "eigen", "oud"] },
        zoekwoorden: strList("Bedrijfsnaam en varianten"),
        woordvoerders: strList("Voor- en achternamen"),
        uitsluitwoorden: strList("Woorden die op naamsverwarring wijzen"),
        website: str("Website van de klant (voor foto's in het rapport)"),
        huisstijlkleur: str("Hex-kleur, bv. #1F6FEB"),
        actief: { type: "boolean" },
      },
    },
    async run(db, a) {
      const c = await findClient(db, a.naam);
      const v: Record<string, unknown> = {};
      if (a.lijst) v.list = a.lijst;
      if (a.zoekwoorden) v.match = a.zoekwoorden;
      if (a.woordvoerders) v.spokespersons = a.woordvoerders;
      if (a.uitsluitwoorden) v.exclude = a.uitsluitwoorden;
      if (a.website) v.website = a.website;
      if (a.huisstijlkleur) v.brand_color = a.huisstijlkleur;
      if (a.actief !== undefined) v.active = a.actief;
      if (c) {
        const [r] = await db.update("clients", `id=eq.${c.id}`, v);
        return { bijgewerkt: r.name, ...v };
      }
      const [r] = await db.insert("clients", [{ name: a.naam, match: a.zoekwoorden || [a.naam], ...v }]);
      return { toegevoegd: r.name, ...v };
    },
  },
  {
    name: "mediawaarde_instellen",
    description: "Stel bereik en advertentiewaarde van een medium in of corrigeer ze. Wordt gebruikt voor alle publicaties in dat medium.",
    inputSchema: {
      type: "object",
      required: ["medium"],
      properties: {
        medium: str("Naam zoals in de publicaties, bv. Computable"),
        domein: str("Optioneel, bv. computable.nl"),
        bezoekers_per_maand: int("Unieke bezoekers per maand"),
        bereik_per_artikel: int("Geschat aantal lezers per artikel"),
        cpm_eur: { type: "number", description: "Advertentietarief per 1.000 vertoningen" },
        advertorial_eur: { type: "number", description: "Prijs van een gesponsord artikel" },
        vaste_ave_eur: { type: "number", description: "Vaste advertentiewaarde per publicatie (overschrijft de rest)" },
        bron: str("Waar komt het cijfer vandaan"),
      },
    },
    async run(db, a) {
      const v: Record<string, unknown> = { outlet: a.medium, updated_at: new Date().toISOString(), confidence: "hoog" };
      if (a.domein) v.domain = a.domein;
      if (a.bezoekers_per_maand != null) v.monthly_visitors = a.bezoekers_per_maand;
      if (a.bereik_per_artikel != null) v.article_reach = a.bereik_per_artikel;
      if (a.cpm_eur != null) v.cpm_eur = a.cpm_eur;
      if (a.advertorial_eur != null) v.advertorial_eur = a.advertorial_eur;
      if (a.vaste_ave_eur != null) v.ave_eur = a.vaste_ave_eur;
      if (a.bron) v.source_urls = a.bron;
      const [r] = await db.insert("media", [v], "outlet", "merge");
      return { opgeslagen: r };
    },
  },
  {
    name: "rapport_maken",
    description: "Maak het klantrapport voor een periode: aantal publicaties, bereik, advertentiewaarde en highlights, in de huisstijl van de klant. Geeft een link naar een printbare pagina (opslaan als pdf).",
    inputSchema: {
      type: "object",
      required: ["klant"],
      properties: {
        klant: str("Naam van de klant"),
        van: str("Begindatum JJJJ-MM-DD (standaard 30 dagen terug)"),
        tot: str("Einddatum JJJJ-MM-DD (standaard vandaag)"),
        titel: str("Optionele titel, bv. 'Lancering Aspyre'"),
        toelichting: str("Optionele tekst van Jennifer bovenaan het rapport"),
      },
    },
    async run(db, a, ctx) {
      const c = await findClient(db, a.klant);
      if (!c) return { fout: `Klant '${a.klant}' niet gevonden.` };
      const van = a.van || isoDaysAgo(30).slice(0, 10);
      const tot = a.tot || new Date().toISOString().slice(0, 10);
      const rows = await db.get(`mentions_enriched?client_id=eq.${c.id}&published=gte.${van}&published=lte.${tot}&status=neq.ruis`);
      const q = new URLSearchParams({ klant: c.name, van, tot });
      if (a.titel) q.set("titel", a.titel);
      if (a.toelichting) q.set("tekst", a.toelichting);
      return {
        klant: c.name, van, tot, totaal: totals(rows),
        rapport_link: `${ctx.reportBase}?${q.toString()}`,
        tip: "Open de link en kies Afdrukken → Opslaan als pdf.",
      };
    },
  },
];
