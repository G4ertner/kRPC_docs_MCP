from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .python_ast import parse_python_module
from .walk_repo import WalkOptions, discover_python_files


def modulize_rel_path(rel_path: str) -> str:
    p = rel_path.replace("\\", "/")
    if p.endswith("/__init__.py"):
        p = p[: -len("/__init__.py")]
    elif p.endswith(".py"):
        p = p[: -len(".py")]
    return p.replace("/", ".")


@dataclass
class Symbol:
    module: str
    kind: str  # function|method|class
    qualname: str  # local qualname within module e.g., fn, Class.method
    path: str   # repo-relative path (POSIX)


def build_symbol_index(repo_root: Path) -> Dict[str, Symbol]:
    repo_root = repo_root.resolve()
    idx: Dict[str, Symbol] = {}
    for fi in discover_python_files(repo_root, WalkOptions()):
        rel = fi.rel_path
        modname = modulize_rel_path(rel)
        summ = parse_python_module(Path(fi.abs_path))
        if summ.parse_error:
            continue
        for fn in summ.functions:
            fq = f"{modname}.{fn.name}"
            idx[fq] = Symbol(module=modname, kind=("method" if fn.is_method else "function"), qualname=fn.name, path=rel)
        for cls in summ.classes:
            fq = f"{modname}.{cls.name}"
            idx[fq] = Symbol(module=modname, kind="class", qualname=cls.name, path=rel)
            for m in cls.methods:
                fq2 = f"{modname}.{cls.name}.{m.name}"
                idx[fq2] = Symbol(module=modname, kind="method", qualname=f"{cls.name}.{m.name}", path=rel)
    return idx


def _alias_map(mod: ast.Module) -> Dict[str, str]:
    amap: Dict[str, str] = {}
    for node in mod.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    amap[a.asname] = a.name
                else:
                    root = a.name.split(".")[0]
                    amap[root] = root
                    # also map full dotted name to itself for convenience
                    amap[a.name] = a.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            for a in node.names:
                tgt = f"{base}.{a.name}" if base else a.name
                alias = a.asname or a.name
                amap[alias] = tgt
    return amap


def _dotted_from_attr(node: ast.AST) -> Optional[str]:
    parts: List[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        parts.reverse()
        return ".".join(parts)
    return None


def analyze_module_calls(path: Path) -> Tuple[str, Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Return (module_name, calls_map, class_to_methods) for a module.

    calls_map: qualname -> set of dotted candidate symbols (unresolved to repo-local yet)
    class_to_methods: class_name -> set of method names
    """
    text = Path(path).read_text(encoding="utf-8")
    mod = ast.parse(text)
    amap = _alias_map(mod)
    module_name = modulize_rel_path(str(Path(path)))  # absolute path, will be reduced later
    # Correct module_name to repo-relative by stripping repo root later
    calls: Dict[str, Set[str]] = {}
    class_methods: Dict[str, Set[str]] = {}

    # Build class methods registry
    for node in mod.body:
        if isinstance(node, ast.ClassDef):
            mset: Set[str] = set()
            for ch in node.body:
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    mset.add(ch.name)
            class_methods[node.name] = mset

    def add_call(qn: str, sym: str) -> None:
        calls.setdefault(qn, set()).add(sym)

    class FnVisitor(ast.NodeVisitor):
        def __init__(self, qn: str, cls: Optional[str] = None) -> None:
            self.qn = qn
            self.cls = cls

        def visit_Call(self, node: ast.Call) -> None:
            target = node.func
            dotted: Optional[str] = None
            if isinstance(target, ast.Name):
                nm = target.id
                if nm in amap:
                    dotted = amap[nm]
                else:
                    # Local function name
                    dotted = nm
            elif isinstance(target, ast.Attribute):
                d = _dotted_from_attr(target)
                if d:
                    dotted = d
                    # Resolve root alias if any
                    root = d.split(".")[0]
                    if root in amap:
                        dotted = amap[root] + "." + ".".join(d.split(".")[1:])
                    elif root == "self" and self.cls:
                        dotted = f"{self.cls}." + ".".join(d.split(".")[1:])
                # else leave None
            if dotted:
                add_call(self.qn, dotted)
            self.generic_visit(node)

    for node in mod.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qn = node.name
            FnVisitor(qn).visit(node)
        elif isinstance(node, ast.ClassDef):
            for ch in node.body:
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qn = f"{node.name}.{ch.name}"
                    FnVisitor(qn, cls=node.name).visit(ch)

    return module_name, calls, class_methods


def resolve_dependencies(
    repo_root: Path,
    *,
    symbol_index: Dict[str, Symbol],
) -> Dict[Tuple[str, str], Set[str]]:
    """Return mapping {(rel_path, qualname)} -> set of resolved repo-local symbols (module.qualname).
    """
    repo_root = repo_root.resolve()
    dep_map: Dict[Tuple[str, str], Set[str]] = {}
    files = discover_python_files(repo_root, WalkOptions())
    for fi in files:
        abs_p = Path(fi.abs_path)
        rel = fi.rel_path
        modname = modulize_rel_path(rel)
        try:
            _, calls_map, class_methods = analyze_module_calls(abs_p)
        except Exception:
            continue
        # Post-process calls_map to fully qualified names and keep only repo-local
        for qn, cset in calls_map.items():
            resolved: Set[str] = set()
            for cand in cset:
                if cand.startswith("self.") and "." in qn:
                    # Already rewritten in analyze when root==self
                    pass
                # Normalize to fully-qualified with module prefix if needed
                if "." not in cand or cand.split(".")[0] in ("self",):
                    fq = f"{modname}.{cand.replace('self.', '')}"
                else:
                    fq = cand
                # Keep only repo-local symbols
                if fq in symbol_index:
                    resolved.add(fq)
            dep_map[(rel, qn)] = resolved
        # Classes aggregate method deps
        for cls, methods in class_methods.items():
            agg: Set[str] = set()
            for m in methods:
                agg |= dep_map.get((rel, f"{cls}.{m}"), set())
            dep_map[(rel, cls)] = agg
    return dep_map


def attach_deps_to_records(records: List[Dict[str, any]], dep_map: Dict[Tuple[str, str], Set[str]]) -> List[Dict[str, any]]:
    out: List[Dict[str, any]] = []
    for r in records:
        rel = r.get("path")
        name = r.get("name")
        deps = sorted(dep_map.get((rel, name), set()))
        r2 = dict(r)
        r2["dependencies"] = deps
        out.append(r2)
    return out

