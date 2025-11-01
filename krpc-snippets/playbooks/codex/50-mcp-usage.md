# MCP Usage

In chat:

```text
snippets_search("helper", k=5, mode="keyword")
snippets_search("helper", k=5, mode="hybrid", rerank=true)
snippets_get("<id>", include_code=false)
snippets_resolve(name="a.sample.NavHelper.circ_dv", max_bytes=25000, max_nodes=25)
snippets_search_and_resolve("NavHelper", k=5, mode="hybrid")
```

Resource:

```text
Fetch resource://snippets/usage for a quick tool summary.
```

Note:
- Hybrid/rerank use OpenAI when `OPENAI_API_KEY` is set; otherwise mock.
- You can also search FastMCP docs via mix_server to see available prompt/resource features.
