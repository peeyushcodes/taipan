"""
Taipan Pretty Error Formatter
==============================
Formats errors with source context, underlines, and helpful suggestions.
Inspired by Rust/Elm error messages.

Usage:
    from taipan.runtime.pretty_errors import format_error
    print(format_error(error, source_code, filename))

Example output:
    error[TaipanSyntaxError]: Expected module name after 'import'
      --> examples/ai_demo.pk:7:8
       |
     7 | import ai
       |        ^^ cannot import module named `ai`
       |
       = help: `ai` is a reserved keyword, not a module name
       = help: To use the AI module, import it as: `import ai_module`
"""

import sys


def _get_line(source: str, line_num: int) -> str:
    """Get a specific line from source code (1-indexed)."""
    lines = source.splitlines()
    if 1 <= line_num <= len(lines):
        return lines[line_num - 1]
    return ""


def _pad_line_number(n: int, max_width: int) -> str:
    """Pad a line number for alignment."""
    return str(n).rjust(max_width)


def _format_underline(column: int, length: int = 1) -> str:
    """Create an underline with carets."""
    if column <= 0:
        column = 1
    spaces = " " * (column - 1)
    carets = "^" * max(1, length)
    return spaces + carets


def format_error(error, source: str = "", filename: str = "", hints: list[str] = None) -> str:
    """
    Format a Taipan error with full source context.

    Args:
        error: A TaipanError instance
        source: The full source code string
        filename: The file path or name
        hints: Optional list of helpful suggestions

    Returns:
        A formatted error string with context, underline, and hints
    """
    error_type = error.__class__.__name__
    message = error.message
    line = error.line
    column = error.column

    # Build the header
    result = []
    result.append(f"\n\033[1;31merror\033[0m [\033[1m{error_type}\033[0m]: {message}")

    # Show source location
    if line > 0 and filename:
        result.append(f"  \033[0;34m-->\033[0m {filename}:{line}:{column}")
    elif line > 0:
        result.append(f"  \033[0;34m-->\033[0m <source>:{line}:{column}")

    # Show source context with underline
    if line > 0 and source:
        lines = source.splitlines()
        total_lines = len(lines)

        # Show context: 2 lines before and 1 line after
        start_line = max(1, line - 2)
        end_line = min(total_lines, line + 1)
        max_width = len(str(end_line))

        # Draw the gutter separator
        result.append(f"  {' ' * max_width} \033[0;34m|\033[0m")

        for i in range(start_line, end_line + 1):
            line_text = lines[i - 1] if i <= total_lines else ""
            padded_num = _pad_line_number(i, max_width)

            if i == line:
                # Error line
                result.append(f"  \033[0;34m{padded_num} |\033[0m {line_text}")
                # Underline
                underline = _format_underline(column, max(1, len(str(message)) // 2))
                result.append(f"  {' ' * max_width} \033[0;34m|\033[0m \033[1;31m{underline}\033[0m")
            else:
                # Context line
                result.append(f"  \033[0;34m{padded_num} |\033[0m {line_text}")

    # Show hints/suggestions
    if hints:
        result.append(f"  {' ' * max_width} \033[0;34m|\033[0m")
        for hint in hints:
            result.append(f"  \033[0;34m=\033[0m \033[1;33mhelp:\033[0m {hint}")

    result.append("")
    return "\n".join(result)


def format_error_simple(error) -> str:
    """Simple fallback formatter without source context."""
    error_type = error.__class__.__name__
    if error.line:
        return f"[Line {error.line}:{error.column}] {error_type}: {error.message}"
    return f"{error_type}: {error.message}"


# ANSI color helpers (for non-ANSI fallback)
if sys.platform == "win32":
    import os
    os.system("")
