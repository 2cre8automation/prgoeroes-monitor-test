// PR Goeroes monitor — MCP-server (Streamable HTTP, stateless) + rapportpagina's.
import { Db, Env } from "./db";
import { tools } from "./tools";
import { renderReport } from "./report";

const SUPPORTED = ["2025-06-18", "2025-03-26", "2024-11-05"];

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function safeEqual(a: string, b: string) {
  if (!a || !b || a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

async function sign(secret: string, data: string) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(data));
  return [...new Uint8Array(sig)].slice(0, 16).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Rapportlinks worden ondertekend, zodat een gedeelde link geen toegang tot de MCP geeft.
async function signedReportLink(env: Env, origin: string, query: string) {
  const q = new URLSearchParams(query);
  q.delete("sig");
  q.sort();
  q.set("sig", await sign(env.MCP_TOKEN, q.toString()));
  return `${origin}/rapport?${q.toString()}`;
}

async function handleRpc(msg: any, env: Env, origin: string) {
  const { id, method, params } = msg || {};
  const reply = (result: unknown) => ({ jsonrpc: "2.0", id, result });
  const fail = (code: number, message: string) => ({ jsonrpc: "2.0", id, error: { code, message } });

  if (id === undefined || id === null) return null; // notificatie: geen antwoord
  switch (method) {
    case "initialize": {
      const v = SUPPORTED.includes(params?.protocolVersion) ? params.protocolVersion : SUPPORTED[0];
      return reply({
        protocolVersion: v,
        capabilities: { tools: {} },
        serverInfo: { name: "prgoeroes-monitor", version: "0.2.0" },
        instructions:
          "Mediamonitor van PR Goeroes (Jennifer Delano). Gebruik 'briefing' voor wat er recent verscheen, " +
          "'publicaties_zoeken' per klant, 'publicatie_toevoegen' voor links die Jennifer zelf vond, 'bron_toevoegen' " +
          "voor nieuwe media, en 'rapport_maken' voor het klantrapport. Verzin nooit bereik of advertentiewaarde: " +
          "die komen uit de database. Antwoord in het Nederlands.",
      });
    }
    case "ping":
      return reply({});
    case "tools/list":
      return reply({ tools: tools.map(({ name, description, inputSchema }) => ({ name, description, inputSchema })) });
    case "tools/call": {
      const tool = tools.find((t) => t.name === params?.name);
      if (!tool) return fail(-32602, `Onbekend gereedschap: ${params?.name}`);
      try {
        const db = new Db(env);
        const out: any = await tool.run(db, params?.arguments || {}, { reportBase: `${origin}/rapport` });
        if (out && typeof out.rapport_link === "string") {
          out.rapport_link = await signedReportLink(env, origin, out.rapport_link.split("?")[1] || "");
        }
        return reply({ content: [{ type: "text", text: JSON.stringify(out, null, 2) }] });
      } catch (e: any) {
        return reply({ content: [{ type: "text", text: `Fout: ${e?.message || e}` }], isError: true });
      }
    }
    default:
      return fail(-32601, `Methode niet ondersteund: ${method}`);
  }
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    const parts = url.pathname.split("/").filter(Boolean);

    if (parts[0] === "mcp") {
      if (!safeEqual(parts[1] || "", env.MCP_TOKEN)) return new Response("Niet gevonden", { status: 404 });
      if (req.method === "GET") return new Response("Method Not Allowed", { status: 405, headers: { Allow: "POST" } });
      if (req.method === "DELETE") return new Response(null, { status: 204 });
      if (req.method !== "POST") return new Response("Method Not Allowed", { status: 405 });
      let body: any;
      try {
        body = await req.json();
      } catch {
        return json({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Ongeldige JSON" } }, 400);
      }
      if (Array.isArray(body)) {
        const out = (await Promise.all(body.map((m) => handleRpc(m, env, url.origin)))).filter(Boolean);
        return out.length ? json(out) : new Response(null, { status: 202 });
      }
      const out = await handleRpc(body, env, url.origin);
      return out ? json(out) : new Response(null, { status: 202 });
    }

    if (parts[0] === "rapport" && req.method === "GET") {
      const q = new URLSearchParams(url.search);
      const sig = q.get("sig") || "";
      q.delete("sig");
      q.sort();
      if (!safeEqual(sig, await sign(env.MCP_TOKEN, q.toString()))) return new Response("Link ongeldig", { status: 403 });
      return renderReport(new Db(env), q);
    }

    return new Response("PR Goeroes monitor", { status: 200 });
  },
};
