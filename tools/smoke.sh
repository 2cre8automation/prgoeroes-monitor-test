#!/usr/bin/env bash
# Rooktest van de live MCP-server. Schrijft resultaat zonder token.
set -u
M="$MCP_BASE/mcp/$MCP_TOKEN"
call() { curl -s -m 60 "$M" -H 'content-type: application/json' -d "$1"; }
echo "== initialize"; call '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}' | head -c 300; echo
echo "== tools/list"; call '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | python3 -c "import json,sys;print([t['name'] for t in json.load(sys.stdin)['result']['tools']])"
tool() { echo "== $1"; call "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"$1\",\"arguments\":$2}}" | python3 -c "import json,sys;r=json.load(sys.stdin);print(r['result']['content'][0]['text'][:${3:-1500}])"; }
tool klanten_lijst '{"lijst":"vast"}' 600
tool publicaties_zoeken '{"klant":"Aspyre","van":"2026-10-01","tot":"2026-10-31"}' 1500
tool briefing '{"dagen":3}' 800
tool bronnen_lijst '{}' 800
echo "== rapport_maken"
LINK=$(call '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"rapport_maken","arguments":{"klant":"Katapull","van":"2026-10-01","tot":"2026-10-31"}}}' | python3 -c "import json,sys;d=json.loads(json.load(sys.stdin)['result']['content'][0]['text']);print(json.dumps(d['totaal']));print(d['rapport_link'])")
echo "$LINK"
echo "rapport http: $(curl -s -o /dev/null -w '%{http_code}' "$(echo "$LINK" | tail -1)")"
echo "fout token http: $(curl -s -o /dev/null -w '%{http_code}' -X POST "$MCP_BASE/mcp/fout" -d '{}')"
