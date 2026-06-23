#!/usr/bin/env python3
"""
Taipan CLI — tai
==================
The main command-line interface for Taipan.

Usage:
  python -m taipan run <file.tp>        Run a Taipan source file
  python -m taipan test <file.tp>       Run all test blocks in a file
  python -m taipan repl                 Launch the interactive REPL
  python -m taipan check <file.tp>      Lint / type-check without running
  python -m taipan tokens <file.tp>     Print lexed tokens (debug)
  python -m taipan ast <file.tp>        Print the parsed AST (debug)
  python -m taipan version              Show version info
  python -m taipan help                 Show this help message
"""

import sys
import os
try:
    import readline  # noqa: F401 — enables arrow-key history in REPL (not available on Windows)
except ImportError:
    pass  # readline not available on Windows — REPL still works
from pathlib import Path

# ── Force UTF-8 output on Windows ─────────────────────────────────────────────
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from taipan.compiler.lexer.lexer    import Lexer
from taipan.compiler.parser.parser  import Parser
from taipan.compiler.semantic.analyzer import SemanticAnalyzer
from taipan.runtime.pretty_errors import format_error
from taipan.runtime.ai_errors import format_error_with_ai  # AI-powered error explanations
from taipan.compiler.backend.interpreter import Interpreter
from taipan.runtime.errors import TaipanError

VERSION = "1.0.0"

_art_lines = [
    "████████╗ █████╗ ██╗██████╗  █████╗ ███╗   ██╗",
    "╚══██╔══╝██╔══██╗██║██╔══██╗██╔══██╗████╗  ██║",
    "   ██║   ███████║██║██████╔╝███████║██╔██╗ ██║",
    "   ██║   ██╔══██║██║██╔═══╝ ██╔══██║██║╚██╗██║",
    "   ██║   ██║  ██║██║██║     ██║  ██║██║ ╚████║",
    "   ╚═╝   ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═══╝"
]

_banner_lines = [
    "╔" + "═" * 58 + "╗"
]
for _l in _art_lines:
    _banner_lines.append("║" + " " * 6 + _l + " " * 6 + "║")

_version_str = f"Lang v{VERSION}"
_banner_lines.append(f"║{_version_str.center(58)}║")
_banner_lines.append("║" + " " * 58 + "║")

_tagline = "A Modern Python Successor — Simple, Fast, AI-Native"
_banner_lines.append(f"║{_tagline.center(58)}║")
_banner_lines.append("╚" + "═" * 58 + "╝")

BANNER = "\n".join(_banner_lines) + "\n"

ANSI = {
    "reset":  "\033[0m",
    "bold":   "\033[1m",
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "blue":   "\033[94m",
    "red":    "\033[91m",
    "cyan":   "\033[96m",
    "purple": "\033[95m",
    "gray":   "\033[90m",
}


def c(color: str, text: str) -> str:
    if sys.platform == "win32":
        os.system("")
    return f"{ANSI.get(color, '')}{text}{ANSI['reset']}"


# ── Pipeline helpers ──────────────────────────────────────────────────────────

def _lex(source: str, filename: str):
    return Lexer(source, filename).tokenize()


def _parse(source: str, filename: str):
    tokens = _lex(source, filename)
    return Parser(tokens, filename).parse()


def _analyze(ast, filename: str):
    analyzer = SemanticAnalyzer()
    errors   = analyzer.analyze(ast)
    if errors:
        return errors

    # Run Static Type Checker
    from taipan.compiler.semantic.type_checker import TypeChecker
    checker = TypeChecker()
    type_errors = checker.check(ast)
    return type_errors



def _print_error(e: TaipanError, source: str = "", filename: str = "", use_ai: bool = False):
    """Print an error with professional source context and optional AI-powered explanation."""
    hints = []

    # AI-powered error suggestions — enabled by flag OR environment variable
    if use_ai or os.environ.get("TAIPAN_AI_ERRORS"):
        from taipan.runtime.ai_errors import ai_explain
        source_line = ""
        if e.line and source:
            lines = source.splitlines()
            if 0 < e.line <= len(lines):
                source_line = lines[e.line - 1]
        suggestion = ai_explain(e, source_line)
        if suggestion:
            hints.append(suggestion)

    # Use professional error formatter with source context
    formatted = format_error(e, source=source, filename=filename, hints=hints)
    print(formatted)


