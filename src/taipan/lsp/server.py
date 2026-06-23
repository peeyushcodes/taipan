"""
Taipan Language Server Protocol (LSP) Server
==============================================
Raw JSON-RPC implementation over stdio. Zero dependencies.

Features:
  - Diagnostics (real-time error squiggles on type)
  - Hover (show docs for builtins/stdlib)
  - Completion (keywords, builtins, user-defined symbols)
  - Go to Definition (jump to function/class/variable declaration)
  - Document Symbols (outline view in VS Code sidebar)
  - Signature Help (show function parameters while typing)
  - Document Formatting (auto-format on save)

Run:  python -m taipan.lsp.server
"""
import sys
import os
import json
import re
from pathlib import Path
from typing import Any

from taipan.compiler.lexer.lexer import Lexer
from taipan.compiler.lexer.tokens import TokenType
from taipan.compiler.parser.parser import Parser
from taipan.compiler.ast.nodes import (
    Node, Program, FunctionDecl, ClassDecl, VariableDecl, ConstDecl,
    IfStmt, WhileStmt, ForStmt, RepeatStmt, TryCatchStmt, Block, Param,
)
from taipan.runtime.errors import TaipanLexError, TaipanSyntaxError


# ═══════════════════════════════════════════════════════════════════════════════
#  LSP Type Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Error severity levels
ERROR = 1
WARNING = 2
INFORMATION = 3
HINT = 4

# Symbol kinds
SYM_FILE = 1
SYM_MODULE = 2
SYM_NAMESPACE = 3
SYM_PACKAGE = 4
SYM_CLASS = 5
SYM_METHOD = 6
SYM_PROPERTY = 7
SYM_FIELD = 8
SYM_CONSTRUCTOR = 9
SYM_ENUM = 10
SYM_INTERFACE = 11
SYM_FUNCTION = 12
SYM_VARIABLE = 13
SYM_CONSTANT = 14

# Completion item kinds
COMP_TEXT = 1
COMP_METHOD = 2
COMP_FUNCTION = 3
COMP_CONSTRUCTOR = 4
COMP_FIELD = 5
COMP_VARIABLE = 6
COMP_CLASS = 7
COMP_INTERFACE = 8
COMP_MODULE = 9
COMP_PROPERTY = 10
COMP_UNIT = 11
COMP_VALUE = 12
COMP_ENUM = 13
COMP_KEYWORD = 14
COMP_SNIPPET = 15
COMP_COLOR = 16
COMP_FILE = 17
COMP_REFERENCE = 18


# ═══════════════════════════════════════════════════════════════════════════════
#  Built-in Documentation
# ═══════════════════════════════════════════════════════════════════════════════

BUILTIN_DOCS = {
    "show": "**show**(`value`, `...`) → `None`\n\nPrint values to stdout.",
    "print": "**print**(`value`, `...`) → `None`\n\nAlias for `show`.",
    "input": "**input**(`prompt`) → `String`\n\nRead a line from stdin.",
    "len": "**len**(`value`) → `Int`\n\nReturn length of string/list/map/set/tuple.",
    "type": "**type**(`value`) → `String`\n\nReturn the type name as a string.",
    "int": "**int**(`value`) → `Int`\n\nConvert value to integer.",
    "float": "**float**(`value`) → `Float`\n\nConvert value to float.",
    "str": "**str**(`value`) → `String`\n\nConvert value to string.",
    "bool": "**bool**(`value`) → `Bool`\n\nConvert value to boolean.",
    "range": "**range**(`end`) | **range**(`start`, `end`) | **range**(`start`, `end`, `step`) → `Range`\n\nCreate a range iterable.",
    "list": "**list**(`value`) → `List`\n\nConvert value to list.",
    "set": "**set**(`value`) → `Set`\n\nConvert value to set.",
    "map": "**map**() → `Map`\n\nCreate an empty map.",
    "abs": "**abs**(`value`) → `Number`\n\nReturn absolute value.",
    "min": "**min**(`values`) → `Number`\n\nReturn minimum value.",
    "max": "**max**(`values`) → `Number`\n\nReturn maximum value.",
    "sum": "**sum**(`values`) → `Number`\n\nReturn sum of values.",
    "round": "**round**(`value`, `digits=0`) → `Float`\n\nRound to specified digits.",
    "sorted": "**sorted**(`list`) → `List`\n\nReturn sorted copy.",
    "reversed": "**reversed**(`list`) → `List`\n\nReturn reversed copy.",
    "exit": "**exit**(`code=0`) → `None`\n\nExit the program.",
    "assert": "**assert**(`condition`, `msg`) → `None`\n\nRaise error if condition is false.",
    "chr": "**chr**(`code`) → `String`\n\nReturn ASCII character from code.",
    "ord": "**ord**(`char`) → `Int`\n\nReturn ASCII code from character.",
    "hex": "**hex**(`n`) → `String`\n\nReturn hex string representation.",
    "bin": "**bin**(`n`) → `String`\n\nReturn binary string representation.",
}

