# Taipan Language Reference

> **Taipan** — A Modern Python Successor  
> Version 1.0.0 · Phase 1: Tree-Walk Interpreter  
> File extension: `.tp` · Run with: `python -m taipan run <file.tp>`  
> **VS Code Extension v2.0.0** with LSP (diagnostics, autocomplete, hover docs)

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [CLI Usage](#cli-usage)
3. [Variables & Constants](#variables--constants)
4. [Types](#types)
5. [Operators](#operators)
6. [Control Flow](#control-flow)
7. [Functions](#functions)
8. [Classes & OOP](#classes--oop)
9. [Collections](#collections)
10. [Error Handling](#error-handling)
11. [Concurrency](#concurrency)
12. [AI Features](#ai-features)
13. [Modules & Imports](#modules--imports)
14. [Standard Library](#standard-library)
15. [Built-in Functions](#built-in-functions)
16. [Package Manager — tpkg](#package-manager--tpkg)
17. [VS Code Extension](#vs-code-extension)
18. [Roadmap](#roadmap)

---

## Quick Start

### Installation

No installation needed — just Python 3.10+:

```bash
git clone https://github.com/peeyush/taipan
cd taipan
python -m taipan run examples/hello_world.tp
```

### Hello World

```tp
show("Hello, World!")
```

### Your first program

```tp
let name = input("What is your name? ")
show("Hello, " + name + "!")

let age = 19
if age >= 18 {
    show("You are an adult.")
}
else {
    show("You are a minor.")
}
```

---

## CLI Usage

```
python -m taipan <command> [arguments]
```


| Command | Description |
|---|---|
| `run <file.tp>` | Run a Taipan source file |
| `repl` | Launch interactive REPL |
| `check <file.tp>` | Lint / type-check only |
| `format <file.tp>` | Auto-format source code |
| `tokens <file.tp>` | Print lexer tokens (debug) |
| `ast <file.tp>` | Print the parsed AST (debug) |
| `version` | Show version info |
| `help` | Show help message |

### Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Enable real AI features |
| `TAIPAN_DEBUG` | Show full Python tracebacks |

---

## Variables & Constants

### Variables (`let`)

```tp
let x = 42
let name = "Peeyush"
let flag = true
let nothing = null
```

### Typed Variables

```tp
let age:   Int    = 19
let price: Float  = 9.99
let label: String = "Taipan"
let ok:    Bool   = true
```

### Constants (`const`)

```tp
const PI        = 3.14159
const MAX_USERS = 1000
const APP_NAME  = "Taipan"
```

Constants cannot be reassigned after declaration.

### Assignment

```tp
let x = 0
x = 10        // simple assignment
x += 5        // augmented: x = x + 5
x -= 2        // x = x - 2
x *= 3        // x = x * 3
x /= 4        // x = x / 4
```

---

## Types

### Primitive Types

| Type | Example | Notes |
|---|---|---|
| `Int` | `42`, `-7`, `1_000_000` | Arbitrary precision |
| `Float` | `3.14`, `2.5e10` | 64-bit double |
| `String` | `"hello"`, `'world'` | UTF-8, immutable |
| `Bool` | `true`, `false` | |
| `Null` | `null` | Absence of value |

### Numeric Literals

```tp
let a = 1_000_000    // underscores for readability
let b = 0xFF         // not yet — use int("0xFF", 16)
let c = 1.5e3        // scientific notation → 1500.0
```

### String Escape Sequences

| Escape | Meaning |
|---|---|
| `\n` | Newline |
| `\t` | Tab |
| `\r` | Carriage return |
| `\\` | Backslash |
| `\"` | Double quote |
| `\'` | Single quote |
| `\0` | Null character |

---

## Operators

### Arithmetic

```tp
5 + 3     // 8
10 - 4    // 6
3 * 7     // 21
10 / 4    // 2.5
10 // 4   // 2  (floor division)
10 % 3    // 1  (modulo)
2 ** 10   // 1024 (power)
-5        // unary negation
```

### Comparison

```tp
5 == 5    // true
5 != 6    // true
3 < 5     // true
5 > 3     // true
5 <= 5    // true
6 >= 5    // true
```

### Logical

```tp
true and false   // false
true or false    // true
not true         // false
!false           // true  (alias)
```

### Membership

```tp
"a" in ["a", "b", "c"]   // true
5 in 1..10                // true
"key" in {"key": 1}       // true
```

### Range (`..`)

```tp
1..10     // 1, 2, 3, ..., 9  (exclusive end)
```

---

## Control Flow

### If / Else

```tp
if x > 10 {
    show("big")
}
else if x > 5 {
    show("medium")
}
else {
    show("small")
}
```

### While Loop

```tp
let i = 0
while i < 10 {
    show(i)
    i += 1
}
```

### For Loop (range)

```tp
for i in 1..10 {
    show(i)        // prints 1 through 9
}
```

### For Loop (collection)

```tp
let fruits = ["apple", "banana", "cherry"]
for fruit in fruits {
    show(fruit)
}

let person = {"name": "Peeyush", "age": 19}
for key in person {
    show(key + " = " + str(person[key]))
}
```

### Repeat Loop

```tp
repeat 5 {
    show("Hello!")
}
```

### Break & Continue

```tp
for i in 1..100 {
    if i == 5 { break }      // exit loop
    if i % 2 == 0 { continue } // skip even
    show(i)
}
```

---

## Functions

### Basic Function

```tp
func greet(name) {
    show("Hello, " + name + "!")
}

greet("Peeyush")
```

### Return Values

```tp
func add(a, b) {
    return a + b
}

let result = add(3, 4)
show(result)   // 7
```

### Typed Parameters & Return Type

```tp
func multiply(a: Int, b: Int) -> Int {
    return a * b
}
```

### Default Parameters

```tp
func greet(name, greeting = "Hello") {
    show(greeting + ", " + name + "!")
}

greet("Peeyush")           // Hello, Peeyush!
greet("Peeyush", "Hola")  // Hola, Peeyush!
```

### Recursion

```tp
func factorial(n) {
    if n <= 1 { return 1 }
    return n * factorial(n - 1)
}

show(factorial(10))   // 3628800
```

### First-Class Functions

```tp
func apply(value, fn) {
    return fn(value)
}

func double(x) { return x * 2 }

show(apply(5, double))   // 10
```

---

## Classes & OOP

### Basic Class

```tp
class Dog {
    let name
    let breed

    func init(name, breed) {
        self.name  = name
        self.breed = breed
    }

    func bark() {
        show(self.name + " says: Woof!")
    }

    func info() {
        show(self.name + " is a " + self.breed)
    }
}

let rex = Dog("Rex", "German Shepherd")
rex.bark()
rex.info()
```

### Inheritance

```tp
class Animal {
    let name
    let sound

    func init(name, sound) {
        self.name  = name
        self.sound = sound
    }

    func speak() {
        show(self.name + ": " + self.sound)
    }
}

class Cat extends Animal {
    func init(name) {
        self.name  = name
        self.sound = "Meow!"
    }

    func purr() {
        show(self.name + " purrs...")
    }
}

let luna = Cat("Luna")
luna.speak()
luna.purr()
```

### Accessing Fields

```tp
let dog = Dog("Buddy", "Labrador")
show(dog.name)    // Buddy
dog.name = "Max"  // Mutation allowed
```

---

## Collections

### List

```tp
let nums = [1, 2, 3, 4, 5]
nums.append(6)
nums.remove(3)
let first = nums[0]
let count = len(nums)

nums.sort()
nums.reverse()
show(nums.contains(4))    // true
show(nums.join(", "))     // "1, 2, 4, 5, 6"
```

| Method | Description |
|---|---|
| `append(val)` | Add to end |
| `pop()` | Remove & return last |
| `remove(val)` | Remove first occurrence |
| `insert(i, val)` | Insert at index |
| `clear()` | Remove all elements |
| `sort()` | Sort in place |
| `reverse()` | Reverse in place |
| `contains(val)` | Membership check |
| `index(val)` | First index of val |
| `count(val)` | Count occurrences |
| `slice(start, end)` | Return sub-list |
| `join(sep)` | Join to string |
| `copy()` | Shallow copy |
| `extend(list)` | Extend with another list |

### Map (Dictionary)

```tp
let user = {
    "name": "Peeyush",
    "age":  19,
    "city": "India"
}

show(user["name"])          // Peeyush
user["email"] = "p@p.com"  // Add key
show(user.keys())           // ["name", "age", "city", "email"]
show(user.has("age"))       // true
user.remove("city")
```

| Method | Description |
|---|---|
| `get(key, default)` | Get with fallback |
| `set(key, val)` | Set key |
| `remove(key)` | Delete key |
| `has(key)` | Check if key exists |
| `keys()` | List of keys |
| `values()` | List of values |
| `items()` | List of [key, val] tuples |
| `clear()` | Remove all |
| `update(map)` | Merge another map |
| `copy()` | Shallow copy |

### Set

```tp
let s = set([1, 2, 2, 3, 3])   // {1, 2, 3}
s.add(4)
s.remove(2)
show(s.has(3))       // true
let u = s.union(set([5, 6]))
let i = s.intersect(set([3, 4]))
```

### Tuple

```tp
let point = (10, 20, 30)
show(point[0])       // 10
show(len(point))     // 3
show(point.contains(20))  // true
let lst = point.toList()
```

### Range

```tp
for i in 1..10 {
    show(i)    // 1 through 9
}

let r = range(0, 100, 2)   // even numbers 0..98
for n in r { show(n) }
```

---

## Error Handling

### Try / Catch

```tp
try {
    let result = 10 / 0
}
catch err {
    show("Error caught: " + err)
}
```

### Custom Error Messages

```tp
func safe_sqrt(n) {
    try {
        if n < 0 {
            // Force an error
            let x = "not a number" + 1
        }
        return n ** 0.5
    }
    catch err {
        show("Cannot take sqrt of negative: " + err)
        return null
    }
}
```

---

## Concurrency

Taipan provides true multi-threading with no GIL limitation at the language level.

### Spawn & Wait

```tp
import time

func downloadData(url) {
    show("Downloading: " + url)
    time.sleep(1)
    show("Done: " + url)
}

func trainModel() {
    show("Training model...")
    time.sleep(2)
    show("Training complete!")
}

// Launch both concurrently
spawn downloadData("https://example.com/data")
spawn trainModel()

// Wait for all to finish
wait

show("All tasks complete!")
```

### Worker Pool

```tp
func worker(id, items) {
    for item in items {
        show("Worker " + str(id) + " processing: " + str(item))
    }
}

spawn worker(1, [1, 2, 3])
spawn worker(2, [4, 5, 6])
spawn worker(3, [7, 8, 9])
wait

show("All workers done!")
```

---

## AI Features

### AI Assistant Declaration

```tp
ai myBot

let answer = myBot.ask("What is the speed of light?")
show(answer)

let poem = myBot.ask("Write a short poem about coding")
show(poem)
```

### AI Module

```tp
import ai

// Summarize text
let summary = ai.summarize("Long article text here...")
show(summary)

// Generate code
let code = ai.generateCode("a function to sort a list")
show(code)

// Translate
let spanish = ai.translate("Hello World", "Spanish")
show(spanish)

// Sentiment analysis
let mood = ai.sentiment("This is absolutely amazing!")
show(mood)   // "positive"

// Classify
let category = ai.classify("The stock market rose 2%", "finance")
show(category)
```

> **Note**: Set `OPENAI_API_KEY` environment variable for real AI responses.  
> Without it, mock responses are returned for offline development.

---

## Modules & Imports

```tp
import math
import json
import time
import file
import string
import network
import ai
import collections
```

---

## Standard Library

### math

```tp
import math

math.sqrt(16)         // 4.0
math.pow(2, 8)        // 256.0
math.abs(-5)          // 5
math.floor(3.9)       // 3
math.ceil(3.1)        // 4
math.round(3.567, 2)  // 3.57
math.sin(math.pi / 2) // 1.0
math.cos(0)           // 1.0
math.log(math.e)      // 1.0
math.factorial(5)     // 120
math.gcd(12, 8)       // 4
math.random()         // 0.0..1.0
math.randint(1, 100)  // random int
math.pi               // 3.14159...
math.e                // 2.71828...
math.clamp(x, min, max)
math.lerp(a, b, t)
math.degrees(radians)
math.radians(degrees)
```

### string

```tp
import string

string.upper("hello")        // "HELLO"
string.lower("WORLD")        // "world"
string.title("hello world")  // "Hello World"
string.split("a,b,c", ",")  // ["a", "b", "c"]
string.join("-", ["a","b"])  // "a-b"
string.replace("foo", "o", "0") // "f00"
string.strip("  hi  ")       // "hi"
string.startsWith("hello", "he")  // true
string.endsWith("world", "ld")    // true
string.contains("hello", "ell")   // true
string.substring("hello", 1, 3)   // "el"
string.reverse("abc")             // "cba"
string.repeat("ab", 3)            // "ababab"
string.padLeft("5", 3, "0")       // "005"
string.length("hello")            // 5
string.isDigit("123")             // true
string.regexMatch("hello", "h.*o") // true
string.regexFind("a1b2c3", "\\d+") // ["1","2","3"]
string.chars("abc")               // ["a","b","c"]
```

### file

```tp
import file

let content = file.read("data.txt")
file.write("output.txt", "Hello World")
file.append("log.txt", "New entry\n")
let lines = file.lines("data.txt")
file.delete("temp.txt")
show(file.exists("config.json"))  // true/false
let files = file.listDir("./src")
file.mkdir("new_folder")
let path = file.join("src", "main.tp")
let ext  = file.extension("main.tp")  // ".tp"
```

### json

```tp
import json

let data = {"name": "Taipan", "version": 1}
let text = json.stringify(data, 2)   // pretty-printed
let parsed = json.parse(text)
show(parsed["name"])

json.save("config.json", data)
let loaded = json.load("config.json")
```

### time

```tp
import time

show(time.now())         // "2026-06-15 22:00:00"
show(time.date())        // "2026-06-15"
show(time.timestamp())   // Unix timestamp
time.sleep(1.5)          // Sleep 1.5 seconds
show(time.year())        // 2026
show(time.month())       // 6
show(time.day())         // 15
show(time.hour())        // 22
show(time.minute())      // 0
show(time.second())      // 0
let t0 = time.clock()
// ... do work ...
show(time.clock() - t0)  // elapsed seconds
```

### collections

```tp
import collections

// Stack
let stack = collections.Stack()
stack.push(10)
stack.push(20)
stack.pop()        // 20
stack.peek()       // 10
stack.isEmpty()    // false
stack.size()       // 1

// Queue
let queue = collections.Queue()
queue.enqueue("first")
queue.enqueue("second")
queue.dequeue()    // "first"
queue.front()      // "second"

// PriorityQueue (min-heap by priority)
let pq = collections.PriorityQueue()
pq.push(3, "low priority")
pq.push(1, "high priority")
pq.pop()           // "high priority"

// Utilities
collections.counter([1,1,2,3,3,3])  // {1:2, 2:1, 3:3}
collections.flatten([[1,2],[3,4]])   // [1,2,3,4]
collections.unique([1,1,2,2,3])     // [1,2,3]
collections.zip([1,2],[3,4])        // [[1,3],[2,4]]
collections.enumerate(["a","b"])    // [[0,"a"],[1,"b"]]
collections.chunk([1,2,3,4,5], 2)  // [[1,2],[3,4],[5]]
```

### network

```tp
import network

let html = network.get("https://example.com")
let resp = network.post("https://api.example.com/data", '{"key":"val"}')
network.download("https://example.com/file.zip", "file.zip")
let enc = network.urlEncode("hello world")  // "hello%20world"
let dec = network.urlDecode("hello%20world")
```

### ai

```tp
import ai

ai.ask("Explain recursion in simple terms")
ai.summarize("Long text to summarize...")
ai.generateCode("fibonacci function in Taipan")
ai.translate("Hello World", "Japanese")
ai.sentiment("I love this language!")   // "positive"
ai.classify("Breaking news: ...", "news")
ai.isAvailable()    // true if OPENAI_API_KEY is set
ai.setModel("gpt-4")
```

---

## Built-in Functions

```tp
show(x)             // Print (no newline at end internally)
show(a, b, c)       // Print multiple values space-separated
input("prompt: ")   // Read a line from stdin
len(x)              // Length of string/list/map/set/tuple
type(x)             // Type name as string: "Int", "String", etc.
int(x)              // Convert to integer
float(x)            // Convert to float
str(x)              // Convert to string
bool(x)             // Convert to boolean
range(n)            // Range 0..n-1
range(start, end)   // Range start..end-1
range(start, end, step)
list(x)             // Convert to List
set(x)              // Convert to Set
abs(n)              // Absolute value
min(list)           // Minimum
max(list)           // Maximum
sum(list)           // Sum
round(x, digits)    // Round to digits
sorted(list)        // Sorted copy
reversed(list)      // Reversed copy
exit(code)          // Exit program
assert(cond, msg)   // Assert condition
chr(n)              // ASCII char from code
ord(c)              // ASCII code from char
hex(n)              // Hex string
bin(n)              // Binary string
```

---

## Package Manager — tpkg

```bash
python package_manager/tpkg.py install numpy
python package_manager/tpkg.py install requests pillow
python package_manager/tpkg.py remove numpy
python package_manager/tpkg.py list
python package_manager/tpkg.py search "machine learning"
python package_manager/tpkg.py info requests
python package_manager/tpkg.py init my_project
python package_manager/tpkg.py update
```

---

## VS Code Extension

### Installation (with LSP — Recommended)

1. **Install Node.js** (for LSP client support): [nodejs.org](https://nodejs.org)

2. **Copy the extension** to your VS Code extensions directory:
   - **Windows**: `%USERPROFILE%\.vscode\extensions\taipan-2.0.0`
   - **macOS/Linux**: `~/.vscode/extensions/taipan-2.0.0`

3. **Install LSP dependencies** (inside the extension folder):
   ```bash
   cd %USERPROFILE%\.vscode\extensions\taipan-2.0.0   # Windows
   cd ~/.vscode/extensions/taipan-2.0.0             # macOS/Linux
   npm install
   ```

4. **Reload VS Code** (`Ctrl+Shift+P` → "Developer: Reload Window")

5. Open any `.tp` file — full IDE support activates automatically!

### Basic Installation (Syntax Highlighting Only)

If you only need syntax highlighting (no LSP features):

1. Copy `vscode_extension/` to your extensions directory
2. Skip `npm install` — the extension works without it
3. Reload VS Code

### Features

| Feature | Status | Description |
|---|---|---|
| ✅ Syntax highlighting | Ready | Keywords, strings, numbers, comments, types |
| ✅ Bracket matching | Ready | Auto-closing `{ }`, `[ ]`, `( )` |
| ✅ Comment toggling | Ready | `Ctrl+/` for line comments |
| ✅ Code folding | Ready | Fold blocks, functions, classes |
| 🔥 **Symbol outline** | LSP | Tree of functions/classes in VS Code sidebar |
| 🔥 **Signature help** | LSP | Show function parameters while typing `foo(` |
| 🔥 **Format on save** | LSP | Auto-format `.tp` files with `Shift+Alt+F` |
| 🔥 **Hover docs** | LSP | Hover over `math.sqrt` to see signature |
| 🔥 **Autocomplete** | LSP | Keywords, builtins, stdlib, user-defined symbols |
| 🔥 **Go to definition** | LSP | `Ctrl+Click` on functions/classes to jump to declaration |
| 🔥 **Run file** | Command | `Ctrl+Shift+P` to run current `.tp` file |
| 🔥 **Open REPL** | Command | Open Taipan REPL in integrated terminal |

### LSP Commands

| Command | Shortcut | Action |
|---|---|---|
| `Taipan: Run Current File` | `Ctrl+Shift+P` | Run the current `.tp` file |
| `Taipan: Open REPL` | — | Launch interactive REPL |
| `Taipan: Restart Language Server` | — | Restart LSP if it crashes |

### Troubleshooting

**LSP server not starting?**
- Make sure Python is on your PATH (`py` on Windows, `python3` on macOS/Linux)
- Check the Output panel (`Ctrl+Shift+U`) → select "Taipan Language Server" for logs
- Run `Taipan: Restart Language Server` from the command palette

**No autocomplete/hover?**
- Ensure you ran `npm install` in the extension directory
- Reload VS Code window after installing dependencies

---

## Roadmap

| Phase | Status | Description |
|---|---|---|
| Phase 1 | ✅ **Complete** | Tree-walk interpreter (this release) |
| Phase 2 | 🔄 Planned | Bytecode virtual machine |
| Phase 3 | 🔄 Planned | LLVM backend |
| Phase 4 | 🔄 Planned | Native executable generation |
| **LSP / IDE Support** | ✅ **Complete** | Diagnostics, hover, autocomplete, go-to-definition |
| Package Registry | 🔄 Planned | Dedicated Taipan package registry |
| Type Inference | 🔄 Planned | Full static type system |
| Generics | 🔄 Planned | Generic types |
| Pattern Matching | 🔄 Planned | `match`/`case` expressions |
| Async/Await | 🔄 Planned | Native async coroutines |

---

## Example Programs

| File | Description |
|---|---|
| `examples/hello_world.tp` | Basic I/O, variables, loops |
| `examples/fibonacci.tp` | Recursion, iteration, algorithms |
| `examples/classes.tp` | OOP, inheritance, real-world patterns |
| `examples/concurrency.tp` | spawn/wait, parallel tasks |
| `examples/ai_demo.tp` | AI assistant, summarization, code gen |
| `examples/full_demo.tp` | Everything — comprehensive showcase |

---

## License

MIT License — Copyright (c) 2026 Peeyush

---

*Taipan — Built for the next generation of developers.*  
*Simple. Fast. Safe. AI-Native.*