def _run_file(filepath: str, check_only: bool = False, use_vm: bool = False, use_ai: bool = False) -> int:
    path = Path(filepath)
    if not path.exists():
        print(c("red", f"Error: File '{filepath}' not found."))
        return 1
    if path.suffix != ".tp":
        print(c("yellow", f"Warning: '{filepath}' does not have a .tp extension."))

    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        print(c("red", f"Error reading file: {e}"))
        return 1

    filename = str(path)

    # ── Lex ──────────────────────────────────────────────────────────────────
    try:
        tokens = _lex(source, filename)
    except TaipanError as e:
        _print_error(e, source, filename)
        return 1

    # ── Parse ─────────────────────────────────────────────────────────────────
    try:
        ast = Parser(tokens, filename).parse()
    except TaipanError as e:
        _print_error(e, source, filename)
        return 1

    # ── Semantic analysis ─────────────────────────────────────────────────────
    errors = _analyze(ast, filename)
    if errors:
        for err in errors:
            print(c("yellow", f"[Semantic Warning] {err}"))
        # Warnings only — don't abort

    if check_only:
        if errors:
            print(c("yellow", f"\n{len(errors)} semantic warning(s) found."))
        else:
            print(c("green", "✓ No issues found."))
        return 0

    # ── Interpret / Run VM ────────────────────────────────────────────────────
    try:
        if use_vm:
            from taipan.compiler.vm.compiler import BytecodeCompiler
            from taipan.compiler.vm.vm_optimized import VM
            compiler = BytecodeCompiler(name=filename)
            code_obj = compiler.compile(ast)
            vm = VM(filename=filename)
            vm.execute(code_obj)
        else:
            interp = Interpreter(filename=filename)
            interp.execute(ast)
        return 0
    except TaipanError as e:
        _print_error(e, source, filename, use_ai=use_ai)
        return 1
    except KeyboardInterrupt:
        print(c("yellow", "\nInterrupted."))
        return 130
    except SystemExit as e:
        return int(e.code) if e.code is not None else 0
    except Exception as e:
        print(c("red", f"\nInternal Error: {type(e).__name__}: {e}"))
        if os.environ.get("TAIPAN_DEBUG"):
            import traceback
            traceback.print_exc()
        return 1



# ── REPL ──────────────────────────────────────────────────────────────────────

def _run_repl(use_vm: bool = False, use_ai: bool = False):
    print(BANNER)
    print(c("gray", "Type Taipan code and press Enter. Type 'exit' or Ctrl+C to quit.\n"))

    if use_vm:
        from taipan.compiler.vm.compiler import BytecodeCompiler
        from taipan.compiler.vm.vm_optimized import VM
        vm = VM(filename="<repl>")
    else:
        interp  = Interpreter(filename="<repl>")
    history = []

    while True:
        try:
            line = input(c("cyan", "tai> "))
        except (EOFError, KeyboardInterrupt):
            print(c("yellow", "\nGoodbye! 👋"))
            break

        if not line.strip():
            continue
        if line.strip().lower() in ("exit", "quit", "bye"):
            print(c("yellow", "Goodbye! 👋"))
            break
        if line.strip() == "help":
            _repl_help()
            continue
        if line.strip() == "clear":
            os.system("cls" if sys.platform == "win32" else "clear")
            continue
        if line.strip().startswith("//") or line.strip().startswith("#"):
            continue

        # Support multi-line input (blocks ending with '{')
        source = line
        open_braces = line.count("{") - line.count("}")
        while open_braces > 0:
            try:
                cont = input(c("gray", "...  "))
                source += "\n" + cont
                open_braces += cont.count("{") - cont.count("}")
            except (EOFError, KeyboardInterrupt):
                break

        history.append(source)

        try:
            tokens = _lex(source, "<repl>")
            ast    = Parser(tokens, "<repl>").parse()
        except TaipanError as e:
            _print_repl_error(e, source)
            continue

        try:
            if use_vm:
                compiler = BytecodeCompiler(name="<repl>")
                code_obj = compiler.compile(ast)
                result = vm.execute(code_obj)
            else:
                result = interp.execute(ast)
            if result is not None:
                from taipan.runtime.taipan_types import pee_str
                print(c("gray", f"→ {pee_str(result)}"))

        except TaipanError as e:
            _print_repl_error(e, source, use_ai=use_ai)
        except SystemExit:
            break
        except KeyboardInterrupt:
            print(c("yellow", "Interrupted."))
        except Exception as e:
            print(c("red", f"Internal: {e}"))
            if os.environ.get("TAIPAN_DEBUG"):
                import traceback
                traceback.print_exc()


