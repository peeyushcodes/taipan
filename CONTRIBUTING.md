# Contributing to Taipan

Thank you for your interest in contributing to Taipan! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- (Optional) Node.js for VS Code extension development
- (Optional) Ollama for local AI testing

### Clone and Install

```bash
git clone https://github.com/peeyush/taipan.git
cd taipan
pip install -e ".[dev]"
```

### Verify Installation

```bash
tai --help
peek --help
tai run examples/hello_world.pk
```

## Project Structure

```
taipan/
├── src/taipan/              # Core source code
│   ├── compiler/             # Compiler pipeline
│   │   ├── lexer/            # Tokenizer
│   │   ├── parser/           # Recursive descent parser
│   │   ├── ast/              # AST node definitions
│   │   ├── semantic/         # Semantic analyzer + type checker
│   │   ├── backend/          # Tree-walk interpreter
│   │   ├── vm/               # Bytecode compiler + VM
│   │   └── c_transpiler/     # C code generator
│   ├── runtime/              # Execution environment
│   │   ├── errors.py         # Error hierarchy
│   │   ├── pretty_errors.py  # Professional error formatting
│   │   ├── ai_errors.py     # AI-powered error suggestions
│   │   ├── environment.py    # Variable scopes
│   │   └── taipan_types.py  # Taipan value types
│   ├── stdlib/               # Standard library modules
│   │   ├── math_module.py
│   │   ├── string_module.py
│   │   ├── json_module.py
│   │   ├── time_module.py
│   │   ├── file_module.py
│   │   ├── collections_module.py
│   │   ├── network_module.py
│   │   └── ai_module.py
│   ├── lsp/                  # Language Server Protocol
│   │   └── server.py         # JSON-RPC LSP server
│   ├── package_manager/       # Package manager
│   │   └── peek.py           # peek CLI
│   └── cli.py                # Main tai CLI
├── tests/                     # Test suite
├── examples/                  # Example programs
├── docs/                      # Documentation
├── vscode_extension/          # VS Code extension
├── pyproject.toml             # Modern Python packaging
└── README.md
```

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_interpreter.py -v

# Run with coverage
python -m pytest tests/ --cov=taipan --cov-report=html
```

## Adding a New Feature

### 1. Add Lexer Token (if needed)

Edit `src/taipan/compiler/lexer/tokens.py`:

```python
class TokenType(Enum):
    # ... existing tokens ...
    MY_NEW_KEYWORD = auto()

KEYWORDS = {
    # ... existing keywords ...
    "mykeyword": TokenType.MY_NEW_KEYWORD,
}
```

### 2. Add AST Node

Edit `src/taipan/compiler/ast/nodes.py`:

```python
@dataclass(kw_only=True)
class MyNewStmt(Node):
    """Description of the new statement."""
    body: Block
```

### 3. Add Parser Rule

Edit `src/taipan/compiler/parser/parser.py`:

```python
def _parse_statement(self) -> Node:
    match tok.type:
        # ... existing cases ...
        case TokenType.MY_NEW_KEYWORD:
            return self._parse_my_new_stmt()

def _parse_my_new_stmt(self) -> MyNewStmt:
    tok = self._expect(TokenType.MY_NEW_KEYWORD)
    body = self._parse_block()
    return MyNewStmt(body=body, line=tok.line, column=tok.column)
```

### 4. Add Interpreter Handler

Edit `src/taipan/compiler/backend/interpreter.py`:

```python
def _exec_MyNewStmt(self, node: MyNewStmt):
    # Implementation here
    self._exec(node.body)
```

### 5. Add Test

Create or edit a test file in `tests/`:

```python
def test_my_new_feature():
    r = run('''
        mykeyword {
            show("it works!")
        }
    ''')
    assert r == "it works!"
```

### 6. Update Documentation

- Add the feature to `README.md`
- Add examples to `docs/README.md`
- Update the language tour if applicable

## Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Add docstrings to all public functions and classes
- Keep functions focused and under 50 lines when possible
- Write tests for all new features

## Commit Messages

Use conventional commits:

```
feat: add pattern matching support
fix: resolve memory leak in VM
perf: optimize list.append() by 20%
docs: update installation instructions
test: add tests for AI error explanations
refactor: restructure compiler into src layout
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes with tests
4. Run the full test suite (`python -m pytest tests/ -v`)
5. Commit with conventional commit messages
6. Push to your fork and open a Pull Request
7. Describe what your PR does and why

## Reporting Issues

When reporting bugs, please include:

- Taipan version (`tai version`)
- Python version (`python --version`)
- Operating system
- Minimal code example that reproduces the issue
- Expected vs actual behavior
- Full error message (run with `TAIPAN_DEBUG=1` for tracebacks)

## Areas Needing Help

- **Performance**: JIT compilation, WebAssembly target
- **Ecosystem**: Package registry website, more stdlib modules
- **Tooling**: IDE plugins (IntelliJ, Vim, Emacs, Sublime)
- **Documentation**: Tutorials, API docs, language specification
- **Testing**: More edge case tests, property-based testing
- **AI Features**: Better error explanations, code generation, documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for helping make Taipan better! 🚀
