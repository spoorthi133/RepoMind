from app.llm import build_diagnosis_prompt, build_prompt

CHUNK = {
    "file_path": "app/main.py",
    "start_line": 10,
    "end_line": 20,
    "symbol_type": "function",
    "symbol_name": "handler",
    "code": "def handler():\n    pass",
}


def test_build_prompt_includes_citation_header_and_question():
    prompt = build_prompt("What does handler do?", [CHUNK])

    assert "app/main.py:10-20" in prompt
    assert "def handler():" in prompt
    assert "What does handler do?" in prompt


def test_build_prompt_with_no_chunks_says_so():
    prompt = build_prompt("anything", [])
    assert "(no relevant code found)" in prompt


def test_build_diagnosis_prompt_includes_findings():
    findings = [
        {"tool": "pylint", "file_path": "app/main.py", "line": 12, "severity": "error", "message": "undefined name"}
    ]
    prompt = build_diagnosis_prompt("NameError: x is not defined", [CHUNK], findings)

    assert "[pylint] app/main.py:12 (error): undefined name" in prompt
    assert "NameError: x is not defined" in prompt


def test_build_diagnosis_prompt_with_no_findings_says_so():
    prompt = build_diagnosis_prompt("some error", [CHUNK], [])
    assert "(no static analysis findings linked to the retrieved files)" in prompt
