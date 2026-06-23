import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from taipan.runtime.errors import TaipanDivisionByZeroError, TaipanTypeError, TaipanNameError, TaipanIndexError
from taipan.runtime.ai_errors import ai_explain
from taipan.cli import _run_repl, _ai_refactor, _ai_document_file, _ai_generate_tests


def test_ai_explain_rule_based_fallbacks():
    # Make sure env keys are unset to force local rules
    old_openai = os.environ.pop("OPENAI_API_KEY", None)
    
    # Division by zero
    err = TaipanDivisionByZeroError(line=1, column=1)
    suggestion = ai_explain(err, "let x = 1 / 0")
    assert suggestion is not None
    assert "divide" in suggestion.lower() or "zero" in suggestion.lower()
    
    # Type error
    err = TaipanTypeError("type mismatch", line=1, column=1)
    suggestion = ai_explain(err, "let x = 1 + 'a'")
    assert suggestion is not None
    assert "type mismatch" in suggestion.lower() or "compatible" in suggestion.lower()
    
    # Name error
    err = TaipanNameError("name 'y' is not defined", line=1, column=1)
    suggestion = ai_explain(err, "show(y)")
    assert suggestion is not None
    assert "undefined" in suggestion.lower() or "typo" in suggestion.lower()
    
    # Index error
    err = TaipanIndexError("index out of range", line=1, column=1)
    suggestion = ai_explain(err, "let y = a[10]")
    assert suggestion is not None
    assert "index" in suggestion.lower() or "range" in suggestion.lower()

    # Restore OpenAI API Key if it was present
    if old_openai:
        os.environ["OPENAI_API_KEY"] = old_openai


@patch("taipan.cli.input")
@patch("taipan.stdlib.ai_module._ai_call")
def test_repl_ai_query(mock_ai_call, mock_input):
    mock_input.side_effect = ["? How to use lists", EOFError()]
    mock_ai_call.return_value = "Mocked AI Response"
    
    try:
        _run_repl(use_vm=False, use_ai=True)
    except SystemExit:
        pass
        
    mock_ai_call.assert_called_once_with("How to use lists")


@patch("taipan.cli.input")
@patch("taipan.stdlib.ai_module._ai_call")
def test_cli_ai_refactor(mock_ai_call, mock_input, tmp_path):
    temp_file = tmp_path / "test_refactor.tp"
    temp_file.write_text("let x = 1\n", encoding="utf-8")
    
    # Mock AI response with markdown fences
    mock_ai_call.return_value = "```tp\nlet x = 2\n```"
    mock_input.return_value = "y"
    
    res = _ai_refactor(str(temp_file))
    assert res == 0
    assert temp_file.read_text(encoding="utf-8") == "let x = 2"


@patch("taipan.cli.input")
@patch("taipan.stdlib.ai_module._ai_call")
def test_cli_ai_refactor_cancelled(mock_ai_call, mock_input, tmp_path):
    temp_file = tmp_path / "test_refactor.tp"
    temp_file.write_text("let x = 1\n", encoding="utf-8")
    
    mock_ai_call.return_value = "let x = 2"
    mock_input.return_value = "n"
    
    res = _ai_refactor(str(temp_file))
    assert res == 0
    assert temp_file.read_text(encoding="utf-8") == "let x = 1\n"


@patch("taipan.cli.input")
@patch("taipan.stdlib.ai_module._ai_call")
def test_cli_ai_document(mock_ai_call, mock_input, tmp_path):
    temp_file = tmp_path / "test_doc.tp"
    temp_file.write_text("func f() {}\n", encoding="utf-8")
    
    mock_ai_call.return_value = "```tp\n// doc comment\nfunc f() {}\n```"
    mock_input.return_value = "y"
    
    res = _ai_document_file(str(temp_file))
    assert res == 0
    assert temp_file.read_text(encoding="utf-8") == "// doc comment\nfunc f() {}"


@patch("taipan.cli.input")
@patch("taipan.stdlib.ai_module._ai_call")
def test_cli_ai_generate_tests(mock_ai_call, mock_input, tmp_path):
    temp_file = tmp_path / "test_generate.tp"
    temp_file.write_text("func f() {}\n", encoding="utf-8")
    
    mock_ai_call.return_value = "```tp\ntest \"f\" {\n    assert(f() == null)\n}\n```"
    mock_input.return_value = "y"
    
    res = _ai_generate_tests(str(temp_file))
    assert res == 0
    expected = "func f() {}\n\ntest \"f\" {\n    assert(f() == null)\n}\n"
    assert temp_file.read_text(encoding="utf-8") == expected
