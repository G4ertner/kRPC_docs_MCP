from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Iterable

from ..store.types import now_iso, calc_size_bytes, calc_loc
from .python_ast import (
    parse_python_module,
    ModuleSummary,
    AstFunction,
    AstClass,
    ConstBlock,
)
from .walk_repo import discover_python_files, WalkOptions


@dataclass
class Provenance:
    repo_url: str
    commit: str
    repo_root: Path
    rel_path: str


@dataclass
class ExtractOptions:
    include_functions: bool = True
    include_methods: bool = True
    include_classes: bool = True
    include_consts: bool = True
    default_license: str = "UNKNOWN"
    default_license_url: str = "about:blank"


def _hash_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def stable_id(repo: str, commit: str, rel_path: str, kind: str, qualname: str, lineno: int, end_lineno: int) -> str:
    key = "|".join([repo, commit, rel_path, kind, qualname, str(lineno), str(end_lineno)])
    return _hash_str(key)


def _param_names(params: List[str]) -> List[str]:
    names: List[str] = []
    for p in params:
        # Strip annotations after ':' and stars
        name = p.split(":", 1)[0].strip()
        name = name.lstrip("*")
        if name:
            names.append(name)
    return names


def _summarize_function(fn: AstFunction, rel_path: str) -> Tuple[str, str, List[str], List[str]]:
    name = fn.qualname
    desc = fn.docstring or fn.leading_comments or f"Extracted function {name} from {rel_path}"
    cats = ["method" if fn.is_method else "function"]
    inputs = _param_names(fn.params)
    return name, desc, cats, inputs


def _summarize_class(cls: AstClass, rel_path: str) -> Tuple[str, str, List[str]]:
    name = cls.qualname
    desc = cls.docstring or cls.leading_comments or f"Extracted class {name} from {rel_path}"
    cats = ["class"]
    return name, desc, cats


def _summarize_consts(cb: ConstBlock, rel_path: str) -> Tuple[str, str, List[str]]:
    name = "CONST_BLOCK"
    desc = f"Top-level constants: {', '.join(cb.assignments)}"
    cats = ["const"]
    return name, desc, cats


def _make_record(
    prov: Provenance,
    *,
    kind: str,
    qualname: str,
    lineno: int,
    end_lineno: int,
    code: str,
    name: str,
    description: str,
    categories: List[str],
    inputs: Optional[List[str]] = None,
    license: Optional[str] = None,
    license_url: Optional[str] = None,
) -> Dict[str, Any]:
    rid = stable_id(prov.repo_url, prov.commit, prov.rel_path, kind, qualname, lineno, end_lineno)
    record: Dict[str, Any] = {
        "id": rid,
        "repo": prov.repo_url,
        "commit": prov.commit,
        "path": prov.rel_path,
        "lang": "python",
        "name": name,
        "description": description,
        "code": code,
        "categories": categories,
        "dependencies": [],
        "license": license or "UNKNOWN",
        "license_url": license_url or "about:blank",
        "created_at": now_iso(),
        "size_bytes": calc_size_bytes(code),
        "lines_of_code": calc_loc(code),
    }
    if inputs:
        record["inputs"] = inputs
    return record


def detect_provenance(repo_root: Path) -> Optional[Tuple[str, str]]:
    # If this repo was fetched via B1, a fetch.json should be at the repo root
    manifest = repo_root / "fetch.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            repo_url = data.get("repo_url")
            commit = data.get("resolved_commit")
            if repo_url and commit:
                return str(repo_url), str(commit)
        except Exception:
            return None
    return None


def extract_from_module(prov: Provenance, mod: ModuleSummary, opts: ExtractOptions) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    if opts.include_functions:
        for fn in mod.functions:
            name, desc, cats, inputs = _summarize_function(fn, prov.rel_path)
            recs.append(
                _make_record(
                    prov,
                    kind=("method" if fn.is_method else "function"),
                    qualname=fn.qualname,
                    lineno=fn.lineno,
                    end_lineno=fn.end_lineno,
                    code=fn.code_span or "",
                    name=name,
                    description=desc,
                    categories=cats,
                    inputs=inputs,
                    license=opts.default_license,
                    license_url=opts.default_license_url,
                )
            )
    if opts.include_methods:
        for cls in mod.classes:
            for m in cls.methods:
                name, desc, cats, inputs = _summarize_function(m, prov.rel_path)
                recs.append(
                    _make_record(
                        prov,
                        kind="method",
                        qualname=m.qualname,
                        lineno=m.lineno,
                        end_lineno=m.end_lineno,
                        code=m.code_span or "",
                        name=name,
                        description=desc,
                        categories=cats,
                        inputs=inputs,
                        license=opts.default_license,
                        license_url=opts.default_license_url,
                    )
                )
    if opts.include_classes:
        for cls in mod.classes:
            name, desc, cats = _summarize_class(cls, prov.rel_path)
            recs.append(
                _make_record(
                    prov,
                    kind="class",
                    qualname=cls.qualname,
                    lineno=cls.lineno,
                    end_lineno=cls.end_lineno,
                    code=cls.code_span or "",
                    name=name,
                    description=desc,
                    categories=cats,
                    license=opts.default_license,
                    license_url=opts.default_license_url,
                )
            )
    if opts.include_consts and mod.const_blocks:
        # Only first block as per design
        cb = mod.const_blocks[0]
        name, desc, cats = _summarize_consts(cb, prov.rel_path)
        recs.append(
            _make_record(
                prov,
                kind="const",
                qualname=name,
                lineno=cb.lineno,
                end_lineno=cb.end_lineno,
                code=cb.code_span or "",
                name=name,
                description=desc,
                categories=cats,
                license=opts.default_license,
                license_url=opts.default_license_url,
            )
        )
    return recs


def extract_from_file(
    repo_root: Path,
    file_path: Path,
    *,
    repo_url: Optional[str] = None,
    commit: Optional[str] = None,
    opts: Optional[ExtractOptions] = None,
) -> List[Dict[str, Any]]:
    opts = opts or ExtractOptions()
    repo_root = repo_root.resolve()
    file_path = file_path.resolve()
    rel_path = str(file_path.relative_to(repo_root)).replace("\\", "/")

    # Determine provenance
    if not (repo_url and commit):
        det = detect_provenance(repo_root)
        if det:
            repo_url, commit = det
    if not (repo_url and commit):
        raise ValueError("Provenance missing: provide --repo-url and --commit or include fetch.json at repo root")

    mod = parse_python_module(file_path)
    if mod.parse_error:
        return []
    prov = Provenance(repo_url=repo_url, commit=commit, repo_root=repo_root, rel_path=rel_path)
    return extract_from_module(prov, mod, opts)


def extract_from_repo(
    repo_root: Path,
    *,
    repo_url: Optional[str] = None,
    commit: Optional[str] = None,
    opts: Optional[ExtractOptions] = None,
    walk_opts: Optional[WalkOptions] = None,
) -> List[Dict[str, Any]]:
    walk_opts = walk_opts or WalkOptions()
    files = discover_python_files(repo_root, walk_opts)
    out: List[Dict[str, Any]] = []
    for fi in files:
        out.extend(
            extract_from_file(
                repo_root,
                Path(fi.abs_path),
                repo_url=repo_url,
                commit=commit,
                opts=opts,
            )
        )
    return out

