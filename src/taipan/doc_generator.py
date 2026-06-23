"""
Taipan Documentation Generator
================================
Extracts documentation from Taipan source code and generates Markdown.

Supports:
  - Function documentation (extracts comment before function)
  - Class documentation (extracts comment before class)
  - Module documentation (overview)
  - Cross-references

Usage:
    tai doc <file.tp>           # Generate markdown for a file
    tai doc <file.tp> --output docs.md   # Save to file

Doc comments:
    // This is a regular comment (not extracted)
    /// This is a doc comment (extracted for documentation)
    
    func greet(name: String) -> String {
        return f"Hello, {name}!"
    }
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict

from taipan.compiler.lexer.lexer import Lexer
from taipan.compiler.lexer.tokens import TokenType
from taipan.compiler.parser.parser import Parser
from taipan.compiler.ast.nodes import (
    Node, Program, FunctionDecl, ClassDecl, VariableDecl, ConstDecl,
    Identifier, Block, Param,
)


class DocItem:
    """A documented item in the source code."""
    def __init__(self, name: str, kind: str, doc: str, signature: str = "",
                 line: int = 0, params: List[Param] = None, return_type: Optional[str] = None):
        self.name = name
        self.kind = kind  # "function", "class", "variable", "constant"
        self.doc = doc
        self.signature = signature
        self.line = line
        self.params = params or []
        self.return_type = return_type


def extract_doc_comments(source: str) -> Dict[int, str]:
    """
    Extract doc comments (/// or // immediately before declarations).
    Returns: {line_number: comment_text}
    """
    lines = source.splitlines()
    doc_comments = {}
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("///"):
            # Doc comment
            comment_text = stripped[3:].strip()
            # Associate with next non-empty, non-comment line
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith("//"):
                    doc_comments[j + 1] = comment_text  # line numbers are 1-indexed
                    break
        elif stripped.startswith("//") and not stripped.startswith("///"):
            # Regular comment - might be doc if directly before declaration
            comment_text = stripped[2:].strip()
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith("//"):
                    # Check if next line starts with func, class, let, const
                    if any(next_line.startswith(kw) for kw in ["func", "class", "let", "const"]):
                        if (j + 1) not in doc_comments:  # Don't overwrite /// comments
                            doc_comments[j + 1] = comment_text
                    break
    
    return doc_comments


def generate_docs(ast: Program, source: str, filename: str = "") -> str:
    """Generate Markdown documentation from a Taipan AST."""
    doc_comments = extract_doc_comments(source)
    items: List[DocItem] = []
    
    # Walk AST and extract documented items
    for stmt in ast.body:
        line = getattr(stmt, 'line', 0)
        doc = doc_comments.get(line, "")
        
        match stmt:
            case FunctionDecl():
                params_str = ", ".join(
                    f"{p.name}: {p.type_hint}" if p.type_hint else p.name
                    for p in stmt.params
                )
                sig = f"func {stmt.name}({params_str})"
                if stmt.return_type:
                    sig += f" -> {stmt.return_type}"
                
                items.append(DocItem(
                    name=stmt.name,
                    kind="function",
                    doc=doc,
                    signature=sig,
                    line=line,
                    params=stmt.params,
                    return_type=stmt.return_type,
                ))
            
            case ClassDecl():
                items.append(DocItem(
                    name=stmt.name,
                    kind="class",
                    doc=doc,
                    signature=f"class {stmt.name}" + (f" extends {stmt.superclass}" if stmt.superclass else ""),
                    line=line,
                ))
            
            case VariableDecl():
                items.append(DocItem(
                    name=stmt.name,
                    kind="variable",
                    doc=doc,
                    signature=f"let {stmt.name}: {stmt.type_hint}" if stmt.type_hint else f"let {stmt.name}",
                    line=line,
                ))
            
            case ConstDecl():
                items.append(DocItem(
                    name=stmt.name,
                    kind="constant",
                    doc=doc,
                    signature=f"const {stmt.name}",
                    line=line,
                ))
    
    # Generate Markdown
    parts = []
    
    # Header
    title = Path(filename).stem if filename else "Module Documentation"
    parts.append(f"# {title}")
    parts.append("")
    
    if filename:
        parts.append(f"*Source: `{filename}`*")
        parts.append("")
    
    # Module overview (if there's a top-level comment)
    module_doc = doc_comments.get(1, "")
    if module_doc:
        parts.append(module_doc)
        parts.append("")
    
    # Table of contents
    if items:
        parts.append("## Table of Contents")
        parts.append("")
        for item in items:
            anchor = f"{item.kind}-{item.name}"
            parts.append(f"- [{item.name}](#{anchor}) — {item.kind}")
        parts.append("")
    
    # Functions
    functions = [i for i in items if i.kind == "function"]
    if functions:
        parts.append("## Functions")
        parts.append("")
        for f in functions:
            parts.append(f"### <a id=\"function-{f.name}\"></a> `{f.signature}`")
            parts.append("")
            if f.doc:
                parts.append(f.doc)
                parts.append("")
            if f.params:
                parts.append("**Parameters:**")
                parts.append("")
                for p in f.params:
                    type_str = f"`: {p.type_hint}`" if p.type_hint else ""
                    default_str = f" (default: {p.default})" if p.default else ""
                    parts.append(f"- `{p.name}`{type_str}{default_str}")
                parts.append("")
            if f.return_type:
                parts.append(f"**Returns:** `{f.return_type}`")
                parts.append("")
            parts.append("")
    
    # Classes
    classes = [i for i in items if i.kind == "class"]
    if classes:
        parts.append("## Classes")
        parts.append("")
        for c in classes:
            parts.append(f"### <a id=\"class-{c.name}\"></a> `{c.signature}`")
            parts.append("")
            if c.doc:
                parts.append(c.doc)
                parts.append("")
            parts.append("")
    
    # Variables
    variables = [i for i in items if i.kind in ("variable", "constant")]
    if variables:
        parts.append("## Variables & Constants")
        parts.append("")
        for v in variables:
            parts.append(f"### <a id=\"{v.kind}-{v.name}\"></a> `{v.signature}`")
            parts.append("")
            if v.doc:
                parts.append(v.doc)
                parts.append("")
            parts.append("")
    
    return "\n".join(parts)


def main(filepath: str, output: Optional[str] = None) -> int:
    """Generate documentation for a Taipan file."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: File '{filepath}' not found.", file=sys.stderr)
        return 1
    
    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1
    
    try:
        tokens = Lexer(source, str(path)).tokenize()
        ast = Parser(tokens, str(path)).parse()
    except Exception as e:
        print(f"Error parsing file: {e}", file=sys.stderr)
        return 1
    
    docs = generate_docs(ast, source, str(path))
    
    if output:
        output_path = Path(output)
        output_path.write_text(docs, encoding="utf-8")
        print(f"Documentation written to {output_path}")
    else:
        print(docs)
    
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Taipan Documentation Generator")
    parser.add_argument("file", help="Taipan source file to document")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    args = parser.parse_args()
    sys.exit(main(args.file, args.output))
