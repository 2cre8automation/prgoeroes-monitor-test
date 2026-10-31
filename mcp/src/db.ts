// Kleine Supabase (PostgREST) helper voor de Worker.

export interface Env {
  SUPABASE_URL: string;
  SUPABASE_SERVICE_ROLE_KEY: string;
  MCP_TOKEN: string;
}

export class Db {
  constructor(private env: Env) {}

  private async req(method: string, path: string, body?: unknown, prefer?: string): Promise<any> {
    const res = await fetch(`${this.env.SUPABASE_URL.replace(/\/$/, "")}/rest/v1/${path}`, {
      method,
      headers: {
        apikey: this.env.SUPABASE_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${this.env.SUPABASE_SERVICE_ROLE_KEY}`,
        "Content-Type": "application/json",
        ...(prefer ? { Prefer: prefer } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await res.text();
    if (!res.ok) throw new Error(`Database-fout ${res.status}: ${text.slice(0, 300)}`);
    return text ? JSON.parse(text) : null;
  }

  get(path: string) {
    return this.req("GET", path);
  }
  insert(table: string, rows: unknown, onConflict?: string, mode: "ignore" | "merge" | "none" = "none") {
    const q = onConflict ? `?on_conflict=${onConflict}` : "";
    const prefer = ["return=representation"];
    if (mode === "ignore") prefer.push("resolution=ignore-duplicates");
    if (mode === "merge") prefer.push("resolution=merge-duplicates");
    return this.req("POST", `${table}${q}`, rows, prefer.join(","));
  }
  update(table: string, filter: string, values: unknown) {
    return this.req("PATCH", `${table}?${filter}`, values, "return=representation");
  }
}

export const enc = encodeURIComponent;

export async function findClient(db: Db, name: string): Promise<any | null> {
  const exact = await db.get(`clients?name=ilike.${enc(name)}&select=*`);
  if (exact.length) return exact[0];
  const fuzzy = await db.get(`clients?name=ilike.*${enc(name)}*&select=*`);
  return fuzzy.length === 1 ? fuzzy[0] : null;
}
