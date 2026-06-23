"""
Taipan Performance Benchmark
=============================
Compares Interpreter vs Bytecode VM vs AOT C Compiled performance.
Run: python -m taipan.benchmark
"""
import time
import sys
import os
import tempfile
import subprocess
from pathlib import Path

from taipan.compiler.lexer.lexer import Lexer
from taipan.compiler.parser.parser import Parser
from taipan.compiler.vm.compiler import BytecodeCompiler
from taipan.compiler.vm.vm_optimized import VM
from taipan.compiler.backend.interpreter import Interpreter
from taipan.cli import _compile_file


BENCHMARKS = {
    "fibonacci(20)": """
func fib(n) {
    if n <= 1 { return n }
    return fib(n - 1) + fib(n - 2)
}
show(fib(20))
""",
    "loop_1M": """
let i = 0
while i < 1000000 {
    i += 1
}
show(i)
""",
    "list_ops": """
let lst = []
for i in 1..10000 {
    lst.append(i)
}
show(len(lst))
""",
    "math_heavy": """
let sum = 0
for i in 1..100000 {
    sum += i * i + i / 2
}
show(sum)
""",
}


def run_benchmark(name: str, source: str, iterations: int = 3):
    print(f"\n{'='*60}")
    print(f"Benchmark: {name}")
    print(f"{'='*60}")

    # Compile AST once
    tokens = Lexer(source, "<bench>").tokenize()
    ast = Parser(tokens, "<bench>").parse()

    # --- Interpreter ---
    interp_times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        interp = Interpreter(filename="<bench>")
        # Redirect print to avoid console clutter during benchmark
        import io
        import builtins
        old_print = builtins.print
        builtins.print = lambda *a, **k: None
        try:
            interp.execute(ast)
        finally:
            builtins.print = old_print
        t1 = time.perf_counter()
        interp_times.append(t1 - t0)
    interp_avg = sum(interp_times) / len(interp_times)

    # --- VM ---
    try:
        vm_times = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            compiler = BytecodeCompiler(name="<bench>")
            code_obj = compiler.compile(ast)
            vm = VM(filename="<bench>")
            old_print = builtins.print
            builtins.print = lambda *a, **k: None
            try:
                vm.execute(code_obj)
            finally:
                builtins.print = old_print
            t1 = time.perf_counter()
            vm_times.append(t1 - t0)
        vm_avg = sum(vm_times) / len(vm_times)
    except Exception as e:
        vm_avg = None
        print(f"  VM Error: {e}")

    # --- C Compiled ---
    try:
        c_times = []
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            pk_file = tmpdir_path / "bench.tp"
            pk_file.write_text(source, encoding="utf-8")
            exe_file = tmpdir_path / "bench.exe" if sys.platform == "win32" else tmpdir_path / "bench"
            
            # Suppress CLI compilation output
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                ret = _compile_file(str(pk_file), str(exe_file))
            finally:
                sys.stdout = old_stdout

            if ret == 0 and exe_file.exists():
                for _ in range(iterations):
                    t0 = time.perf_counter()
                    res = subprocess.run([str(exe_file)], capture_output=True, text=True)
                    t1 = time.perf_counter()
                    c_times.append(t1 - t0)
                c_avg = sum(c_times) / len(c_times)
            else:
                c_avg = None
    except Exception as e:
        c_avg = None
        print(f"  C Compiler Error: {e}")

    print(f"  Interpreter:  {interp_avg:.6f}s")
    if vm_avg is not None:
        print(f"  Bytecode VM:  {vm_avg:.6f}s  ({interp_avg / vm_avg:.2f}x speedup vs Interp)" if vm_avg < interp_avg else f"  Bytecode VM:  {vm_avg:.6f}s  ({vm_avg / interp_avg:.2f}x slower vs Interp)")
    else:
        print(f"  Bytecode VM:  N/A")
        
    if c_avg is not None:
        print(f"  C Compiled:   {c_avg:.6f}s  ({interp_avg / c_avg:.2f}x speedup vs Interp)")
    else:
        print(f"  C Compiled:   N/A")
        
    return interp_avg, vm_avg, c_avg


def main():
    print("=" * 60)
    print("Taipan Performance Benchmark (Interpreter vs VM vs C)")
    print("=" * 60)

    results = {}
    for name, source in BENCHMARKS.items():
        results[name] = run_benchmark(name, source)

    print("\n" + "=" * 60)
    print("Summary Comparison (Speedup relative to Interpreter)")
    print("=" * 60)
    print(f"{'Benchmark':<18} | {'Interpreter':<12} | {'Bytecode VM':<15} | {'C Compiled':<15}")
    print("-" * 65)
    for name, (interp, vm, c_val) in results.items():
        vm_str = f"{interp/vm:.2f}x" if vm else "N/A"
        c_str = f"{interp/c_val:.2f}x" if c_val else "N/A"
        print(f"{name:<18} | {'1.00x':<12} | {vm_str:<15} | {c_str:<15}")


if __name__ == "__main__":
    main()
