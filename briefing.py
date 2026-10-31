"""Briefings per mail, naast die van Agility.

Gebruik: python briefing.py dagelijks|wekelijks|maandelijks [--dry-run]
- dagelijks:   nieuwe publicaties (24 uur) voor vaste, losse en eigen klanten
- wekelijks:   nieuwe publicaties (7 dagen) voor oud-klanten
- maandelijks: overzicht vorige maand per klant, met link naar het rapport

Versturen via SMTP (Gmail met app-wachtwoord). Nodig: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
MCP_TOKEN, MCP_BASE, SMTP_USER, SMTP_PASSWORD, BRIEFING_TO (komma-gescheiden).
"""
import hashlib
import hmac
import html
import os
import smtplib
import sys
import urllib.parse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr

import supa

ACCENT = "#5B3DF5"
LISTS = {"vast": "Vaste klanten", "los": "Losse klanten", "eigen": "Onze eigen naam en producten",
         "oud": "Eerdere samenwerkingen"}
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
           "september", "oktober", "november", "december"]
DAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]


def e(s):
    return html.escape(str(s or ""))


def nl_date(d):
    if not d:
        return ""
    d = date.fromisoformat(str(d)[:10])
    return f"{d.day} {MAANDEN[d.month - 1]}"


def fmt_int(n):
    return f"{int(round(n)):,}".replace(",", ".")


