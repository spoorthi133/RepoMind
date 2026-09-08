from app.ignore_list import detect_language, should_ignore_dir, should_ignore_file


def test_should_ignore_known_dirs():
    assert should_ignore_dir("node_modules")
    assert should_ignore_dir(".git")
    assert should_ignore_dir("__pycache__")


def test_should_ignore_hidden_dirs_by_convention():
    assert should_ignore_dir(".github")
    assert should_ignore_dir(".anything")


def test_should_not_ignore_normal_dirs():
    assert not should_ignore_dir("src")
    assert not should_ignore_dir("app")


def test_should_ignore_lockfiles():
    assert should_ignore_file("package-lock.json")
    assert should_ignore_file("go.sum")


def test_should_ignore_binary_and_minified_extensions():
    assert should_ignore_file("photo.png")
    assert should_ignore_file("bundle.min.js")
    assert should_ignore_file("app.min.css")
    assert should_ignore_file("archive.tar.gz")


def test_should_not_ignore_source_files():
    assert not should_ignore_file("main.py")
    assert not should_ignore_file("index.ts")


def test_detect_language_by_extension():
    assert detect_language("main.py") == "python"
    assert detect_language("app.tsx") == "tsx"
    assert detect_language("server.js") == "javascript"
    assert detect_language("lib.rs") == "rust"


def test_detect_language_unknown_extension_returns_none():
    assert detect_language("README.md") is None
    assert detect_language("Makefile") is None
