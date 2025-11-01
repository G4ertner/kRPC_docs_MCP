# Resolve & Bundle

```bash
SN=krpc-snippets/data/snippets_enriched.jsonl
[ -f "$SN" ] || SN=krpc-snippets/data/snippets_extracted.jsonl

# 1) Resolve by id
uv --directory . run python krpc-snippets/scripts/resolve_snippet.py \
  --snippets $SN --id <snippet_id> --out krpc-snippets/data/bundle.py

# 2) Resolve by name (module.qualname)
uv --directory . run python krpc-snippets/scripts/resolve_snippet.py \
  --snippets $SN --name a.sample.NavHelper.circ_dv --out krpc-snippets/data/bundle_navhelper.py

# Caps
#   --max-bytes 25000 --max-nodes 25
```