def _print_repl_error(e: TaipanError, source: str = "", use_ai: bool = False):
    """Print a REPL error with professional formatting."""
    _print_error(e, source=source, filename="<repl>", use_ai=use_ai)


def _repl_help():
    print(c("cyan", "\n  REPL Commands:"))
    print("  exit / quit  — Exit the REPL")
    print("  clear        — Clear the screen")
    print("  help         — Show this help")
    print()
    print(c("cyan", "  Quick examples:"))
    print('  let x = 42')
    print('  show("Hello " + "World")')
    print('  for i in 1..5 { show(i) }')
    print('  func double(n) { return n * 2 }')
    print()


# ── Token printer ─────────────────────────────────────────────────────────────

def _print_tokens(filepath: str) -> int:
    path = Path(filepath)
    if not path.exists():
        print(c("red", f"Error: File '{filepath}' not found."))
        return 1
    source = path.read_text(encoding="utf-8")
    try:
        tokens = _lex(source, str(path))
        print(c("bold", f"Tokens from '{filepath}':"))
        print(c("gray", f"{'TYPE':<22} {'VALUE':<30} {'LINE:COL'}"))
        print(c("gray", "-" * 65))
        for tok in tokens:
            val = repr(tok.value)[:28]
            print(f"  {c('cyan', tok.type.name):<30} {val:<30} {tok.line}:{tok.column}")
        return 0
    except TaipanError as e:
        print(c("red", str(e)))
        return 1


# ── AST printer ───────────────────────────────────────────────────────────────

def _print_ast(filepath: str) -> int:
    path = Path(filepath)
    if not path.exists():
        print(c("red", f"Error: File '{filepath}' not found."))
        return 1
    source = path.read_text(encoding="utf-8")
    try:
        tokens = _lex(source, str(path))
        ast    = Parser(tokens, str(path)).parse()
        print(c("bold", f"AST for '{filepath}':"))
        _pprint_node(ast, 0)
        return 0
    except TaipanError as e:
        print(c("red", str(e)))
        return 1


def _pprint_node(node, depth: int):
    import dataclasses
    indent = "  " * depth
    name   = type(node).__name__
    print(f"{indent}{c('cyan', name)}")
    if dataclasses.is_dataclass(node):
        for f in dataclasses.fields(node):
            if f.name in ("line", "column"):
                continue
            val = getattr(node, f.name)
            if hasattr(val, "__class__") and val.__class__.__module__ == "compiler.ast.nodes":
                print(f"{indent}  {c('yellow', f.name)}:")
                _pprint_node(val, depth + 2)
            elif isinstance(val, list):
                print(f"{indent}  {c('yellow', f.name)}: [")
                for item in val:
                    if hasattr(item, "__class__") and item.__class__.__module__ == "compiler.ast.nodes":
                        _pprint_node(item, depth + 2)
                    elif isinstance(item, tuple):
                        for sub in item:
                            if hasattr(sub, "__class__") and sub.__class__.__module__ == "compiler.ast.nodes":
                                _pprint_node(sub, depth + 2)
                    else:
                        print(f"{indent}    {item!r}")
                print(f"{indent}  ]")
            else:
                print(f"{indent}  {c('yellow', f.name)}: {val!r}")


# ── Auto-formatter ─────────────────────────────────────────────────────────────

