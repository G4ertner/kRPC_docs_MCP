# Knowledge Tools (kRPC Docs + KSP Wiki)

These prompts describe concise, input/output–focused usage of the existing knowledge tools in the MCP server. They align with the repository’s structure where knowledge endpoints are commonly exposed as `wiki.search`, `wiki.get`, `krpc_docs.search`, and `krpc_docs.get`. Adjust tool names if your `mcp_server/tools.py` registers different identifiers.

---

## 1) Search (Docs or Wiki)

**Intent:** Find the best pages before fetching details.

**Call**
```json
{
  "tool": "wiki.search",               // or "krpc_docs.search"
  "args": { "query": "gravity turn kerbin" }
}
```

**Return**
```json
{
  "results": [
    { "id": "gravity_turn", "title": "Gravity Turn", "url": "https://..." , "summary": "..." },
    { "id": "ascent_profiles", "title": "Ascent Profiles", "url": "https://..." , "summary": "..." }
  ]
}
```

**Agent action:** Pick 1–3 hits, then call `get`.

---

## 2) Get Page (Docs or Wiki)

**Intent:** Pull structured content for planning/coding.

**Call**
```json
{
  "tool": "wiki.get",                  // or "krpc_docs.get"
  "args": { "id": "gravity_turn" }     // supports id/slug/title based on server
}
```

**Return**
```json
{
  "title": "Gravity Turn",
  "url": "https://...",
  "sections": [
    { "heading": "Overview", "markdown": "..." },
    { "heading": "Recommended Profile", "markdown": "..." }
  ],
  "tables": [
    { "name": "Kerbin Atmosphere", "rows": [{ "alt_km": 10, "density": 0.413 }, ...] }
  ],
  "facts": {
    "sea_level_g": 9.81,
    "lko_delta_v_mps": 3500
  }
}
```

**Agent action:** Quote only the minimum facts/tables needed; keep links for traceability.

---

## 3) Usage Pattern

1. **Search** for target pages in the appropriate source (kRPC docs or KSP wiki).
2. **Get** the best match by `id`/`slug`.
3. Extract only the **minimal facts** required for reasoning and code generation.
4. Preserve the **source URL** for audits and debugging.

---

## 4) Examples (Drop-in)

### Example A — Gravity Turn (Wiki)
```json
{ "tool": "wiki.search", "args": { "query": "gravity turn kerbin" } }
```
→ choose `gravity_turn`

```json
{ "tool": "wiki.get", "args": { "id": "gravity_turn" } }
```

### Example B — Maneuver Node (kRPC Docs)
```json
{ "tool": "krpc_docs.search", "args": { "query": "maneuver node api" } }
```
→ choose `maneuver_node`

```json
{ "tool": "krpc_docs.get", "args": { "id": "maneuver_node" } }
```

---

## 5) Return Shape Guarantees (Target)

- All **search** calls return an array `results[]` with `{ id, title, url, summary }`.
- All **get** calls return `{ title, url, sections[], tables[], facts{} }` when available.
- Missing fields **MAY** be omitted; treat them as unknown, not zero.
- Always pass through raw links for inspection in logs or debugging.

---

## 6) Agent Checklist (Knowledge)

- [ ] Pick the **right source**: `krpc_docs` for API usage, `wiki` for gameplay/physics/parts.
- [ ] Perform **search** first, then **get**.
- [ ] Extract **minimal facts**; avoid over-quoting.
- [ ] Keep **URLs** for auditability.
- [ ] Use extracted knowledge to **constrain** plan and code (TWR, Δv budgets, atmosphere rules).
