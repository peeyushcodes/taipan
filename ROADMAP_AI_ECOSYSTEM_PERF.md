# Taipan — Strategic Roadmap: AI, Ecosystem & Performance

> **Focus:** Make Taipan the world's first *truly AI-native* programming language.

---

## ✅ What We Just Implemented

### 1. AI Features (Sprint 0 — Done Today)

| Feature | File | Status |
|---|---|---|
| **Fix `import ai` conflict** | `compiler/parser/parser.py` | ✅ `ai` keyword now works as module name |
| **AI-powered error explanations** | `runtime/ai_errors.py` | ✅ Errors include AI suggestions when `TAIPAN_AI_ERRORS=1` |
| **Local LLM support (Ollama)** | `stdlib/ai_module.py` | ✅ Ollama → OpenAI → Mock fallback chain |
| **F-strings verified** | `compiler/lexer/lexer.py` | ✅ `f"Hello, {name}!"` already works! |

**How to use AI error explanations:**
```bash
set TAIPAN_AI_ERRORS=1          # Windows
export TAIPAN_AI_ERRORS=1       # Linux/macOS

tai run my_program.pk            # Errors now include AI fix suggestions!
```

**How to use local LLM (free, private, no API keys):**
```bash
# 1. Install Ollama: https://ollama.com
# 2. Pull a model: ollama pull llama3.2
# 3. Run Ollama server: ollama serve

tai run examples/ai_demo.pk      # Uses local LLM, no OpenAI needed!
```

### 2. Ecosystem (Sprint 0 — Done Today)

| Feature | File | Status |
|---|---|---|
| **Fix `peek` Unicode crash** | `package_manager/peek.py` | ✅ Replaced `●` with `*` for Windows cp1252 |

**What already works (Python interop):**
```pk
import requests
let resp = requests.get("https://api.example.com")
show(resp.status_code)
```
Taipan's interpreter already falls back to Python `importlib` for unknown modules!

### 3. Performance (Sprint 0 — Benchmarked Today)

**Benchmark Results:**

| Workload | Interpreter | VM | VM Speedup |
|---|---|---|---|
| `fibonacci(20)` | 0.17s | 0.20s | **0.89x** (slower!) |
| `loop_1M` | 5.29s | 6.62s | **0.80x** (slower!) |
| `list_ops` | 0.07s | 0.10s | **0.75x** (slower!) |
| `math_heavy` | 0.75s | 1.07s | **0.70x** (slower!) |

**Critical insight:** The VM is currently **slower** than the tree-walk interpreter. This is expected for a simple bytecode VM that still does Python-level dispatch per instruction. The VM needs:
- Direct opcode dispatch (not `if/elif` chain)
- Inline caching for attribute lookups
- Peephole optimizations (constant folding, dead code elimination)
- A proper benchmark suite to measure progress

---

## 🚀 Next 3 Sprints — Concrete Implementation Plan

### Sprint 1: AI-Native Killer Features (2 Weeks)

**Goal:** Make Taipan the only language where AI is a first-class citizen, not an add-on.

#### 1.1 `ai explain` — Interactive Error Tutor
When a runtime error occurs, the REPL should:
```
tai> let x = "hello" + 5
[Line 1:9] TaipanTypeError: Operator '+' cannot be applied to String and Int

┌─ AI Explanation ───────────────────────┐
│ You're trying to add a number to text. │
│ Fix: convert the number to a string:   │
│   let x = "hello" + str(5)             │
│ Or use an f-string:                    │
│   let x = f"hello{5}"                  │
└────────────────────────────────────────┘
```

**Implementation:** Already started in `runtime/ai_errors.py`. Need to:
- [ ] Wire it into the REPL (`_run_repl` in `taipan.py`)
- [ ] Cache AI explanations so repeated errors don't re-call the API
- [ ] Add `--ai` flag to CLI: `tai run --ai myfile.tp`

#### 1.2 `ai refactor` — Code Transformation
```pk
// Before
let result = []
for i in 1..10 {
    if i % 2 == 0 {
        result.append(i * 2)
    }
}

// After running `ai refactor`
let result = [i * 2 for i in 1..10 if i % 2 == 0]
```

