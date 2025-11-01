from __future__ import annotations

import ast
import io
import tokenize
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class AstFunction:
    name: str
    qualname: str
    lineno: int
    end_lineno: int
    is_async: bool
    decorators: List[str]
    params: List[str]
    returns: Optional[str]
    docstring: Optional[str]
    leading_comments: Optional[str]
    is_method: bool = False
    parent_class: Optional[str] = None
    code_span: Optional[str] = None


@dataclass
class AstClass:
    name: str
    qualname: str
    lineno: int
    end_lineno: int
    bases: List[str]
    decorators: List[str]
    docstring: Optional[str]
    leading_comments: Optional[str]
    methods: List[AstFunction] = field(default_factory=list)
    code_span: Optional[str] = None


@dataclass
class ConstBlock:
    lineno: int
    end_lineno: int
    assignments: List[str]
    code_span: Optional[str] = None


@dataclass
class ModuleSummary:
    path: str
    encoding: str
    module_docstring: Optional[str]
    imports: List[str]
    from_imports: List[str]
    functions: List[AstFunction]
    classes: List[AstClass]
    const_blocks: List[ConstBlock]
    parse_error: Optional[str] = None


def _node_span(node: ast.AST) -> Tuple[int, int]:
    lineno = getattr(node, "lineno", None)
    end_lineno = getattr(node, "end_lineno", None)
    if lineno is None:
        lineno = 1
    if end_lineno is None:
        # Fallback: best-effort by descending into last child
        end_lineno = lineno
        for child in ast.walk(node):
            el = getattr(child, "end_lineno", None)
            if el is not None and el > end_lineno:
                end_lineno = el
    return int(lineno), int(end_lineno)


def _slice_code(lines: List[str], lineno: int, end_lineno: int) -> str:
    # Lines are 1-based; include end line
    start = max(1, lineno)
    end = max(start, end_lineno)
    return "".join(lines[start - 1 : end])


def _leading_comments_above(lines: List[str], start_line: int) -> Optional[str]:
    # Walk upwards gathering contiguous comment lines, allowing at most one blank line between
    i = start_line - 2  # index of the line above
    if i < 0:
        return None
    collected: List[str] = []
    blanks = 0
    while i >= 0:
        s = lines[i].rstrip("\n")
        if s.strip().startswith("#"):
            collected.append(s)
            i -= 1
            continue
        if s.strip() == "":
            blanks += 1
            if blanks <= 1:
                collected.append(s)
                i -= 1
                continue
        break
    if not collected:
        return None
    collected.reverse()
    # Trim leading/trailing blank lines in the collected block
    while collected and collected[0].strip() == "":
        collected.pop(0)
    while collected and collected[-1].strip() == "":
        collected.pop()
    return "\n".join(collected) if collected else None


def _unparse(node: ast.AST) -> Optional[str]:
    try:
        return ast.unparse(node)  # type: ignore[attr-defined]
    except Exception:
        return None


def _param_list(fn: ast.AST) -> List[str]:
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    a = fn.args
    out: List[str] = []
    # Positional-only (3.8+)
    for arg in getattr(a, "posonlyargs", []) or []:
        nm = arg.arg
        ann = _unparse(arg.annotation) if getattr(arg, "annotation", None) is not None else None
        out.append(f"{nm}: {ann}" if ann else nm)
    # Regular args
    for arg in a.args:
        nm = arg.arg
        ann = _unparse(arg.annotation) if getattr(arg, "annotation", None) is not None else None
        out.append(f"{nm}: {ann}" if ann else nm)
    # Vararg
    if a.vararg is not None:
        nm = "*" + a.vararg.arg
        ann = _unparse(a.vararg.annotation) if getattr(a.vararg, "annotation", None) is not None else None
        out.append(f"{nm}: {ann}" if ann else nm)
    # Kw-only
    for arg in a.kwonlyargs:
        nm = arg.arg
        ann = _unparse(arg.annotation) if getattr(arg, "annotation", None) is not None else None
        out.append(f"{nm}: {ann}" if ann else nm)
    # Kwarg
    if a.kwarg is not None:
        nm = "**" + a.kwarg.arg
        ann = _unparse(a.kwarg.annotation) if getattr(a.kwarg, "annotation", None) is not None else None
        out.append(f"{nm}: {ann}" if ann else nm)
    return out