def _format_file(filepath: str) -> int:
    """Basic Taipan auto-formatter: normalizes indentation and spacing."""
    path = Path(filepath)
    if not path.exists():
        print(c("red", f"Error: File '{filepath}' not found."))
        return 1

    source = path.read_text(encoding="utf-8")
    try:
        # Verify it's parseable first
        tokens = _lex(source, str(path))
        Parser(tokens, str(path)).parse()
    except TaipanError as e:
        print(c("red", f"Cannot format: {e}"))
        return 1

    # Basic formatting: normalize brace spacing, consistent 4-space indent
    lines   = source.splitlines()
    result  = []
    indent  = 0
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

    formatted = "\n".join(result) + "\n"
    path.write_text(formatted, encoding="utf-8")
    print(c("green", f"✓ Formatted '{filepath}'"))
    return 0


# ── Test runner ───────────────────────────────────────────────────────────────

def _run_tests(target: str = None) -> int:
    """Run all test{ } blocks in .pk files and report aggregated results.

    target: a .pk file, a directory, or None (auto-discover tests/ or .)
    """
    from taipan.compiler.ast.nodes import TestStmt

    if target is None:
        # Auto-discover: prefer ./tests/ directory, else current directory
        if Path("tests").is_dir():
            target = "tests"
        else:
            target = "."

    target_path = Path(target)

    # Collect .pk files to test
    if target_path.is_file():
        pk_files = [target_path]
    elif target_path.is_dir():
        pk_files = sorted(target_path.rglob("*.tp"))
    else:
        print(c("red", f"Error: '{target}' is not a file or directory."))
        return 1

    if not pk_files:
        print(c("yellow", f"No .tp files found in '{target}'."))
        return 0

    total_passed = 0
    total_failed = 0
    files_with_tests = 0

    print()
    print(c("bold", f"Taipan Test Runner — scanning {len(pk_files)} file(s)"))
    print(c("gray", "=" * 55))

    for pk_path in pk_files:
        try:
            source = pk_path.read_text(encoding="utf-8")
        except Exception as e:
            print(c("red", f"  Cannot read '{pk_path}': {e}"))
            continue

        filename = str(pk_path)

        # Quick check: does the file contain any 'test' keyword?
        # (Skip files with no test blocks to avoid polluting output)
        try:
            tokens = _lex(source, filename)
        except TaipanError as e:
            print(c("red", f"  Lex error in '{pk_path}': {e}"))
            continue

        try:
            ast = Parser(tokens, filename).parse()
        except TaipanError as e:
            print(c("red", f"  Parse error in '{pk_path}': {e}"))
            continue

        # Check if there are any TestStmt nodes in this file
        has_tests = any(isinstance(node, TestStmt) for node in ast.body)
        if not has_tests:
            continue

        files_with_tests += 1
        print()
        print(f"  {c('cyan', str(pk_path))}")

        interp = Interpreter(filename=filename)
        try:
            interp.execute(ast)
        except TaipanError as e:
            print(c("red", f"    Runtime error: {e}"))
            continue
        except Exception as e:
            print(c("red", f"    Internal error: {e}"))
            continue

        results = getattr(interp, "_test_results", [])
        for r in results:
            status = c("green", "  ✓ PASS") if r["passed"] else c("red", "  ✗ FAIL")
            print(f"    {status}  {r['name']}")
            if not r["passed"] and r["error"]:
                print(f"         {c('red', r['error'])}")

        passed = sum(1 for r in results if r["passed"])
        failed = len(results) - passed
        total_passed += passed
        total_failed += failed

    if files_with_tests == 0:
        print(c("yellow", f"\n  No test{{}} blocks found in any .pk file under '{target}'."))
        print(c("gray",   "  Hint: Add test blocks like:  test \"my test\" { assert(1 == 1) }"))
        return 0

    print()
    print(c("gray", "=" * 55))
    color = "green" if total_failed == 0 else ("yellow" if total_passed > 0 else "red")
    print(c(color, f"  {total_passed} passed, {total_failed} failed  ({total_passed + total_failed} total across {files_with_tests} file(s))"))
    print()

    return 0 if total_failed == 0 else 1