**Implementation:**
- [ ] New CLI command: `tai refactor <file.tp>`
- [ ] Sends source + "refactor this" prompt to AI
- [ ] Applies diff to file after user confirmation

#### 1.3 `ai doc` — Auto-Documentation
```bash
tai doc func my_function        # Generate docstring
tai doc class MyClass           # Generate class docs
tai doc --all src/              # Document entire project
```

**Implementation:**
- [ ] Parse function signatures from AST
- [ ] Send to AI with "document this function" prompt
- [ ] Insert comments above function declarations

#### 1.4 `ai test` — AI-Generated Unit Tests
```bash
tai test --ai                   # Generate tests for untested functions
tai test --ai func my_func      # Generate tests for specific function
```

**Implementation:**
- [ ] Read function AST
- [ ] Generate edge cases (null, empty, negative, large values)
- [ ] Output `.pk` test files in `tests/` directory

#### 1.5 AI Assistant in REPL (`ai myBot` enhanced)
```
tai> ai myBot
tai> myBot.explain("What is a closure?")
A closure is a function that captures variables from its enclosing scope...
tai> myBot.review(my_code)
Your code has a potential null pointer issue on line 5...
```

**Implementation:**
- [ ] Add new methods to `PeeAI` class: `explain`, `review`, `suggest`
- [ ] REPL integration: special commands starting with `?`

### Sprint 2: Ecosystem & Developer Experience (2 Weeks)

**Goal:** Make Taipan usable for real projects.

#### 2.1 Language Server Protocol (LSP)
This is the #1 adoption blocker. Every modern language needs IDE support.

**Features:**
- [ ] Autocomplete (show methods on `list`, `map`, `string`)
- [ ] Hover docs (hover over `math.sqrt` → `sqrt(x: Float) -> Float`)
- [ ] Go to definition (Ctrl+Click on function names)
- [ ] Real-time error squiggles (parse file continuously, show errors)
- [ ] Symbol outline (class/function tree in VS Code sidebar)

**Implementation:**
- [ ] Create `lsp/` package with `taipan-lsp` CLI
- [ ] Use `pygls` (Python LSP framework) — saves months of work
- [ ] Hook into existing lexer/parser for diagnostics
- [ ] Build completion engine from stdlib + user-defined symbols

#### 2.2 Real Package Registry (`peek` upgrade)
Currently `peek` wraps PyPI. Build a real Taipan registry:

```bash
tai publish mylib v1.0.0        # Upload to registry.taipan.dev
tai install @peeyush/web        # Scoped packages
tai search "http server"         # Search registry
tai info @peeyush/web           # Show package info
```

**Implementation:**
- [ ] Simple HTTP registry server (Node.js/Go/Python)
- [ ] Package format: `.tar.gz` with `.pk` files + `peek.toml`
- [ ] Version resolution (semver)
- [ ] `peek.toml` dependency resolution

#### 2.3 Built-in Test Runner (`tai test`)
```pk
// test_math.pk
test "addition works" {
    let result = add(2, 3)
    assert(result == 5)
}

test "division by zero throws" {
    let err = catch { 10 / 0 }
    assert(err != null)
}
```

```bash
tai test                        # Run all tests/ *.tp files
tai test --verbose              # Show each test
tai test --watch                # Re-run on file changes
```

**Implementation:**
- [ ] Add `test` keyword to lexer/parser
- [ ] Test runner in `taipan.py` or separate `pee_test.py`
- [ ] Collect pass/fail statistics
- [ ] `--watch` mode with `watchdog` library

#### 2.4 Python Interop Layer (Formalize)
Already partially works! Just needs polish:

```pk
import python "numpy" as np
let arr = np.array([1, 2, 3])
show(arr.mean())
```

**Implementation:**
- [ ] `import python "module" as alias` syntax (or `import python:module`)
- [ ] Automatic type conversion (PeeList ↔ Python list, PeeMap ↔ dict)
- [ ] Error translation (Python exceptions → Taipan errors)
- [ ] Documentation: "Using Python Libraries in Taipan"

