// Printbaar klantrapport (A4) in de huisstijl van de klant.
import { Db, findClient } from "./db";

const esc = (s: unknown) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));

const nl = (n: number) => new Intl.NumberFormat("nl-NL").format(Math.round(n));
const eur = (n: number) =>
  new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(Math.round(n));
const datum = (d: string) =>
  d ? new Date(d + "T12:00:00Z").toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric" }) : "";

function domainOf(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

async function brandFromSite(site: string | null) {
  if (!site) return { image: "", color: "" };
  try {
    const res = await fetch(site.startsWith("http") ? site : `https://${site}`, {
      headers: { "User-Agent": "PRGoeroesMonitor/0.2 (+https://2cre8.eu)" },
      signal: AbortSignal.timeout(8000),
    });
    const html = (await res.text()).slice(0, 200_000);
    const pick = (p: string) =>
      html.match(new RegExp(`<meta[^>]+(?:property|name)=["']${p}["'][^>]+content=["']([^"']+)["']`, "i"))?.[1] ||
      html.match(new RegExp(`<meta[^>]+content=["']([^"']+)["'][^>]+(?:property|name)=["']${p}["']`, "i"))?.[1] || "";
    const img = pick("og:image");
    return { image: img ? new URL(img, res.url).toString() : "", color: pick("theme-color") };
  } catch {
    return { image: "", color: "" };
  }
}

export async function renderReport(db: Db, params: URLSearchParams): Promise<Response> {
  const c = await findClient(db, params.get("klant") || "");
  if (!c) return new Response("Klant niet gevonden", { status: 404 });
  const van = params.get("van") || new Date(Date.now() - 30 * 86400_000).toISOString().slice(0, 10);
  const tot = params.get("tot") || new Date().toISOString().slice(0, 10);
  const rows: any[] = await db.get(
    `mentions_enriched?client_id=eq.${c.id}&published=gte.${van}&published=lte.${tot}&status=neq.ruis&order=published.desc`,
  );
  const brand = await brandFromSite(c.website);
  const accent = /^#[0-9a-f]{3,8}$/i.test(c.brand_color || "") ? c.brand_color : /^#[0-9a-f]{3,8}$/i.test(brand.color) ? brand.color : "#5B3DF5";

  const reach = rows.reduce((s, r) => s + (r.reach_est || 0), 0);
  const ave = rows.reduce((s, r) => s + Number(r.ave_est || 0), 0);
  const outlets = [...new Set(rows.map((r) => r.outlet))];
  const editorial = rows.filter((r) => r.kind !== "press_release").length;
  const unknown = rows.filter((r) => !r.media_known).length;
  // Highlights: hoogste bereik eerst, redactioneel voor persbericht
  const highlights = [...rows]
    .sort((a, b) => (b.reach_est || 0) - (a.reach_est || 0) || (a.kind === "press_release" ? 1 : -1))
    .slice(0, 3);
  const title = params.get("titel") || `Mediaresultaten ${c.name}`;
  const intro = params.get("tekst") || "";
  const logo = (url: string) => `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domainOf(url))}&sz=64`;

  const html = `<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{--accent:${esc(accent)};--ink:#14161a;--muted:#5d6470;--line:#e6e8ec;--bg:#fff;--soft:#f6f7f9}
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,sans-serif;color:var(--ink);background:#eceef1}
.page{width:210mm;min-height:297mm;margin:16px auto;background:var(--bg);padding:18mm 16mm;box-shadow:0 2px 18px rgba(0,0,0,.08)}
.cover{position:relative;border-radius:14px;overflow:hidden;background:var(--accent);color:#fff;min-height:70mm;display:flex;align-items:flex-end;padding:12mm}
.cover img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.35}
.cover .t{position:relative}.eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;opacity:.9;font-weight:600}
h1{font-size:30px;line-height:1.15;margin:6px 0 4px;font-weight:800}.period{font-size:14px;opacity:.95}
.intro{margin:9mm 0 0;font-size:14px;line-height:1.6;color:var(--muted)}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:5mm;margin:9mm 0}
.kpi{border:1px solid var(--line);border-radius:12px;padding:6mm 5mm;border-top:4px solid var(--accent)}
.kpi .v{font-size:28px;font-weight:800;letter-spacing:-.01em}.kpi .l{font-size:12px;color:var(--muted);margin-top:2px}
h2{font-size:16px;margin:9mm 0 4mm;font-weight:700}
.hl{display:grid;grid-template-columns:repeat(3,1fr);gap:4mm}
.card{background:var(--soft);border-radius:12px;padding:5mm;break-inside:avoid}
.card .o{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:600;color:var(--muted)}
.card img,.row img{width:18px;height:18px;border-radius:4px}
.card .h{font-size:13px;font-weight:600;line-height:1.35;margin:3mm 0;color:var(--ink);text-decoration:none;display:block}
.card .m{font-size:11px;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;color:var(--muted);font-weight:600;border-bottom:1px solid var(--line);padding:2.5mm 2mm}
td{border-bottom:1px solid var(--line);padding:2.5mm 2mm;vertical-align:top}td.n{text-align:right;white-space:nowrap}
.row{display:flex;align-items:center;gap:8px;font-weight:600}
a{color:inherit}.tag{font-size:10px;padding:1px 6px;border-radius:99px;background:var(--soft);color:var(--muted);margin-left:4px}
.foot{margin-top:9mm;font-size:10.5px;color:var(--muted);line-height:1.5;border-top:1px solid var(--line);padding-top:4mm}
.print{position:fixed;right:18px;bottom:18px;background:var(--accent);color:#fff;border:0;border-radius:99px;padding:12px 18px;font:600 14px Inter,sans-serif;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.2)}
@media print{body{background:#fff}.page{margin:0;box-shadow:none;width:auto;min-height:auto;padding:12mm}.print{display:none}
 .cover{-webkit-print-color-adjust:exact;print-color-adjust:exact}.kpi,.card{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
@media (max-width:820px){.page{width:auto;margin:0;padding:16px}.kpis,.hl{grid-template-columns:1fr}}
@page{size:A4;margin:0}
</style></head><body>
<button class="print" onclick="window.print()">Opslaan als pdf</button>
<div class="page">
  <div class="cover">${brand.image ? `<img src="${esc(brand.image)}" alt="">` : ""}
    <div class="t"><div class="eyebrow">Mediarapport</div><h1>${esc(title)}</h1>
    <div class="period">${esc(datum(van))} – ${esc(datum(tot))}</div></div></div>
  ${intro ? `<p class="intro">${esc(intro)}</p>` : ""}
  <div class="kpis">
    <div class="kpi"><div class="v">${nl(rows.length)}</div><div class="l">publicaties in ${nl(outlets.length)} media${editorial ? ` · ${nl(editorial)} redactioneel` : ""}</div></div>
    <div class="kpi"><div class="v">${nl(reach)}</div><div class="l">geschat bereik</div></div>
    <div class="kpi"><div class="v">${eur(ave)}</div><div class="l">advertentiewaarde</div></div>
  </div>
  ${highlights.length ? `<h2>Highlights</h2><div class="hl">${highlights.map((r) => `
    <div class="card"><div class="o"><img src="${logo(r.url)}" alt="">${esc(r.outlet)}</div>
    <a class="h" href="${esc(r.url)}">${esc(r.title)}</a>
    <div class="m">${esc(datum(r.published))}${r.reach_est ? ` · ${nl(r.reach_est)} bereik` : ""}</div></div>`).join("")}</div>` : ""}
  <h2>Alle publicaties</h2>
  <table><thead><tr><th>Medium</th><th>Publicatie</th><th>Datum</th><th class="n">Bereik</th><th class="n">Waarde</th></tr></thead><tbody>
  ${rows.map((r) => `<tr><td><div class="row"><img src="${logo(r.url)}" alt="">${esc(r.outlet)}</div></td>
    <td><a href="${esc(r.url)}">${esc(r.title)}</a>${r.kind === "press_release" ? '<span class="tag">persbericht</span>' : ""}${r.kind === "offline" ? '<span class="tag">offline</span>' : ""}</td>
    <td>${esc(datum(r.published))}</td><td class="n">${r.reach_est ? nl(r.reach_est) : "–"}</td><td class="n">${r.ave_est ? eur(Number(r.ave_est)) : "–"}</td></tr>`).join("")}
  </tbody></table>
  <div class="foot">Bereik en advertentiewaarde zijn schattingen per publicatie op basis van bezoekersaantallen en advertentietarieven van de media (mediakits en openbare bronnen). Advertentiewaarde geeft aan wat vergelijkbare zichtbaarheid als advertentie zou kosten.${unknown ? ` Voor ${nl(unknown)} publicatie(s) zijn nog geen mediacijfers bekend; die tellen niet mee in bereik en waarde.` : ""}<br>Samengesteld door PR Goeroes.</div>
</div></body></html>`;
  return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
}