def signed_report_link(klant, van, tot):
    base = os.environ.get("MCP_BASE", "").rstrip("/")
    params = sorted({"klant": klant, "van": van, "tot": tot}.items())
    q = urllib.parse.urlencode(params, quote_via=urllib.parse.quote_plus)
    sig = hmac.new(os.environ["MCP_TOKEN"].encode(), q.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{base}/rapport?{q}&sig={sig}"


def fetch(where):
    return supa.select("mentions_enriched", **where, status="neq.ruis", order="client,pub_date.desc")


def item_html(r):
    meta = [nl_date(r.get("published") or r.get("pub_date"))]
    if r.get("reach_est"):
        meta.append(f"{fmt_int(r['reach_est'])} bereik")
    if r.get("ave_est"):
        meta.append(f"€ {fmt_int(float(r['ave_est']))} waarde")
    tag = " · persbericht" if r.get("kind") == "press_release" else ""
    return (f'<tr><td style="padding:10px 0;border-bottom:1px solid #eceef1">'
            f'<div style="font-size:12px;color:#5d6470;font-weight:600">{e(r["outlet"])}{tag}</div>'
            f'<a href="{e(r["url"])}" style="font-size:15px;color:#14161a;font-weight:600;text-decoration:none">{e(r["title"])}</a>'
            f'<div style="font-size:12px;color:#5d6470;margin-top:2px">{e(" · ".join(m for m in meta if m))}</div></td></tr>')


def wrap(title, subtitle, body):
    return f"""<!doctype html><html><body style="margin:0;background:#f3f4f6;font-family:Inter,Arial,sans-serif;color:#14161a">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#fff;border-radius:14px;overflow:hidden">
<tr><td style="background:{ACCENT};color:#fff;padding:22px 26px">
<div style="font-size:11px;letter-spacing:.14em;text-transform:uppercase;opacity:.9;font-weight:600">PR Goeroes monitor</div>
<div style="font-size:24px;font-weight:800;margin-top:4px">{e(title)}</div>
<div style="font-size:14px;opacity:.95;margin-top:2px">{e(subtitle)}</div></td></tr>
<tr><td style="padding:8px 26px 24px">{body}
<p style="font-size:12px;color:#5d6470;line-height:1.55;margin-top:26px;border-top:1px solid #eceef1;padding-top:12px">
Iets gemist? Zeg in Claude: <i>"neem deze link mee voor [klant]"</i>, dan staat hij er de volgende keer in en wordt het medium voortaan gevolgd.<br>
Bereik en waarde zijn schattingen op basis van mediacijfers; ze worden alleen getoond als het medium in de mediatabel staat.</p>
</td></tr></table></td></tr></table></body></html>"""


def build_list_briefing(lists, hours, title):
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=hours)).isoformat()
    recent = (now - timedelta(days=max(7, hours // 24 + 2))).date().isoformat()
    clients = supa.select("clients", active="eq.true", order="name")
    rows = fetch({"found_at": f"gte.{since}", "pub_date": f"gte.{recent}"})
    per = defaultdict(list)
    for r in rows:
        if r["client_list"] in lists:
            per[r["client"]].append(r)
    total = sum(len(v) for v in per.values())
    parts = []
    for lst in lists:
        names = [c["name"] for c in clients if c["list"] == lst]
        if not names:
            continue
        parts.append(f'<h2 style="font-size:17px;margin:22px 0 4px">{e(LISTS[lst])}</h2>')
        quiet = []
        for n in names:
            if per.get(n):
                parts.append(f'<h3 style="font-size:14px;margin:14px 0 0;color:{ACCENT}">{e(n)}</h3>'
                             f'<table width="100%" cellpadding="0" cellspacing="0">{"".join(item_html(r) for r in per[n])}</table>')
            else:
                quiet.append(n)
        if quiet:
            parts.append(f'<p style="font-size:12px;color:#5d6470;margin:10px 0 0">Geen nieuwe publicaties: {e(", ".join(quiet))}</p>')
    today = datetime.now(timezone.utc).astimezone().date()
    subtitle = f"{DAGEN[today.weekday()]} {today.day} {MAANDEN[today.month - 1]} {today.year}"
    subject = f"{title} – {subtitle}: {total} nieuwe publicatie{'s' if total != 1 else ''}"
    return subject, wrap(title, subtitle, "".join(parts)), total


def build_monthly():
    today = date.today()
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    van, tot = last_prev.replace(day=1).isoformat(), last_prev.isoformat()
    maand = f"{MAANDEN[last_prev.month - 1]} {last_prev.year}"
    rows = fetch({"pub_date": f"gte.{van}", "and": f"(pub_date.lte.{tot})"})
    per = defaultdict(list)
    rows = [r for r in rows if r["client_list"] in ("vast", "los", "eigen")]  # oud-klanten: wekelijkse mail
    for r in rows:
        per[(r["client_list"], r["client"])].append(r)
    total = len(rows)
    parts = [f'<p style="font-size:14px;line-height:1.6">In {e(maand)} vond de monitor <b>{total}</b> publicaties '
             f'voor {len({k[1] for k in per})} klanten. Per klant staat hieronder een link naar het rapport, klaar om als pdf op te slaan.</p>']
    for lst in LISTS:
        keys = sorted([k for k in per if k[0] == lst], key=lambda k: -len(per[k]))
        if not keys:
            continue
        parts.append(f'<h2 style="font-size:17px;margin:22px 0 6px">{e(LISTS[lst])}</h2>'
                     '<table width="100%" cellpadding="0" cellspacing="0" style="font-size:14px">')
        for k in keys:
            rs = per[k]
            reach = sum(r.get("reach_est") or 0 for r in rs)
            ave = sum(float(r.get("ave_est") or 0) for r in rs)
            extra = (f" · {fmt_int(reach)} bereik" if reach else "") + (f" · € {fmt_int(ave)} waarde" if ave else "")
            link = signed_report_link(k[1], van, tot)
            parts.append(f'<tr><td style="padding:9px 0;border-bottom:1px solid #eceef1"><b>{e(k[1])}</b>'
                         f'<div style="font-size:12px;color:#5d6470">{len(rs)} publicatie{"s" if len(rs) != 1 else ""}{e(extra)}</div></td>'
                         f'<td align="right" style="border-bottom:1px solid #eceef1"><a href="{e(link)}" '
                         f'style="background:{ACCENT};color:#fff;text-decoration:none;font-weight:600;font-size:13px;padding:7px 12px;border-radius:99px">Rapport</a></td></tr>')
        parts.append("</table>")
    subject = f"PR Goeroes maandoverzicht – {maand}: {total} publicaties"
    return subject, wrap("Maandoverzicht", maand, "".join(parts)), total


def send(subject, body_html):
    to = [a.strip() for a in os.environ.get("BRIEFING_TO", "").split(",") if a.strip()]
    if not to:
        sys.exit("BRIEFING_TO ontbreekt")
    user = os.environ["SMTP_USER"]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr(("PR Goeroes monitor", user))
    msg["To"] = ", ".join(to)
    msg.set_content("Deze briefing is in HTML opgemaakt. Open hem in een mailprogramma dat HTML toont.")
    msg.add_alternative(body_html, subtype="html")
    with smtplib.SMTP_SSL(os.environ.get("SMTP_HOST", "smtp.gmail.com"), 465, timeout=60) as s:
        s.login(user, os.environ["SMTP_PASSWORD"])
        s.send_message(msg)
    print(f"Verstuurd aan {len(to)} ontvanger(s): {subject}")


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else "dagelijks"
    dry = "--dry-run" in sys.argv or not os.environ.get("SMTP_PASSWORD")
    if kind == "dagelijks":
        subject, body, n = build_list_briefing(["vast", "los", "eigen"], 24, "Dagelijkse briefing")
    elif kind == "wekelijks":
        subject, body, n = build_list_briefing(["oud"], 24 * 7, "Wekelijkse update eerdere samenwerkingen")
    elif kind == "maandelijks":
        subject, body, n = build_monthly()
    else:
        sys.exit(f"Onbekend type: {kind}")
    os.makedirs("data", exist_ok=True)
    with open(f"data/briefing-{kind}.html", "w", encoding="utf-8") as f:
        f.write(body)
    print(subject)
    if dry:
        print("(proefrun: niet verstuurd)")
    else:
        send(subject, body)


if __name__ == "__main__":
    main()