def _collect_imports(mod: ast.Module) -> Tuple[List[str], List[str]]:
    imps: List[str] = []
    frs: List[str] = []
    for node in mod.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    imps.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                frs.append(node.module)
    # Deduplicate preserving order
    def dedup(xs: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    return dedup(imps), dedup(frs)


def _detect_const_blocks(mod: ast.Module, lines: List[str]) -> List[ConstBlock]:
    blocks: List[ConstBlock] = []
    cur_names: List[str] = []
    start: Optional[int] = None
    end: Optional[int] = None
    def is_upper_name(n: ast.AST) -> Optional[str]:
        if isinstance(n, ast.Name) and n.id.isupper():
            return n.id
        return None

    for node in mod.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            break  # stop at first code section beyond consts
        if isinstance(node, ast.Assign):
            names = []
            for t in node.targets:
                nm = is_upper_name(t)
                if nm:
                    names.append(nm)
            if names:
                if start is None:
                    start, end = _node_span(node)
                else:
                    _, end = _node_span(node)
                cur_names.extend(names)
                continue
        if isinstance(node, ast.AnnAssign):
            nm = is_upper_name(node.target)
            if nm:
                if start is None:
                    start, end = _node_span(node)
                else:
                    _, end = _node_span(node)
                cur_names.append(nm)
                continue
        # Non-const top-level node encountered while not started: ignore
        if start is not None:
            break

    if start is not None and end is not None and cur_names:
        code = _slice_code(lines, start, end)
        blocks.append(ConstBlock(lineno=start, end_lineno=end, assignments=cur_names, code_span=code))
    return blocks


def parse_python_module(path: Path) -> ModuleSummary:
    # Use tokenize.open to respect PEP 263 encoding cookie
    try:
        with tokenize.open(str(path)) as f:
            text = f.read()
            encoding = f.encoding or "utf-8"
    except Exception as e:
        return ModuleSummary(
            path=str(path),
            encoding="utf-8",
            module_docstring=None,
            imports=[],
            from_imports=[],
            functions=[],
            classes=[],
            const_blocks=[],
            parse_error=str(e),
        )

    lines = text.splitlines(True)
    try:
        mod = ast.parse(text)
    except SyntaxError as e:
        return ModuleSummary(
            path=str(path),
            encoding=encoding,
            module_docstring=None,
            imports=[],
            from_imports=[],
            functions=[],
            classes=[],
            const_blocks=[],
            parse_error=f"SyntaxError: {e}",
        )

    module_docstring = ast.get_docstring(mod)
    imports, from_imports = _collect_imports(mod)

    # Collect functions and classes (top-level only)
    functions: List[AstFunction] = []
    classes: List[AstClass] = []

    for node in mod.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lineno, end_lineno = _node_span(node)
            doc = ast.get_docstring(node)
            leading = _leading_comments_above(lines, lineno)
            decos = [_unparse(d) or "" for d in node.decorator_list]
            decos = [d for d in decos if d]
            params = _param_list(node)
            ret = _unparse(node.returns) if getattr(node, "returns", None) is not None else None
            fn = AstFunction(
                name=node.name,
                qualname=node.name,
                lineno=lineno,
                end_lineno=end_lineno,
                is_async=isinstance(node, ast.AsyncFunctionDef),
                decorators=decos,
                params=params,
                returns=ret,
                docstring=doc,
                leading_comments=leading,
                code_span=_slice_code(lines, lineno, end_lineno),
            )
            functions.append(fn)
        elif isinstance(node, ast.ClassDef):
            lineno, end_lineno = _node_span(node)
            doc = ast.get_docstring(node)
            leading = _leading_comments_above(lines, lineno)
            bases = [_unparse(b) or "" for b in node.bases]
            bases = [b for b in bases if b]
            decos = [_unparse(d) or "" for d in node.decorator_list]
            decos = [d for d in decos if d]
            cls = AstClass(
                name=node.name,
                qualname=node.name,
                lineno=lineno,
                end_lineno=end_lineno,
                bases=bases,
                decorators=decos,
                docstring=doc,
                leading_comments=leading,
                code_span=_slice_code(lines, lineno, end_lineno),
            )
            # Methods
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    l2, e2 = _node_span(child)
                    doc2 = ast.get_docstring(child)
                    leading2 = _leading_comments_above(lines, l2)
                    decos2 = [_unparse(d) or "" for d in child.decorator_list]
                    decos2 = [d for d in decos2 if d]
                    params2 = _param_list(child)
                    ret2 = _unparse(child.returns) if getattr(child, "returns", None) is not None else None
                    fn2 = AstFunction(
                        name=child.name,
                        qualname=f"{node.name}.{child.name}",
                        lineno=l2,
                        end_lineno=e2,
                        is_async=isinstance(child, ast.AsyncFunctionDef),
                        decorators=decos2,
                        params=params2,
                        returns=ret2,
                        docstring=doc2,
                        leading_comments=leading2,
                        is_method=True,
                        parent_class=node.name,
                        code_span=_slice_code(lines, l2, e2),
                    )
                    cls.methods.append(fn2)
            classes.append(cls)

    const_blocks = _detect_const_blocks(mod, lines)

    return ModuleSummary(
        path=str(path),
        encoding=encoding,
        module_docstring=module_docstring,
        imports=imports,
        from_imports=from_imports,
        functions=functions,
        classes=classes,
        const_blocks=const_blocks,
    )

