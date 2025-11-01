# Troubleshooting

Common issues
- Missing data files
  - Ensure `krpc-snippets/data/snippets_enriched.jsonl` or `snippets_extracted.jsonl` exist for search/resolve.
  - Build the keyword index: `uv --directory . run python krpc-snippets/scripts/search_keyword.py build --in krpc-snippets/data/snippets_enriched.jsonl --out krpc-snippets/data/keyword_index.json`.
- `No module named 'krpc_snippets'` in MCP tools
  - The server adds `krpc-snippets` to `sys.path`. If you moved folders, re‑run the MCP server so it picks up paths, or install editable: `uv pip install -e .`.
- OpenAI API key behavior
  - Put the key directly after `=` with no quotes, e.g., `OPENAI_API_KEY=sk-...`.
  - Mock mode is used automatically when the key is not set.
- License policy failures
  - Add `--exclude-restricted` to search CLIs or MCP tools to hide GPL‑family results.
  - For ingestion, run the license audit to identify restricted items: `uv --directory . run python krpc-snippets/scripts/audit_licenses.py --snippets krpc-snippets/data/snippets_enriched.jsonl --report krpc-snippets/data/license_audit.json`.
- Resolver truncation
  - Increase caps with `--max-bytes` or `--max-nodes` when bundles are large; unresolved items are listed in the output.

Getting help
- Check the playbooks under `krpc-snippets/playbooks/codex/` for step‑by‑step commands.
- Use `--help` on any script for flags and examples.

