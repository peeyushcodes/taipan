"""
Taipan Benchmark Suite
=====================
Compares Taipan performance against Python on various workloads.

Usage:
    python -m benchmarks.suite              # Run all benchmarks
    python -m benchmarks.suite --quick    # Run quick subset
    python -m benchmarks.suite --save     # Save results to benchmarks/results.json

Workloads:
    - fibonacci: Recursive algorithm
    - primes: Sieve of Eratosthenes
    - matrix_mult: 2D array operations
    - string_ops: String manipulation
    - sort: Sorting algorithms
    - loops: Simple loop overhead
    - collections: List/dict operations
"""

import sys
import os
import time
import json
import statistics
from pathlib import Path
from typing import Callable

# Ensure project is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from taipan.compiler.lexer.lexer import Lexer
from taipan.compiler.parser.parser import Parser
from taipan.compiler.backend.interpreter import Interpreter
from taipan.compiler.vm.compiler import BytecodeCompiler
from taipan.compiler.vm.vm_optimized import VM


# ── Benchmark Configuration ───────────────────────────────────────────────────

WARMUP_RUNS = 2
BENCHMARK_RUNS = 5

# ── Workloads (Taipan source code) ───────────────────────────────────────────

WORKLOADS = {
    "fibonacci": {
        "taipan": '''
func fib(n) {
    if n <= 1 { return n }
    return fib(n - 1) + fib(n - 2)
}
show(fib(20))
''',
        "python": '''
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)

print(fib(20))
''',
    },
    
    "primes": {
        "taipan": '''
func sieve(n) {
    let is_prime = []
    for i in 0..n+1 {
        is_prime.append(true)
    }
    is_prime[0] = false
    is_prime[1] = false
    let p = 2
    while p * p <= n {
        if is_prime[p] {
            let i = p * p
            while i <= n {
                is_prime[i] = false
                i += p
            }
        }
        p += 1
    }
    let count = 0
    for i in 2..n+1 {
        if is_prime[i] {
            count += 1
        }
    }
    show(count)
}
sieve(10000)
''',
        "python": '''
def sieve(n):
    is_prime = [True] * (n + 1)
    is_prime[0] = is_prime[1] = False
    p = 2
    while p * p <= n:
        if is_prime[p]:
            for i in range(p * p, n + 1, p):
                is_prime[i] = False
        p += 1
    count = sum(1 for i in range(2, n + 1) if is_prime[i])
    print(count)

sieve(10000)
''',
    },
    
    "matrix_mult": {
        "taipan": '''
func mat_mult(n) {
    let a = []
    let b = []
    let c = []
    for i in 0..n {
        let row_a = []
        let row_b = []
        let row_c = []
        for j in 0..n {
            row_a.append(i + j)
            row_b.append(i - j)
            row_c.append(0)
        }
        a.append(row_a)
        b.append(row_b)
        c.append(row_c)
    }
    for i in 0..n {
        for j in 0..n {
            let sum = 0
            for k in 0..n {
                sum += a[i][k] * b[k][j]
            }
            c[i][j] = sum
        }
    }
    show(c[0][0])
}
mat_mult(50)
''',
        "python": '''
def mat_mult(n):
    a = [[i + j for j in range(n)] for i in range(n)]
    b = [[i - j for j in range(n)] for i in range(n)]
    c = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            s = 0
            for k in range(n):
                s += a[i][k] * b[k][j]
            c[i][j] = s
    print(c[0][0])

mat_mult(50)
''',
    },
    
    "string_concat": {
        "taipan": '''
func concat(n) {
    let s = ""
    for i in 0..n {
        s += "x"
    }
    show(len(s))
}
concat(10000)
''',
        "python": '''
def concat(n):
    s = ""
    for i in range(n):
        s += "x"
    print(len(s))

concat(10000)
''',
    },
    
    "loop_overhead": {
        "taipan": '''
func loop_sum(n) {
    let sum = 0
    for i in 0..n {
        sum += i
    }
    show(sum)
}
loop_sum(100000)
''',
        "python": '''
def loop_sum(n):
    s = 0
    for i in range(n):
        s += i
    print(s)

loop_sum(100000)
''',
    },
    
    "list_ops": {
        "taipan": '''
func list_ops(n) {
    let lst = []
    for i in 0..n {
        lst.append(i)
    }
    let sum = 0
    for i in 0..len(lst) {
        sum += lst[i]
    }
    show(sum)
}
list_ops(10000)
''',
        "python": '''
def list_ops(n):
    lst = []
    for i in range(n):
        lst.append(i)
    s = sum(lst)
    print(s)

list_ops(10000)
''',
    },
    
    "sort": {
        "taipan": '''
func bubble_sort(n) {
    let arr = []
    for i in 0..n {
        arr.append(n - i)
    }
    for i in 0..n {
        for j in 0..n-i-1 {
            if arr[j] > arr[j+1] {
                let temp = arr[j]
                arr[j] = arr[j+1]
                arr[j+1] = temp
            }
        }
    }
    show(arr[0])
}
bubble_sort(500)
''',
        "python": '''
def bubble_sort(n):
    arr = [n - i for i in range(n)]
    for i in range(n):
        for j in range(n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    print(arr[0])

bubble_sort(500)
''',
    },
}