BUILTIN_SIGNATURES = {
    "show": "show(value, ...)",
    "print": "print(value, ...)",
    "input": "input(prompt)",
    "len": "len(value)",
    "type": "type(value)",
    "int": "int(value)",
    "float": "float(value)",
    "str": "str(value)",
    "bool": "bool(value)",
    "range": "range(start, end, step)",
    "list": "list(value)",
    "set": "set(value)",
    "abs": "abs(value)",
    "min": "min(values)",
    "max": "max(values)",
    "sum": "sum(values)",
    "round": "round(value, digits=0)",
    "sorted": "sorted(list)",
    "reversed": "reversed(list)",
    "exit": "exit(code=0)",
    "assert": "assert(condition, msg)",
    "chr": "chr(code)",
    "ord": "ord(char)",
    "hex": "hex(n)",
    "bin": "bin(n)",
}

STDLIB_DOCS = {
    "math": {
        "sqrt": "**math.sqrt**(`x`) → `Float`\n\nSquare root of x.",
        "pow": "**math.pow**(`x`, `y`) → `Float`\n\nx raised to power y.",
        "abs": "**math.abs**(`x`) → `Number`\n\nAbsolute value.",
        "floor": "**math.floor**(`x`) → `Int`\n\nLargest integer ≤ x.",
        "ceil": "**math.ceil**(`x`) → `Int`\n\nSmallest integer ≥ x.",
        "round": "**math.round**(`x`, `digits`) → `Float`\n\nRound to digits.",
        "sin": "**math.sin**(`x`) → `Float`\n\nSine of x (radians).",
        "cos": "**math.cos**(`x`) → `Float`\n\nCosine of x (radians).",
        "log": "**math.log**(`x`) → `Float`\n\nNatural logarithm.",
        "factorial": "**math.factorial**(`n`) → `Int`\n\nn! (n factorial).",
        "gcd": "**math.gcd**(`a`, `b`) → `Int`\n\nGreatest common divisor.",
        "random": "**math.random**() → `Float`\n\nRandom float in [0, 1).",
        "randint": "**math.randint**(`a`, `b`) → `Int`\n\nRandom integer in [a, b].",
        "pi": "**math.pi** → `Float`\n\nπ ≈ 3.14159...",
        "e": "**math.e** → `Float`\n\ne ≈ 2.71828...",
        "clamp": "**math.clamp**(`x`, `min`, `max`) → `Number`\n\nConstrain x to [min, max].",
        "lerp": "**math.lerp**(`a`, `b`, `t`) → `Float`\n\nLinear interpolation.",
    },
    "string": {
        "upper": "**string.upper**(`s`) → `String`\n\nConvert to uppercase.",
        "lower": "**string.lower**(`s`) → `String`\n\nConvert to lowercase.",
        "title": "**string.title**(`s`) → `String`\n\nTitle case.",
        "split": "**string.split**(`s`, `sep`) → `List`\n\nSplit string by separator.",
        "join": "**string.join**(`sep`, `list`) → `String`\n\nJoin list with separator.",
        "replace": "**string.replace**(`s`, `old`, `new`) → `String`\n\nReplace occurrences.",
        "strip": "**string.strip**(`s`) → `String`\n\nRemove leading/trailing whitespace.",
        "startsWith": "**string.startsWith**(`s`, `prefix`) → `Bool`\n\nCheck prefix.",
        "endsWith": "**string.endsWith**(`s`, `suffix`) → `Bool`\n\nCheck suffix.",
        "contains": "**string.contains**(`s`, `substr`) → `Bool`\n\nCheck substring.",
        "substring": "**string.substring**(`s`, `start`, `end`) → `String`\n\nExtract substring.",
        "reverse": "**string.reverse**(`s`) → `String`\n\nReverse string.",
        "repeat": "**string.repeat**(`s`, `n`) → `String`\n\nRepeat n times.",
        "padLeft": "**string.padLeft**(`s`, `n`, `char`) → `String`\n\nPad left with char.",
        "length": "**string.length**(`s`) → `Int`\n\nString length.",
        "isDigit": "**string.isDigit**(`s`) → `Bool`\n\nCheck if all digits.",
        "regexMatch": "**string.regexMatch**(`s`, `pattern`) → `Bool`\n\nRegex match.",
        "regexFind": "**string.regexFind**(`s`, `pattern`) → `List`\n\nFind all regex matches.",
        "chars": "**string.chars**(`s`) → `List`\n\nSplit into character list.",
    },
    "json": {
        "stringify": "**json.stringify**(`value`, `indent=0`) → `String`\n\nConvert to JSON string.",
        "parse": "**json.parse**(`text`) → `Map`\n\nParse JSON string.",
        "save": "**json.save**(`path`, `value`) → `None`\n\nSave value as JSON file.",
        "load": "**json.load**(`path`) → `Map`\n\nLoad JSON from file.",
    },
    "time": {
        "now": "**time.now**() → `String`\n\nCurrent datetime string.",
        "date": "**time.date**() → `String`\n\nCurrent date string.",
        "timestamp": "**time.timestamp**() → `Float`\n\nUnix timestamp.",
        "sleep": "**time.sleep**(`seconds`) → `None`\n\nSleep for seconds.",
        "year": "**time.year**() → `Int`\n\nCurrent year.",
        "month": "**time.month**() → `Int`\n\nCurrent month.",
        "day": "**time.day**() → `Int`\n\nCurrent day.",
        "hour": "**time.hour**() → `Int`\n\nCurrent hour.",
        "minute": "**time.minute**() → `Int`\n\nCurrent minute.",
        "second": "**time.second**() → `Int`\n\nCurrent second.",
        "clock": "**time.clock**() → `Float`\n\nHigh-resolution timer.",
    },
    "file": {
        "read": "**file.read**(`path`) → `String`\n\nRead file contents.",
        "write": "**file.write**(`path`, `text`) → `None`\n\nWrite text to file.",
        "append": "**file.append**(`path`, `text`) → `None`\n\nAppend text to file.",
        "lines": "**file.lines**(`path`) → `List`\n\nRead file as lines.",
        "delete": "**file.delete**(`path`) → `None`\n\nDelete file.",
        "exists": "**file.exists**(`path`) → `Bool`\n\nCheck if file exists.",
        "listDir": "**file.listDir**(`path`) → `List`\n\nList directory contents.",
        "mkdir": "**file.mkdir**(`path`) → `None`\n\nCreate directory.",
        "join": "**file.join**(`parts...`) → `String`\n\nJoin path parts.",
        "extension": "**file.extension**(`path`) → `String`\n\nGet file extension.",
    },
    "ai": {
        "ask": "**ai.ask**(`prompt`) → `String`\n\nAsk AI a question.",
        "summarize": "**ai.summarize**(`text`) → `String`\n\nSummarize text with AI.",
        "generateCode": "**ai.generateCode**(`prompt`) → `String`\n\nGenerate code with AI.",
        "classify": "**ai.classify**(`text`, `category`) → `String`\n\nClassify text with AI.",
        "translate": "**ai.translate**(`text`, `language`) → `String`\n\nTranslate text with AI.",
        "sentiment": "**ai.sentiment**(`text`) → `String`\n\nAnalyze sentiment with AI.",
        "isAvailable": "**ai.isAvailable**() → `Bool`\n\nCheck if AI is available.",
        "setModel": "**ai.setModel**(`name`) → `None`\n\nSet AI model name.",
        "getModel": "**ai.getModel**() → `String`\n\nGet current AI model name.",
    },
}

