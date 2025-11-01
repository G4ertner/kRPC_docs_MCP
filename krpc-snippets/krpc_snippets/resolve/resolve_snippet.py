from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from krpc_snippets.ingest.deps import modulize_rel_path


@dataclass
class ResolveResult:
    bundle_code: str
    include_ids: List[str]
    unresolved_deps: List[str]
    truncated: bool
    stats: Dict[str, int]


def _load_snippets(path: Path) -> Tuple[List[Dict], Dict[str, Dict], Dict[str, Dict]]:
    recs: List[Dict] = []
    id_map: Dict[str, Dict] = {}
    sym_map: Dict[str, Dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        recs.append(r)
        rid = r.get("id")
        if rid:
            id_map[rid] = r
        # Build symbol map
        mod = modulize_rel_path(str(r.get("path", "")).replace("\\", "/"))
        name = str(r.get("name", ""))
        if name:
            sym = f"{mod}.{name}"
            sym_map[sym] = r
    return recs, id_map, sym_map


def _const_record_for_module(recs: List[Dict], module: str) -> Optional[Dict]:
    # Find a record with category 'const' and matching module
    for r in recs:
        if (r.get("categories") or [None])[0] == "const":
            mod_r = modulize_rel_path(str(r.get("path", "")).replace("\\", "/"))
            if mod_r == module:
                return r
    return None


def _symbol_key(rec: Dict) -> str:
    mod = modulize_rel_path(str(rec.get("path", "")).replace("\\", "/"))
    return f"{mod}.{rec.get('name')}"


def _class_symbol_from_method_symbol(symbol: str) -> Optional[str]:
    # Convert module.Class.method -> module.Class
    parts = symbol.split(".")
    if len(parts) >= 3:
        return ".".join(parts[:-1])
    return None


def _deps_for(rec: Dict) -> List[str]:
    deps = []
    for d in rec.get("dependencies") or []:
        d = str(d)
        # If method dependency, depend on its class to ensure runnable code
        cls_sym = _class_symbol_from_method_symbol(d)
        deps.append(cls_sym or d)
    # If target is a method itself, include its parent class
    cat = (rec.get("categories") or [None])[0]
    if cat == "method":
        sym = _symbol_key(rec)
        cls_sym = _class_symbol_from_method_symbol(sym)
        if cls_sym:
            deps.append(cls_sym)
    return list(dict.fromkeys(deps))


def _dfs_collect(
    sym: str,
    *,
    sym_map: Dict[str, Dict],
    visiting: Set[str],
    visited: Set[str],
    order: List[str],
    unresolved: Set[str],
    size_cap_nodes: int,
) -> None:
    if sym in visited:
        return
    if sym in visiting:
        return  # cycle, ignore
    if len(order) >= size_cap_nodes:
        return
    rec = sym_map.get(sym)
    if not rec:
        unresolved.add(sym)
        return
    visiting.add(sym)
    for dep in _deps_for(rec):
        _dfs_collect(dep, sym_map=sym_map, visiting=visiting, visited=visited, order=order, unresolved=unresolved, size_cap_nodes=size_cap_nodes)
        if len(order) >= size_cap_nodes:
            break
    visiting.remove(sym)
    visited.add(sym)
    if sym not in order:
        order.append(sym)


def build_dep_graph(
    target_rec: Dict,
    recs: List[Dict],
    id_map: Dict[str, Dict],
    sym_map: Dict[str, Dict],
    *,
    size_cap_bytes: int = 25000,
    size_cap_nodes: int = 25,
) -> Tuple[List[str], List[str], bool]:
    # Collect symbols in dependency order
    order_syms: List[str] = []
    unresolved: Set[str] = set()
    visiting: Set[str] = set()
    visited: Set[str] = set()

    target_sym = _symbol_key(target_rec)
    # If target is method, pivot to parent class for emission
    if (target_rec.get("categories") or [None])[0] == "method":
        cls_sym = _class_symbol_from_method_symbol(target_sym)
        if cls_sym and cls_sym in sym_map:
            target_sym = cls_sym

    _dfs_collect(target_sym, sym_map=sym_map, visiting=visiting, visited=visited, order=order_syms, unresolved=unresolved, size_cap_nodes=size_cap_nodes)

    # Include const block for each module in order
    to_emit_syms: List[str] = []
    seen_modules: Set[str] = set()
    for sym in order_syms:
        rec = sym_map.get(sym)
        if not rec:
            continue
        mod = modulize_rel_path(str(rec.get("path", "")).replace("\\", "/"))
        if mod not in seen_modules:
            cst = _const_record_for_module(recs, mod)
            if cst:
                cst_sym = _symbol_key(cst)
                if cst_sym not in to_emit_syms:
                    to_emit_syms.append(cst_sym)
            seen_modules.add(mod)
        if sym not in to_emit_syms:
            to_emit_syms.append(sym)

    # Enforce size cap by bytes of concatenated code
    included_ids: List[str] = []
    total_bytes = 0
    truncated = False
    for sym in to_emit_syms:
        rec = sym_map.get(sym)
        if not rec:
            continue
        rid = rec.get("id")
        code = (rec.get("code") or "").encode("utf-8")
        if rid in included_ids:
            continue
        if total_bytes + len(code) > size_cap_bytes:
            truncated = True
            break
        included_ids.append(rid)
        total_bytes += len(code)

    return included_ids, sorted(unresolved), truncated


def assemble_bundle(include_ids: List[str], id_map: Dict[str, Dict]) -> str:
    parts: List[str] = []
    for rid in include_ids:
        rec = id_map.get(rid)
        if not rec:
            continue
        cat = (rec.get("categories") or [None])[0]
        mod = modulize_rel_path(str(rec.get("path", "")).replace("\\", "/"))
        name = rec.get("name")
        header = f"# --- {cat}: {mod} ({name})\n"
        code = rec.get("code") or ""
        parts.append(header + code.rstrip() + "\n\n")
    return "".join(parts)


def resolve_snippet(
    *,
    target_id: Optional[str] = None,
    target_name: Optional[str] = None,
    snippets_path: Path,
    size_cap_bytes: int = 25000,
    size_cap_nodes: int = 25,
    emit_map: bool = False,
) -> ResolveResult:
    recs, id_map, sym_map = _load_snippets(snippets_path)
    target_rec: Optional[Dict] = None
    if target_id:
        target_rec = id_map.get(target_id)
    elif target_name:
        # target_name is module.qualname
        target_rec = sym_map.get(target_name)
    if not target_rec:
        raise ValueError("Target snippet not found by id or name")

    include_ids, unresolved, truncated = build_dep_graph(target_rec, recs, id_map, sym_map, size_cap_bytes=size_cap_bytes, size_cap_nodes=size_cap_nodes)
    bundle = assemble_bundle(include_ids, id_map)
    stats = {"nodes": len(include_ids), "bytes": len(bundle.encode("utf-8"))}
    return ResolveResult(bundle_code=bundle, include_ids=include_ids, unresolved_deps=unresolved, truncated=truncated, stats=stats)
