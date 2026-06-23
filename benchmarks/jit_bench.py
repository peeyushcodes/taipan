"""
JIT Benchmark — Compare interpreter vs JIT-compiled native code
=================================================================
Usage:
    PYTHONPATH=src python benchmarks/jit_bench.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from taipan.compiler.lexer.lexer import Lexer
from taipan.compiler.parser.parser import Parser
from taipan.compiler.backend.interpreter import Interpreter
from taipan.compiler.jit.compiler import JITCompiler

# Simple numeric function
SOURCE = '''
func loop_sum(n: Int) -> Int {
    let sum = 0
    for i in 0..n {
        sum += i
    }
    return sum
}

show(loop_sum(1000000))
'''

def main():
    print("=" * 60)
    print("  Taipan JIT Compiler Benchmark")
    print("=" * 60)
    print()

    # Parse
    tokens = Lexer(SOURCE, "<bench>").tokenize()
    ast = Parser(tokens, "<bench>").parse()

    # Find the function
    func = None
    for stmt in ast.body:
        if hasattr(stmt, 'name') and stmt.name == 'loop_sum':
            func = stmt
            break

    if not func:
        print("Function not found!")
        return

    # JIT compile
    print("JIT Compiling loop_sum(n: Int) -> Int...")
    jit = JITCompiler()
    compiled = jit.compile_function(func)

    if compiled:
        print("  [OK] JIT compilation successful!")
        print()

        # Warmup
        for _ in range(3):
            compiled(1000000)

        # Benchmark JIT
        t0 = time.perf_counter()
        for _ in range(5):
            result = compiled(1000000)
        t1 = time.perf_counter()
        jit_time = (t1 - t0) / 5

        print(f"  JIT result: {result}")
        print(f"  JIT time:   {jit_time:.4f}s")
    else:
        print("  [FAIL] JIT compilation failed (no C compiler or unsupported code)")
        print()

    # Benchmark interpreter
    print("Running interpreter...")
    t0 = time.perf_counter()
    for _ in range(5):
        interp = Interpreter(filename="<bench>")
        interp.execute(ast)
    t1 = time.perf_counter()
    interp_time = (t1 - t0) / 5

    print(f"  Interpreter time: {interp_time:.4f}s")
    print()

    if compiled:
        speedup = interp_time / jit_time
        print(f"  Speedup: {speedup:.1f}x")
    print("=" * 60)

if __name__ == "__main__":
    main()