KEYWORDS = [
    "let", "const", "func", "class", "extends", "if", "else", "while",
    "for", "repeat", "return", "import", "spawn", "wait", "try", "catch",
    "in", "and", "or", "not", "true", "false", "ai", "break", "continue",
    "self", "super", "new", "null", "match", "case", "default",
]


# ═══════════════════════════════════════════════════════════════════════════════
#  Document Cache
# ═══════════════════════════════════════════════════════════════════════════════

_documents: dict[str, str] = {}   # uri → source text


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _get_word_at_position(source: str, line: int, character: int) -> str:
    """Extract the word under the cursor position."""
    lines = source.splitlines()
    if line >= len(lines):
        return ""
    text = lines[line]
    if character >= len(text):
        character = len(text) - 1
    if character < 0:
        return ""

    start = character
    while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
        start -= 1
    end = character
    while end < len(text) and (text[end].isalnum() or text[end] == "_"):
        end += 1
    return text[start:end]


def _extract_symbols(ast: Node) -> dict[str, tuple[int, int, str]]:
    """Extract symbol names, positions, and types from AST.
    Returns: {name: (line, column, kind)} where kind is 'function', 'class', 'variable', 'constant'"""
    symbols = {}
    if not isinstance(ast, Program):
        return symbols

    def _scan(node: Node, depth: int = 0):
        if isinstance(node, FunctionDecl):
            symbols[node.name] = (node.line, node.column, "function")
            for stmt in node.body.statements:
                _scan(stmt, depth + 1)
        elif isinstance(node, ClassDecl):
            symbols[node.name] = (node.line, node.column, "class")
            for stmt in node.body.statements:
                _scan(stmt, depth + 1)
        elif isinstance(node, VariableDecl):
            symbols[node.name] = (node.line, node.column, "constant" if not node.mutable else "variable")
        elif isinstance(node, ConstDecl):
            symbols[node.name] = (node.line, node.column, "constant")
        elif isinstance(node, (IfStmt, WhileStmt, ForStmt, RepeatStmt, TryCatchStmt)):
            if hasattr(node, 'then_branch') and node.then_branch:
                for stmt in node.then_branch.statements:
                    _scan(stmt, depth + 1)
            if hasattr(node, 'else_branch') and node.else_branch and isinstance(node.else_branch, Block):
                for stmt in node.else_branch.statements:
                    _scan(stmt, depth + 1)
            if hasattr(node, 'body') and node.body:
                for stmt in node.body.statements:
                    _scan(stmt, depth + 1)
            if hasattr(node, 'catch_block') and node.catch_block:
                for stmt in node.catch_block.statements:
                    _scan(stmt, depth + 1)
            if hasattr(node, 'try_block') and node.try_block:
                for stmt in node.try_block.statements:
                    _scan(stmt, depth + 1)

    for stmt in ast.body:
        _scan(stmt)
    return symbols