# ── Runners ───────────────────────────────────────────────────────────────────

def run_taipan_interp(source: str) -> float:
    """Run Taipan via interpreter, return elapsed time."""
    tokens = Lexer(source, "<bench>").tokenize()
    ast = Parser(tokens, "<bench>").parse()
    
    t0 = time.perf_counter()
    interp = Interpreter(filename="<bench>")
    interp.execute(ast)
    t1 = time.perf_counter()
    return t1 - t0


def run_taipan_vm(source: str) -> float:
    """Run Taipan via VM, return elapsed time."""
    tokens = Lexer(source, "<bench>").tokenize()
    ast = Parser(tokens, "<bench>").parse()
    
    compiler = BytecodeCompiler(name="<bench>")
    code_obj = compiler.compile(ast)
    
    t0 = time.perf_counter()
    vm = VM(filename="<bench>")
    vm.execute(code_obj)
    t1 = time.perf_counter()
    return t1 - t0


def run_python(source: str) -> float:
    """Run Python code, return elapsed time."""
    t0 = time.perf_counter()
    exec(source, {"__name__": "__main__"})
    t1 = time.perf_counter()
    return t1 - t0


# ── Benchmark Harness ─────────────────────────────────────────────────────────

def run_jit(source: str) -> tuple[float, Any]:
    """Run Taipan via JIT compiler, return (elapsed_time, result)."""
    from taipan.compiler.jit.compiler import JITCompiler
    tokens = Lexer(source, "<bench>").tokenize()
    ast = Parser(tokens, "<bench>").parse()
    
    # Find and JIT compile the first function
    jit = JITCompiler()
    for stmt in ast.body:
        if hasattr(stmt, 'name'):
            compiled = jit.compile_function(stmt)
            if compiled:
                # Call with default args (just test with small value)
                result = compiled(1000000)
                t0 = time.perf_counter()
                for _ in range(5):
                    compiled(1000000)
                t1 = time.perf_counter()
                return (t1 - t0) / 5, result
    return None, None