#### 2.5 Web Framework Skeleton
```pk
// server.pk
import web

route "/hello/{name}" {
    return f"Hello, {name}!"
}

web.run(port: 8080)
```

**Implementation:**
- [ ] `stdlib/web_module.py` wrapping Flask/FastAPI
- [ ] `route` decorator or DSL
- [ ] JSON request/response handling

### Sprint 3: Performance (3 Weeks)

**Goal:** Make the VM faster than the interpreter. Target: 5-10x speedup.

#### 3.1 VM Optimization (Immediate Wins)

**Current problem:** VM is 0.7-0.9x interpreter speed. Why?
- Python `if/elif` chain for opcode dispatch (slow)
- No inline caching for attribute access
- No peephole optimizations
- No constant folding

**Fixes:**
- [ ] **Direct dispatch table:** Replace `if/elif` with `dict[opcode] → function` (easy, 10-20% speedup)
- [ ] **Inline caching:** Cache `obj.attr` → `offset` lookups (harder, 30-50% speedup)
- [ ] **Peephole optimizer:** Fold `LOAD_CONST 2; LOAD_CONST 3; ADD` → `LOAD_CONST 5` (medium, 5-15% speedup)
- [ ] **Stack preallocation:** Pre-allocate stack list instead of `.append()`/`.pop()` (easy, 5-10% speedup)

#### 3.2 JIT Compilation (Research Phase)
- [ ] Study `numba` for simple JIT of numeric loops
- [ ] Or study `pyjion` / `pypy` approaches
- [ ] Target: 50-100x speedup on numeric code

#### 3.3 WebAssembly Target
- [ ] Compile Taipan → WASM via `wasmtime` or `wasmer`
- [ ] Run in browser, on serverless, on embedded devices
- [ ] This is the "killer feature" for deployment flexibility

#### 3.4 Memory Management
- [ ] Add reference counting or tracing GC
- [ ] Currently likely leaks memory on long-running programs
- [ ] Profile with `tracemalloc` to find leaks

---

## 🎯 The "Best Language Ever" Positioning

Taipan should not compete with Python/Rust/Go on their turf. Instead, own this niche:

> **"Taipan — The AI-Native Programming Language"**

### What makes this unique?

| Language | AI Support |
|---|---|
| Python | `import openai` — external library, manual integration |
| JavaScript | `fetch()` to API — external service, manual integration |
| Rust | No built-in AI; use crates |
| **Taipan** | `ai myBot`, `ai.explain()`, `ai.refactor()` — **first-class, built-in** |

### The Vision

1. **For beginners:** AI teaches you as you code. Errors explain *why*, not just *what*.
2. **For productivity:** AI writes tests, docs, and refactors. You focus on logic.
3. **For deployment:** Compile to WASM, run anywhere. No runtime needed.
4. **For performance:** VM + JIT for speed. Python interop for ecosystem access.

---

## 📋 Immediate Next Steps (This Week)

1. [ ] Wire `runtime/ai_errors.py` into REPL (`_run_repl` in `taipan.py`)
2. [ ] Add `--ai` CLI flag to `tai run` and `tai repl`
3. [ ] Document AI features in `docs/README.md` (Ollama setup, `TAIPAN_AI_ERRORS`)
4. [ ] Profile VM to find why it's slower than interpreter
5. [ ] Start LSP research — read `pygls` documentation
6. [ ] Design `test` keyword syntax and parser rules

---

## 🏗 Files Changed Today

| File | Change |
|---|---|
| `compiler/parser/parser.py` | Allow `AI` token in import + expression contexts |
| `runtime/ai_errors.py` | **NEW** — AI-powered error explanations |
| `stdlib/ai_module.py` | Added Ollama local LLM support |
| `package_manager/peek.py` | Fixed Windows Unicode crash |
| `taipan.py` | Wired AI error formatting into `_run_file` |
| `benchmark.py` | **NEW** — VM vs interpreter benchmark |

---

*Built with ❤ by Peeyush — Next update after Sprint 1 completion.*