def _extract_document_symbols(ast: Node) -> list[dict]:
    """Extract top-level symbols for Document Symbol (outline view)."""
    symbols = []
    if not isinstance(ast, Program):
        return symbols

    def _sym(name: str, kind: int, line: int, col: int, children: list = None) -> dict:
        s = {
            "name": name,
            "kind": kind,
            "range": {
                "start": {"line": line - 1, "character": max(0, col - 1)},
                "end": {"line": line - 1, "character": max(0, col - 1) + len(name)},
            },
            "selectionRange": {
                "start": {"line": line - 1, "character": max(0, col - 1)},
                "end": {"line": line - 1, "character": max(0, col - 1) + len(name)},
            },
        }
        if children:
            s["children"] = children
        return s

    def _extract_params(params: list[Param]) -> str:
        """Format parameter list for signature."""
        parts = []
        for p in params:
            if p.name == "self":
                continue
            hint = f": {p.type_hint}" if p.type_hint else ""
            default = f" = {p.default}" if p.default else ""
            parts.append(f"{p.name}{hint}{default}")
        return ", ".join(parts)

    for stmt in ast.body:
        if isinstance(stmt, FunctionDecl):
            params = _extract_params(stmt.params)
            ret = f" -> {stmt.return_type}" if stmt.return_type else ""
            label = f"{stmt.name}({params}){ret}"
            children = []
            # Scan body for nested functions/variables
            for body_stmt in stmt.body.statements:
                if isinstance(body_stmt, (FunctionDecl, VariableDecl, ConstDecl)):
                    kind = SYM_FUNCTION if isinstance(body_stmt, FunctionDecl) else (SYM_CONSTANT if isinstance(body_stmt, ConstDecl) else SYM_VARIABLE)
                    children.append(_sym(body_stmt.name, kind, body_stmt.line, body_stmt.column))
            symbols.append(_sym(label, SYM_FUNCTION, stmt.line, stmt.column, children))
        elif isinstance(stmt, ClassDecl):
            children = []
            for body_stmt in stmt.body.statements:
                if isinstance(body_stmt, FunctionDecl):
                    params = _extract_params(body_stmt.params)
                    children.append(_sym(f"{body_stmt.name}({params})", SYM_METHOD, body_stmt.line, body_stmt.column))
            symbols.append(_sym(stmt.name, SYM_CLASS, stmt.line, stmt.column, children))
        elif isinstance(stmt, VariableDecl):
            symbols.append(_sym(stmt.name, SYM_VARIABLE, stmt.line, stmt.column))
        elif isinstance(stmt, ConstDecl):
            symbols.append(_sym(stmt.name, SYM_CONSTANT, stmt.line, stmt.column))

    return symbols