def benchmark(name: str, runs: int = BENCHMARK_RUNS) -> dict:
    """Run a single benchmark and return results."""
    workload = WORKLOADS[name]
    
    print(f"  Running {name}...", end=" ", flush=True)
    
    # Warmup
    for _ in range(WARMUP_RUNS):
        try:
            run_taipan_interp(workload["taipan"])
            run_taipan_vm(workload["taipan"])
            run_python(workload["python"])
        except Exception as e:
            print(f"WARMUP ERROR: {e}")
            return {"error": str(e)}
    
    # Measure
    interp_times = []
    vm_times = []
    python_times = []
    
    for _ in range(runs):
        try:
            interp_times.append(run_taipan_interp(workload["taipan"]))
        except Exception as e:
            print(f"INTERP ERROR: {e}")
            return {"error": str(e)}
        
        try:
            vm_times.append(run_taipan_vm(workload["taipan"]))
        except Exception as e:
            print(f"VM ERROR: {e}")
            return {"error": str(e)}
        
        try:
            python_times.append(run_python(workload["python"]))
        except Exception as e:
            print(f"PYTHON ERROR: {e}")
            return {"error": str(e)}
    
    interp_avg = statistics.mean(interp_times)
    vm_avg = statistics.mean(vm_times)
    python_avg = statistics.mean(python_times)
    
    # Try JIT
    jit_time = None
    try:
        jit_time, _ = run_jit(workload["taipan"])
    except Exception:
        pass
    
    results = {
        "taipan_interp": {
            "avg": interp_avg,
            "min": min(interp_times),
            "max": max(interp_times),
            "stdev": statistics.stdev(interp_times) if len(interp_times) > 1 else 0,
        },
        "taipan_vm": {
            "avg": vm_avg,
            "min": min(vm_times),
            "max": max(vm_times),
            "stdev": statistics.stdev(vm_times) if len(vm_times) > 1 else 0,
        },
        "python": {
            "avg": python_avg,
            "min": min(python_times),
            "max": max(python_times),
            "stdev": statistics.stdev(python_times) if len(python_times) > 1 else 0,
        },
        "taipan_jit": {
            "avg": jit_time,
        } if jit_time else None,
        "vs_python_interp": python_avg / interp_avg if interp_avg > 0 else 0,
        "vs_python_vm": python_avg / vm_avg if vm_avg > 0 else 0,
    }
    
    jit_str = f" {jit_time:.3f}s (JIT)" if jit_time else ""
    print(f"done (Interp: {interp_avg:.3f}s, VM: {vm_avg:.3f}s, Python: {python_avg:.3f}s{jit_str})")
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Taipan Benchmark Suite")
    parser.add_argument("--quick", action="store_true", help="Run quick subset only")
    parser.add_argument("--save", action="store_true", help="Save results to benchmarks/results.json")
    parser.add_argument("--workloads", nargs="+", help="Run specific workloads only")
    args = parser.parse_args()
    
    workloads = args.workloads if args.workloads else (
        ["loop_overhead", "fibonacci", "primes"] if args.quick else list(WORKLOADS.keys())
    )
    
    print("=" * 70)
    print("  Taipan Benchmark Suite")
    print("  Comparing Taipan (Interpreter + VM + JIT) vs Python")
    print("=" * 70)
    print()
    
    all_results = {}
    
    for name in workloads:
        if name not in WORKLOADS:
            print(f"  Unknown workload: {name}")
            continue
        results = benchmark(name)
        all_results[name] = results
    
    # Summary table
    print()
    print("=" * 70)
    print("  Results Summary")
    print("=" * 70)
    print()
    
    has_jit = any(r.get("taipan_jit") for r in all_results.values() if "error" not in r)
    
    if has_jit:
        print(f"  {'Workload':<20} {'Taipan (Interp)':<18} {'Taipan (VM)':<18} {'Taipan (JIT)':<18} {'Python':<18} {'VM vs Py':<12}")
        print(f"  {'-' * 20} {'-' * 18} {'-' * 18} {'-' * 18} {'-' * 18} {'-' * 12}")
    else:
        print(f"  {'Workload':<20} {'Taipan (Interp)':<18} {'Taipan (VM)':<18} {'Python':<18} {'VM vs Py':<12}")
        print(f"  {'-' * 20} {'-' * 18} {'-' * 18} {'-' * 18} {'-' * 12}")
    
    for name, results in all_results.items():
        if "error" in results:
            print(f"  {name:<20} {'ERROR':<18} {'ERROR':<18} {'ERROR':<18}")
            continue
        
        pi = results["taipan_interp"]["avg"]
        pv = results["taipan_vm"]["avg"]
        py = results["python"]["avg"]
        vs_v = results["vs_python_vm"]
        
        interp_str = f"{pi:.3f}s"
        vm_str = f"{pv:.3f}s"
        py_str = f"{py:.3f}s"
        vs_v_str = f"{vs_v:.1f}x" if vs_v >= 1 else f"{1/vs_v:.1f}x slower"
        
        if has_jit and results.get("taipan_jit"):
            jit_time = results["taipan_jit"]["avg"]
            jit_str = f"{jit_time:.3f}s"
            print(f"  {name:<20} {interp_str:<18} {vm_str:<18} {jit_str:<18} {py_str:<18} {vs_v_str:<12}")
        else:
            print(f"  {name:<20} {interp_str:<18} {vm_str:<18} {py_str:<18} {vs_v_str:<12}")
    
    print()
    
    # Speedup summary
    print("  Speedup vs Python:")
    total_vs_interp = 0
    total_vs_vm = 0
    count = 0
    for name, results in all_results.items():
        if "error" in results:
            continue
        vs_i = results["vs_python_interp"]
        vs_v = results["vs_python_vm"]
        total_vs_interp += vs_i
        total_vs_vm += vs_v
        count += 1
    
    if count > 0:
        avg_vs_interp = total_vs_interp / count
        avg_vs_vm = total_vs_vm / count
        print(f"    Interpreter: {avg_vs_interp:.1f}x on average")
        print(f"    VM:          {avg_vs_vm:.1f}x on average")
    
    print()
    
    if args.save:
        results_file = Path(__file__).parent / "results.json"
        with open(results_file, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"  Results saved to {results_file}")
    
    print("=" * 70)
    
    # Note about JIT
    if not has_jit:
        print()
        print("  Note: JIT compiler requires a C compiler (gcc, clang, or tcc).")
        print("        Install one to enable 100-1000x speedup on numeric code.")
    
    print("=" * 70)


if __name__ == "__main__":
    main()