def _compile_file(filepath: str, output_exe: str = None) -> int:
    path = Path(filepath)
    if not path.exists():
        print(c("red", f"Error: File '{filepath}' not found."))
        return 1
    if path.suffix != ".tp":
        print(c("yellow", f"Warning: '{filepath}' does not have a .tp extension."))

    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        print(c("red", f"Error reading file: {e}"))
        return 1

    filename = str(path)

    # ── Lex ──────────────────────────────────────────────────────────────────
    try:
        tokens = _lex(source, filename)
    except TaipanError as e:
        _print_error(e, source, filename)
        return 1

    # ── Parse ─────────────────────────────────────────────────────────────────
    try:
        ast = Parser(tokens, filename).parse()
    except TaipanError as e:
        _print_error(e, source, filename)
        return 1

    # ── Semantic analysis ─────────────────────────────────────────────────────
    errors = _analyze(ast, filename)
    if errors:
        for err in errors:
            print(c("yellow", f"[Semantic Warning] {err}"))

    # ── Transpile ─────────────────────────────────────────────────────────────
    try:
        from taipan.compiler.c_transpiler.transpiler import CTranspiler
        transpiler = CTranspiler()
        c_code = transpiler.transpile(ast)
    except Exception as e:
        print(c("red", f"Transpilation Error: {e}"))
        if os.environ.get("TAIPAN_DEBUG"):
            import traceback
            traceback.print_exc()
        return 1

    # Write temporary C source file
    temp_c_path = path.with_suffix(".c")
    try:
        temp_c_path.write_text(c_code, encoding="utf-8")
    except Exception as e:
        print(c("red", f"Error writing temporary C file: {e}"))
        return 1

    # Determine default output binary name
    if output_exe is None:
        if sys.platform == "win32":
            output_exe = str(path.with_suffix(".exe"))
        else:
            output_exe = str(path.with_suffix(""))
    else:
        output_exe = str(Path(output_exe).resolve())

    # Compile with GCC
    import subprocess
    c_transpiler_dir = Path(__file__).parent.resolve() / "compiler" / "c_transpiler"
    
    cmd = [
        "gcc",
        "-O3",
        "-I", str(c_transpiler_dir),
        str(temp_c_path),
        "-o", output_exe,
        "-lm"
    ]

    print(c("gray", f"Compiling to C and building native binary..."))
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(c("red", "C Compilation Failed!"))
            print(c("yellow", res.stderr))
            return 1
    except Exception as e:
        print(c("red", f"Error running GCC compiler: {e}"))
        print(c("yellow", "Please make sure GCC is installed and on your PATH."))
        return 1
    finally:
        # Clean up temporary C file unless TAIPAN_DEBUG is set
        if not os.environ.get("TAIPAN_DEBUG") and temp_c_path.exists():
            try:
                temp_c_path.unlink()
            except Exception:
                pass

    print(c("green", f"✓ Successfully compiled to native binary: {output_exe}"))
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def _help():
    print(BANNER)
    print("Usage: tai <command> [arguments]")
    print()
    print(c("bold", "Commands:"))
    print(f"  {c('cyan', 'run')}     <file.tp> [--vm] [--ai]  Run a program")
    print(f"  {c('cyan', 'compile')} <file.tp> [-o <out>]     Compile to native executable")
    print(f"  {c('cyan', 'repl')}    [--vm] [--ai]            Interactive REPL")
    print(f"  {c('cyan', 'check')}   <file.tp>                Lint / type-check")
    print(f"  {c('cyan', 'format')}  <file.tp>                Auto-format source code")
    print(f"  {c('cyan', 'test')}    [file|dir]               Run test{{}} blocks")
    print(f"  {c('cyan', 'disasm')}  <file.tp>                Print compiled bytecode")
    print(f"  {c('cyan', 'bench')}   [quick]                  Run VM benchmarks")
    print(f"  {c('cyan', 'doc')}     <file.tp> [-o <out>]     Generate Markdown docs")
    print(f"  {c('cyan', 'tokens')}  <file.tp>                Print lexer tokens (debug)")
    print(f"  {c('cyan', 'ast')}     <file.tp>                Print AST (debug)")
    print(f"  {c('cyan', 'init')}                             Initialize a new project")
    print(f"  {c('cyan', 'build')}                            Build/verify the project")
    print(f"  {c('cyan', 'version')}                          Show version")
    print(f"  {c('cyan', 'help')}                             Show this help")
    print()
    print(c("bold", "Flags:"))
    print(f"  {c('yellow', '--vm')}    Use bytecode VM backend (faster for compute-heavy code)")
    print(f"  {c('yellow', '--ai')}    Show AI-powered fix suggestions on errors")
    print()
    print(c("bold", "Environment:"))
    print(f"  {c('yellow', 'OPENAI_API_KEY')}     Enable OpenAI error explanations")
    print(f"  {c('yellow', 'OLLAMA_HOST')}        Ollama endpoint (default: localhost:11434)")
    print(f"  {c('yellow', 'TAIPAN_DEBUG')}       Show full Python tracebacks")
    print(f"  {c('yellow', 'TAIPAN_AI_ERRORS')}   Always enable AI error explanations")
    print()
    print(c("bold", "Examples:"))
    print(f"  tai run examples/hello_world.tp")
    print(f"  tai run my_prog.tp --ai           # AI fix suggestions on error")
    print(f"  tai run my_prog.tp --vm           # Use bytecode VM")
    print(f"  tai disasm my_prog.tp             # Inspect compiled bytecode")
    print(f"  tai bench quick                   # Quick benchmark")
    print(f"  tai test                          # Run all tests/")
    print(f"  tai repl --ai                     # REPL with AI hints")
    print()


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("help", "--help", "-h"):
        _help()
        return

    if args[0] in ("version", "--version", "-v"):
        print(f"Taipan v{VERSION}")
        print("Python Interpreter Backend & Bytecode VM — Phase 1 & 2")
        return

    cmd  = args[0].lower()
    rest = args[1:]

    match cmd:
        case "run":
            if not rest:
                print(c("red", "Error: specify a .tp file to run."))
                print("  Usage: tai run <file.tp> [--vm] [--ai]")
                sys.exit(1)
            use_vm  = "--vm" in rest
            use_ai  = "--ai" in rest
            rest = [r for r in rest if r not in ("--vm", "--ai")]
            if not rest:
                print(c("red", "Error: specify a .tp file to run."))
                print("  Usage: tai run <file.tp> [--vm] [--ai]")
                sys.exit(1)
            sys.exit(_run_file(rest[0], use_vm=use_vm, use_ai=use_ai))

        case "compile":
            if not rest:
                print(c("red", "Error: specify a .pk file to compile."))
                print("  Usage: python -m taipan compile <file.tp> [-o <output_exe>]")
                sys.exit(1)
            filepath = rest[0]
            output_exe = None
            if "-o" in rest:
                try:
                    idx = rest.index("-o")
                    if idx + 1 < len(rest):
                        output_exe = rest[idx + 1]
                        # Remove them from rest to get the filename if it was after or before
                        rest.pop(idx + 1)
                        rest.pop(idx)
                    else:
                        print(c("red", "Error: specify an output filename after -o."))
                        sys.exit(1)
                except ValueError:
                    pass
            # Check if filename is still in rest after popping -o args
            if not rest:
                print(c("red", "Error: specify a .pk file to compile."))
                sys.exit(1)
            sys.exit(_compile_file(rest[0], output_exe))

        case "repl":
            use_vm = "--vm" in rest
            use_ai = "--ai" in rest
            _run_repl(use_vm=use_vm, use_ai=use_ai)


        case "check":
            if not rest:
                print(c("red", "Error: specify a .pk file to check."))
                sys.exit(1)
            sys.exit(_run_file(rest[0], check_only=True))

        case "format":
            if not rest:
                print(c("red", "Error: specify a .pk file to format."))
                sys.exit(1)
            sys.exit(_format_file(rest[0]))

        case "tokens":
            if not rest:
                print(c("red", "Error: specify a .pk file."))
                sys.exit(1)
            sys.exit(_print_tokens(rest[0]))

        case "ast":
            if not rest:
                print(c("red", "Error: specify a .pk file."))
                sys.exit(1)
            sys.exit(_print_ast(rest[0]))

        case "test":
            target = rest[0] if rest else None
            sys.exit(_run_tests(target))

        case "disasm":
            if not rest:
                print(c("red", "Error: specify a .tp file to disassemble."))
                print("  Usage: tai disasm <file.tp>")
                sys.exit(1)
            sys.exit(_disasm_file(rest[0]))

        case "bench":
            quick = "quick" in rest
            sys.exit(_run_bench(quick=quick))

        case "init":
            from taipan.package_manager.tpkg import cmd_init as _tpkg_init
            sys.exit(_tpkg_init(rest[0] if rest else None))

        case "build":
            from taipan.package_manager.tpkg import cmd_build as _tpkg_build
            sys.exit(_tpkg_build())

        case "doc":
            if not rest:
                print(c("red", "Error: specify a .tp file to document."))
                print("  Usage: python -m taipan doc <file.tp> [-o <output.md>]")
                sys.exit(1)
            filepath = rest[0]
            output = None
            if "-o" in rest:
                try:
                    idx = rest.index("-o")
                    if idx + 1 < len(rest):
                        output = rest[idx + 1]
                    else:
                        print(c("red", "Error: specify an output filename after -o."))
                        sys.exit(1)
                except ValueError:
                    pass
            from taipan.doc_generator import main as _doc_main
            sys.exit(_doc_main(filepath, output))

        case _:
            # Maybe it's a filename directly
            if os.path.exists(cmd) and cmd.endswith(".tp"):
                sys.exit(_run_file(cmd))
            print(c("red", f"Unknown command: '{cmd}'"))
            print("Run 'tai help' for usage.")
            sys.exit(1)