def _extract_function_params(ast: Node, func_name: str) -> list[Param] | None:
    """Find a function's parameters by name in the AST."""
    if not isinstance(ast, Program):
        return None

    def _scan(node: Node) -> list[Param] | None:
        if isinstance(node, FunctionDecl) and node.name == func_name:
            return node.params
        if isinstance(node, ClassDecl):
            for stmt in node.body.statements:
                if isinstance(stmt, FunctionDecl) and stmt.name == func_name:
                    return stmt.params
        return None

    for stmt in ast.body:
        result = _scan(stmt)
        if result is not None:
            return result
    return None


def _parse_source(source: str) -> tuple[list[dict], Node | None]:
    """Lex and parse source, returning LSP diagnostics and AST."""
    diagnostics = []
    ast = None

    try:
        tokens = Lexer(source, "<lsp>").tokenize()
    except TaipanLexError as e:
        diagnostics.append({
            "range": {
                "start": {"line": e.line - 1, "character": max(0, e.column - 1)},
                "end": {"line": e.line - 1, "character": e.column + 5},
            },
            "message": e.message,
            "severity": ERROR,
            "source": "taipan-lsp",
        })
        return diagnostics, None

    try:
        ast = Parser(tokens, "<lsp>").parse()
    except TaipanSyntaxError as e:
        col = 0
        if hasattr(e, 'column') and e.column:
            col = max(0, e.column - 1)
        diagnostics.append({
            "range": {
                "start": {"line": e.line - 1, "character": col},
                "end": {"line": e.line - 1, "character": col + 10},
            },
            "message": e.message,
            "severity": ERROR,
            "source": "taipan-lsp",
        })
        return diagnostics, None

    return diagnostics, ast


def _format_taipan(source: str) -> str | None:
    """Basic Taipan auto-formatter: normalizes indentation and spacing."""
    try:
        # Verify it's parseable first
        tokens = Lexer(source, "<lsp>").tokenize()
        Parser(tokens, "<lsp>").parse()
    except (TaipanLexError, TaipanSyntaxError):
        return None

    lines = source.splitlines()
    result = []
    indent = 0
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            result.append("")
            continue
        if line.startswith("}"):
            indent = max(0, indent - 1)
        result.append("    " * indent + line)
        if line.endswith("{"):
            indent += 1
    return "\n".join(result) + "\n"


# ═══════════════════════════════════════════════════════════════════════════════
#  JSON-RPC Transport
# ═══════════════════════════════════════════════════════════════════════════════

def _read_message() -> dict[str, Any] | None:
    """Read a JSON-RPC message from stdin."""
    header = b""
    while True:
        byte = sys.stdin.buffer.read(1)
        if not byte:
            return None
        header += byte
        if header.endswith(b"\r\n\r\n"):
            break

    match = re.search(rb"Content-Length:\s*(\d+)", header)
    if not match:
        return None
    length = int(match.group(1))

    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode("utf-8"))


def _write_message(msg: dict[str, Any]):
    """Write a JSON-RPC message to stdout."""
    body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\r\n\r\n".encode("utf-8")
    sys.stdout.buffer.write(header + body)
    sys.stdout.buffer.flush()


# ═══════════════════════════════════════════════════════════════════════════════
#  LSP Message Handlers
# ═══════════════════════════════════════════════════════════════════════════════

def handle_initialize(msg_id: int | str | None, params: dict) -> dict:
    """Respond to initialize request."""
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "capabilities": {
                "textDocumentSync": {"openClose": True, "change": 1},
                "hoverProvider": True,
                "completionProvider": {
                    "triggerCharacters": ["."],
                    "resolveProvider": False,
                },
                "definitionProvider": True,
                "documentSymbolProvider": True,
                "signatureHelpProvider": {
                    "triggerCharacters": ["("],
                },
                "documentFormattingProvider": True,
                "diagnosticProvider": {
                    "interFileDependencies": False,
                    "workspaceDiagnostics": False,
                },
                "semanticTokensProvider": {
                    "legend": {
                        "tokenTypes": ["namespace", "type", "class", "enum", "interface", "struct", "typeParameter", "parameter", "variable", "property", "enumMember", "event", "function", "method", "macro", "keyword", "modifier", "comment", "string", "number", "regexp", "operator"],
                        "tokenModifiers": ["declaration", "definition", "readonly", "static", "deprecated", "abstract", "async", "modification", "documentation", "defaultLibrary"]
                    },
                    "full": {"delta": False},
                    "range": False,
                },
            },
            "serverInfo": {"name": "taipan-lsp", "version": "1.0.0"},
        }
    }


