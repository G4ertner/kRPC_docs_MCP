# Setup

```bash
# Create and activate venv
uv venv
source .venv/bin/activate

# Install project
uv pip install -e .

# Optional: enable OpenAI support for live summarise/embeddings/rerank
# uv pip install -e .[enrich]

# Environment (optional live mode)
# export OPENAI_API_KEY=sk-...
```