# ── Disassembler ──────────────────────────────────────────────────────────────

def _disasm_file(filepath: str) -> int:
    """Compile and print the bytecode disassembly for a .tp file."""
    path = Path(filepath)
    if not path.exists():
        print(c("red", f"Error: File '{filepath}' not found."))
        return 1
    if path.suffix != ".tp":
        print(c("yellow", f"Warning: '{filepath}' does not have a .tp extension."))

    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        print(c("red", f"Error reading file: {e}"))
        return 1

    filename = str(path)
    try:
        tokens = _lex(source, filename)
        ast    = Parser(tokens, filename).parse()
    except TaipanError as e:
        _print_error(e, source, filename)
        return 1

    try:
        from taipan.compiler.vm.compiler import BytecodeCompiler
        from taipan.compiler.vm.instructions import CodeObject
        co = BytecodeCompiler(name=filename).compile(ast)
    except Exception as e:
        print(c("red", f"Compile error: {e}"))
        return 1

    def _dump(code: CodeObject, depth: int = 0):
        indent = "  " * depth
        asm_lines = code.disassemble().splitlines()
        for i, line in enumerate(asm_lines):
            if i == 0:
                # Header: <CodeObject 'name'>
                print(f"{indent}{c('cyan', line)}")
            else:
                print(f"{indent}{c('gray', line)}")
        for const in code.constants:
            if isinstance(const, CodeObject):
                _dump(const, depth + 1)

    print(c("bold", f"\nBytecode disassembly for '{filepath}':"))
    print(c("gray", "=" * 60))
    _dump(co)

    print()
    return 0


# ── Benchmark runner ──────────────────────────────────────────────────────────

def _run_bench(quick: bool = False) -> int:
    """Run the Taipan benchmark suite."""
    try:
        import sys as _sys
        from pathlib import Path as _Path
        bench_dir = _Path(__file__).parent.parent.parent / "benchmarks"
        _sys.path.insert(0, str(bench_dir.parent))
        import importlib.util
        spec = importlib.util.spec_from_file_location("suite", bench_dir / "suite.py")
        suite = importlib.util.module_from_spec(spec)
        # Inject quick flag via argv trick
        old_argv = _sys.argv
        _sys.argv = ["suite"] + (["--quick"] if quick else [])
        try:
            spec.loader.exec_module(suite)
            if hasattr(suite, "main"):
                suite.main()
        finally:
            _sys.argv = old_argv
        return 0
    except FileNotFoundError:
        print(c("red", "Benchmark suite not found. Expected: benchmarks/suite.py"))
        return 1
    except Exception as e:
        print(c("red", f"Benchmark error: {e}"))
        if os.environ.get("TAIPAN_DEBUG"):
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    main()