def handle_did_open(params: dict):
    """Handle textDocument/didOpen."""
    uri = params["textDocument"]["uri"]
    source = params["textDocument"]["text"]
    _documents[uri] = source
    diagnostics, _ = _parse_source(source)
    _write_message({
        "jsonrpc": "2.0",
        "method": "textDocument/publishDiagnostics",
        "params": {"uri": uri, "diagnostics": diagnostics},
    })


def handle_did_change(params: dict):
    """Handle textDocument/didChange."""
    uri = params["textDocument"]["uri"]
    changes = params.get("contentChanges", [])
    if changes:
        source = changes[0].get("text", "")
        _documents[uri] = source
        diagnostics, _ = _parse_source(source)
        _write_message({
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": uri, "diagnostics": diagnostics},
        })


def handle_hover(msg_id: int | str, params: dict) -> dict:
    """Handle textDocument/hover."""
    uri = params["textDocument"]["uri"]
    pos = params["position"]
    source = _documents.get(uri, "")
    word = _get_word_at_position(source, pos["line"], pos["character"])

    contents = None
    if word:
        doc = BUILTIN_DOCS.get(word)
        if doc:
            contents = {"kind": "markdown", "value": doc}
        else:
            for mod, funcs in STDLIB_DOCS.items():
                if word in funcs:
                    contents = {"kind": "markdown", "value": funcs[word]}
                    break

    result = {"contents": contents} if contents else None
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def handle_completion(msg_id: int | str, params: dict) -> dict:
    """Handle textDocument/completion."""
    uri = params["textDocument"]["uri"]
    source = _documents.get(uri, "")

    items = []

    for kw in KEYWORDS:
        items.append({"label": kw, "kind": COMP_KEYWORD, "insertText": kw})

    for name, doc in BUILTIN_DOCS.items():
        items.append({
            "label": name,
            "kind": COMP_FUNCTION,
            "detail": doc.split("\n")[0],
            "documentation": {"kind": "markdown", "value": doc},
            "insertText": name,
        })

    for mod, funcs in STDLIB_DOCS.items():
        for name, doc in funcs.items():
            items.append({
                "label": f"{mod}.{name}",
                "kind": COMP_FUNCTION,
                "detail": doc.split("\n")[0],
                "documentation": {"kind": "markdown", "value": doc},
                "insertText": f"{mod}.{name}",
            })

    _, ast = _parse_source(source)
    if ast:
        symbols = _extract_symbols(ast)
        for name, (line, col, kind) in symbols.items():
            lsp_kind = COMP_FUNCTION if kind == "function" else (COMP_CLASS if kind == "class" else COMP_VARIABLE)
            items.append({
                "label": name,
                "kind": lsp_kind,
                "detail": f"Defined at line {line}",
                "insertText": name,
            })

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {"isIncomplete": False, "items": items},
    }


def handle_definition(msg_id: int | str, params: dict) -> dict:
    """Handle textDocument/definition."""
    uri = params["textDocument"]["uri"]
    pos = params["position"]
    source = _documents.get(uri, "")
    word = _get_word_at_position(source, pos["line"], pos["character"])

    result = None
    if word:
        _, ast = _parse_source(source)
        if ast:
            symbols = _extract_symbols(ast)
            if word in symbols:
                line, col, _ = symbols[word]
                result = [{
                    "uri": uri,
                    "range": {
                        "start": {"line": line - 1, "character": max(0, col - 1)},
                        "end": {"line": line - 1, "character": col + len(word)},
                    },
                }]

    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def handle_document_symbol(msg_id: int | str, params: dict) -> dict:
    """Handle textDocument/documentSymbol — outline view."""
    uri = params["textDocument"]["uri"]
    source = _documents.get(uri, "")
    _, ast = _parse_source(source)

    symbols = _extract_document_symbols(ast) if ast else []
    return {"jsonrpc": "2.0", "id": msg_id, "result": symbols}


