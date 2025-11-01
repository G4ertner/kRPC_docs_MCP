from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class SummarizerConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_output_tokens: int = 400
    batch_size: int = 10
    mock: bool = False
    cache_dir: Path = Path("krpc-snippets/data/enrich_cache")
    only_if_empty: bool = True


PROMPT_VERSION = "v1"


def _cache_path(cfg: SummarizerConfig, snip_id: str) -> Path:
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    name = f"{snip_id}.{PROMPT_VERSION}.{cfg.model.replace('/', '_')}.json"
    return cfg.cache_dir / name


def _prompt_for_record(rec: Dict) -> str:
    name = rec.get("name") or "(unknown)"
    code = rec.get("code", "")
    # Keep prompt size bounded
    code_trunc = code[:4000]
    context = {
        "name": name,
        "existing_description": rec.get("description") or "",
        "existing_categories": rec.get("categories") or [],
        "inputs": rec.get("inputs") or [],
        "code": code_trunc,
    }
    return json.dumps(context, ensure_ascii=False)


def _build_messages(rec: Dict) -> List[Dict[str, str]]:
    sys_prompt = (
        "You are a code librarian for kRPC/KSP snippets. Summarize the snippet in concise,"
        " unambiguous terms and return strict JSON with keys: description (<= 2 sentences),"
        " categories (array; reuse existing if good; typical: ['ascent','circularisation','landing','navigation','telemetry','control','pid','math','examples']),"
        " inputs (array of parameter names), outputs (array of return values or empty), when_to_use (one sentence)."
    )
    user_prompt = (
        "Context JSON follows. Produce ONLY a JSON object, no prose.\n" + _prompt_for_record(rec)
    )
    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _openai_client_or_none():
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def _call_openai(client, cfg: SummarizerConfig, rec: Dict) -> Optional[Dict]:
    try:
        resp = client.chat.completions.create(
            model=cfg.model,
            temperature=cfg.temperature,
            messages=_build_messages(rec),
            response_format={"type": "json_object"},
            max_tokens=cfg.max_output_tokens,
        )
        txt = resp.choices[0].message.content or "{}"
        return json.loads(txt)
    except Exception:
        return None


def _mock_summary(rec: Dict) -> Dict:
    cats = rec.get('categories') or ["snippet"]
    desc = rec.get("description") or f"Extracted {cats[0]} {rec.get('name')}"
    cats = rec.get("categories") or ["snippet"]
    inputs = rec.get("inputs") or []
    return {
        "description": desc,
        "categories": cats,
        "inputs": inputs,
        "outputs": [],
        "when_to_use": "When the described behavior is needed in a kRPC/KSP mission step.",
    }


def _merge_fields(rec: Dict, enriched: Dict, *, only_if_empty: bool) -> Dict:
    out = dict(rec)
    # Always keep categories from enriched if present and non-empty
    if enriched.get("categories"):
        out["categories"] = enriched["categories"]
    # Merge description
    if (not only_if_empty) or (not (out.get("description") or "").strip()):
        if enriched.get("description"):
            out["description"] = enriched["description"]
    # Inputs/outputs/when_to_use
    if enriched.get("inputs") is not None:
        out["inputs"] = enriched.get("inputs") or out.get("inputs")
    if enriched.get("outputs") is not None:
        out["outputs"] = enriched.get("outputs")
    if enriched.get("when_to_use"):
        out["when_to_use"] = enriched["when_to_use"]
    return out


def summarise_snippets(snippets: List[Dict], cfg: Optional[SummarizerConfig] = None) -> List[Dict]:
    cfg = cfg or SummarizerConfig()
    client = None if cfg.mock else _openai_client_or_none()
    out: List[Dict] = []
    for rec in snippets:
        # Skip if only_if_empty and description already exists
        if cfg.only_if_empty and (rec.get("description") or "").strip():
            out.append(rec)
            continue
        cache_file = _cache_path(cfg, rec.get("id", hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()))
        enriched: Optional[Dict] = None
        if cache_file.exists():
            try:
                enriched = json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                enriched = None
        if enriched is None:
            if client is not None:
                enriched = _call_openai(client, cfg, rec)
            if enriched is None:
                enriched = _mock_summary(rec)
            try:
                cache_file.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass
        out.append(_merge_fields(rec, enriched, only_if_empty=cfg.only_if_empty))
    return out
