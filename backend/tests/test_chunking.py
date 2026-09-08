from app.chunking import chunk_source


def test_python_function_and_class_with_docstrings():
    source = b'''def foo():
    """Do foo."""
    return 1


class Bar:
    def method(self):
        pass
'''
    chunks = chunk_source(source, "python")

    assert [c.symbol_name for c in chunks] == ["foo", "Bar", "method"]
    assert [c.symbol_type for c in chunks] == ["function", "class", "function"]

    foo = chunks[0]
    assert foo.docstring == "Do foo."
    assert foo.start_line == 1
    assert "return 1" in foo.code

    bar = chunks[1]
    assert bar.docstring is None


def test_python_no_symbols_falls_back_to_whole_file_chunk():
    source = b"x = 1\ny = 2\n"
    chunks = chunk_source(source, "python")

    assert len(chunks) == 1
    assert chunks[0].symbol_name is None
    assert chunks[0].symbol_type == "module"
    assert chunks[0].code == source.decode()


def test_unsupported_language_returns_no_chunks():
    assert chunk_source(b"anything at all", "plaintext") == []


def test_javascript_class_and_method():
    source = b"""class Foo {
  bar() {
    return 1;
  }
}
"""
    chunks = chunk_source(source, "javascript")

    assert [c.symbol_name for c in chunks] == ["Foo", "bar"]
    assert [c.symbol_type for c in chunks] == ["class", "method"]


def test_javascript_leading_comment_becomes_docstring():
    source = b"""// Adds two numbers
function add(a, b) {
  return a + b;
}
"""
    chunks = chunk_source(source, "javascript")

    assert len(chunks) == 1
    assert chunks[0].symbol_name == "add"
    assert chunks[0].docstring == "// Adds two numbers"