def handle_signature_help(msg_id: int | str, params: dict) -> dict:
    """Handle textDocument/signatureHelp — show function parameters."""
    uri = params["textDocument"]["uri"]
    pos = params["position"]
    source = _documents.get(uri, "")

    # Find the function name before the cursor position (look for '(')
    lines = source.splitlines()
    if pos["line"] >= len(lines):
        return {"jsonrpc": "2.0", "id": msg_id, "result": None}

    line_text = lines[pos["line"]]
    # Find the last word before '(' on this line or before cursor
    before = line_text[:pos["character"]]
    # Look for pattern: word(...
    match = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*$', before)
    if not match:
        return {"jsonrpc": "2.0", "id": msg_id, "result": None}

    func_name = match.group(1)
    sig = BUILTIN_SIGNATURES.get(func_name)
    doc = BUILTIN_DOCS.get(func_name)

    # Try user-defined functions
    if not sig:
        _, ast = _parse_source(source)
        if ast:
            params_list = _extract_function_params(ast, func_name)
            if params_list:
                parts = [p.name for p in params_list if p.name != "self"]
                sig = f"{func_name}({', '.join(parts)})"

    # Try stdlib
    if not sig:
        for mod, funcs in STDLIB_DOCS.items():
            if func_name in funcs:
                doc_text = funcs[func_name]
                # Extract signature from first line
                first_line = doc_text.split("\n")[0]
                sig = first_line.replace("**", "").replace("`", "")
                break

    if not sig:
        return {"jsonrpc": "2.0", "id": msg_id, "result": None}

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "signatures": [{
                "label": sig,
                "documentation": {"kind": "markdown", "value": doc or ""},
            }],
            "activeSignature": 0,
            "activeParameter": 0,
        },
    }


def handle_formatting(msg_id: int | str, params: dict) -> dict:
    """Handle textDocument/formatting — auto-format document."""
    uri = params["textDocument"]["uri"]
    source = _documents.get(uri, "")
    formatted = _format_taipan(source)

    if formatted is None:
        return {"jsonrpc": "2.0", "id": msg_id, "result": None}

    # Compute full document range
    lines = source.splitlines()
    last_line = max(0, len(lines) - 1)
    last_char = len(lines[-1]) if lines else 0

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": [{
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": last_line, "character": last_char},
            },
            "newText": formatted,
        }],
    }


def _encode_semantic_tokens(tokens: list[dict]) -> list[int]:
    """Encode semantic tokens as LSP integer array (5 ints per token)."""
    data = []
    prev_line = 0
    prev_char = 0

    for tok in tokens:
        line = tok["line"]
        char = tok["char"]
        length = tok["length"]
        token_type = tok["type"]
        modifiers = tok.get("modifiers", 0)

        delta_line = line - prev_line
        if delta_line == 0:
            delta_char = char - prev_char
        else:
            delta_char = char

        data.extend([delta_line, delta_char, length, token_type, modifiers])
        prev_line = line
        prev_char = char

    return data


# Semantic token type indices (must match legend in handle_initialize)
SEM_KEYWORD = 15
SEM_STRING = 18
SEM_NUMBER = 19
SEM_COMMENT = 17
SEM_OPERATOR = 21
SEM_FUNCTION = 12
SEM_CLASS = 2
SEM_VARIABLE = 8
SEM_TYPE = 1
SEM_PARAMETER = 7
SEM_PROPERTY = 9
SEM_METHOD = 13
SEM_NAMESPACE = 0
SEM_MODIFIER = 16
SEM_MACRO = 14
SEM_INTERFACE = 4
SEM_ENUM = 3
SEM_STRUCT = 5
SEM_TYPE_PARAMETER = 6
SEM_EVENT = 10
SEM_ENUM_MEMBER = 11
SEM_REGEXP = 20


