"""
Taipan Error Hierarchy
=======================
All Taipan-specific exceptions used during compilation and runtime.
"""


class TaipanError(Exception):
    """Base class for all Taipan errors."""
    def __init__(self, message: str, line: int = 0, column: int = 0):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(self._format())

    def _format(self) -> str:
        if self.line:
            return f"[Line {self.line}:{self.column}] {self.__class__.__name__}: {self.message}"
        return f"{self.__class__.__name__}: {self.message}"


class TaipanLexError(TaipanError):
    """Raised when the lexer encounters an invalid character or token."""
    pass


class TaipanSyntaxError(TaipanError):
    """Raised when the parser encounters a syntax error."""
    pass


class TaipanSemanticError(TaipanError):
    """Raised during semantic analysis (scope, type issues)."""
    pass


class TaipanRuntimeError(TaipanError):
    """Raised during program execution."""
    pass


class TaipanTypeError(TaipanRuntimeError):
    """Raised for type mismatches at runtime."""
    pass


class TaipanNameError(TaipanRuntimeError):
    """Raised when a variable/function is not defined."""
    pass


class TaipanIndexError(TaipanRuntimeError):
    """Raised for out-of-bounds list/tuple access."""
    pass


class TaipanAttributeError(TaipanRuntimeError):
    """Raised when an object does not have the requested attribute."""
    pass


class TaipanValueError(TaipanRuntimeError):
    """Raised for invalid values."""
    pass


class TaipanImportError(TaipanRuntimeError):
    """Raised when a module cannot be found or loaded."""
    pass


class TaipanDivisionByZeroError(TaipanRuntimeError):
    """Raised on division by zero."""
    def __init__(self, line: int = 0, column: int = 0):
        super().__init__("Division by zero", line, column)


# ── Control-flow signals (not real errors) ────────────────────────────────────

class ReturnSignal(Exception):
    """Used to unwind the call stack on 'return'."""
    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    """Used to break out of loops."""
    pass


class ContinueSignal(Exception):
    """Used to continue to the next loop iteration."""
    pass