def handle_semantic_tokens(msg_id: int | str, params: dict) -> dict:
    """Handle textDocument/semanticTokens/full."""
    uri = params["textDocument"]["uri"]
    source = _documents.get(uri, "")

    if not source:
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"data": []}}

    try:
        lexer_tokens = Lexer(source, "<lsp>").tokenize()
    except TaipanLexError:
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"data": []}}

    # Build set of function/class names from AST for identifier mapping
    func_names = set()
    class_names = set()
    var_names = set()
    const_names = set()
    try:
        ast = Parser(lexer_tokens, "<lsp>").parse()
        if isinstance(ast, Program):
            def _scan(node: Node):
                if isinstance(node, FunctionDecl):
                    func_names.add(node.name)
                elif isinstance(node, ClassDecl):
                    class_names.add(node.name)
                elif isinstance(node, VariableDecl):
                    var_names.add(node.name)
                elif isinstance(node, ConstDecl):
                    const_names.add(node.name)
            for stmt in ast.body:
                _scan(stmt)
    except Exception:
        pass

    # Map lexer tokens to semantic tokens
    semantic_tokens = []
    for tok in lexer_tokens:
        if tok.type in (TokenType.NEWLINE, TokenType.EOF, TokenType.COMMENT):
            continue

        line = tok.line - 1  # 0-indexed
        char = tok.column - 1
        length = len(str(tok.value))

        token_type = None
        if tok.type in (TokenType.LET, TokenType.CONST, TokenType.FUNC, TokenType.CLASS,
                         TokenType.IF, TokenType.ELSE, TokenType.WHILE, TokenType.FOR,
                         TokenType.REPEAT, TokenType.RETURN, TokenType.IMPORT,
                         TokenType.SPAWN, TokenType.WAIT, TokenType.TRY, TokenType.CATCH,
                         TokenType.IN, TokenType.AND, TokenType.OR, TokenType.NOT,
                         TokenType.TRUE, TokenType.FALSE, TokenType.AI, TokenType.BREAK,
                         TokenType.CONTINUE, TokenType.EXTENDS, TokenType.SELF,
                         TokenType.SUPER, TokenType.NEW, TokenType.NULL_KW,
                         TokenType.MATCH, TokenType.CASE, TokenType.DEFAULT, TokenType.TEST):
            token_type = SEM_KEYWORD
        elif tok.type in (TokenType.STRING, TokenType.FSTRING):
            token_type = SEM_STRING
        elif tok.type in (TokenType.INT, TokenType.FLOAT, TokenType.BOOL):
            token_type = SEM_NUMBER
        elif tok.type in (TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH,
                           TokenType.PERCENT, TokenType.STAR_STAR, TokenType.SLASH_SLASH,
                           TokenType.EQ_EQ, TokenType.NOT_EQ, TokenType.LT, TokenType.LT_EQ,
                           TokenType.GT, TokenType.GT_EQ, TokenType.BANG, TokenType.EQUALS,
                           TokenType.PLUS_EQ, TokenType.MINUS_EQ, TokenType.STAR_EQ,
                           TokenType.SLASH_EQ, TokenType.DOT_DOT, TokenType.ARROW,
                           TokenType.FAT_ARROW, TokenType.COLON, TokenType.SEMICOLON,
                           TokenType.COMMA, TokenType.DOT, TokenType.LPAREN, TokenType.RPAREN,
                           TokenType.LBRACE, TokenType.RBRACE, TokenType.LBRACKET, TokenType.RBRACKET):
            token_type = SEM_OPERATOR
        elif tok.type == TokenType.IDENTIFIER:
            name = str(tok.value)
            if name in func_names:
                token_type = SEM_FUNCTION
            elif name in class_names:
                token_type = SEM_CLASS
            elif name in const_names:
                token_type = SEM_VARIABLE
                # Add readonly modifier for constants
                semantic_tokens.append({"line": line, "char": char, "length": length, "type": token_type, "modifiers": 4})
                continue
            elif name in var_names:
                token_type = SEM_VARIABLE
            elif name in ("Int", "Float", "String", "Bool", "List", "Map", "Set", "Tuple", "Range"):
                token_type = SEM_TYPE
            else:
                token_type = SEM_VARIABLE

        if token_type is not None:
            semantic_tokens.append({"line": line, "char": char, "length": length, "type": token_type, "modifiers": 0})

    data = _encode_semantic_tokens(semantic_tokens)
    return {"jsonrpc": "2.0", "id": msg_id, "result": {"data": data}}


# ═══════════════════════════════════════════════════════════════════════════════
#  Main Loop
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("Taipan LSP Server v1.0.0 starting...", file=sys.stderr)
    print("Features: diagnostics, hover, completion, go-to-definition, document symbols, signature help, formatting", file=sys.stderr)

    while True:
        msg = _read_message()
        if msg is None:
            break

        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            _write_message(handle_initialize(msg_id, params))

        elif method == "textDocument/didOpen":
            handle_did_open(params)

        elif method == "textDocument/didChange":
            handle_did_change(params)

        elif method == "textDocument/hover":
            _write_message(handle_hover(msg_id, params))

        elif method == "textDocument/completion":
            _write_message(handle_completion(msg_id, params))

        elif method == "textDocument/definition":
            _write_message(handle_definition(msg_id, params))

        elif method == "textDocument/documentSymbol":
            _write_message(handle_document_symbol(msg_id, params))

        elif method == "textDocument/signatureHelp":
            _write_message(handle_signature_help(msg_id, params))

        elif method == "textDocument/formatting":
            _write_message(handle_formatting(msg_id, params))

        elif method == "textDocument/semanticTokens/full":
            _write_message(handle_semantic_tokens(msg_id, params))

        elif method == "shutdown":
            _write_message({"jsonrpc": "2.0", "id": msg_id, "result": None})

        elif method == "exit":
            break

    print("Taipan LSP Server exiting.", file=sys.stderr)


if __name__ == "__main__":
    main()
