from dataclasses import dataclass

from tree_sitter_languages import get_parser

# language -> {tree-sitter node type: our symbol_type label}
SYMBOL_NODE_TYPES = {
    "python": {
        "function_definition": "function",
        "class_definition": "class",
    },
    "javascript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
    },
    "typescript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
        "interface_declaration": "interface",
    },
    "tsx": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
        "interface_declaration": "interface",
    },
    "go": {
        "function_declaration": "function",
        "method_declaration": "method",
    },
    "java": {
        "method_declaration": "method",
        "class_declaration": "class",
        "interface_declaration": "interface",
    },
    "ruby": {
        "method": "method",
        "class": "class",
        "module": "module",
    },
    "rust": {
        "function_item": "function",
        "struct_item": "struct",
    },
    "c": {
        "function_definition": "function",
    },
    "cpp": {
        "function_definition": "function",
    },
}


@dataclass
class CodeChunk:
    symbol_name: str | None
    symbol_type: str
    start_line: int
    end_line: int
    code: str
    docstring: str | None


def _extract_docstring(node, language: str, source: bytes) -> str | None:
    if language == "python":
        body = node.child_by_field_name("body")
        if body is not None and body.child_count > 0:
            first_stmt = body.children[0]
            if first_stmt.type == "expression_statement" and first_stmt.child_count > 0:
                expr = first_stmt.children[0]
                if expr.type == "string":
                    text = source[expr.start_byte:expr.end_byte].decode("utf-8", "replace")
                    return text.strip("\"'").strip()
        return None

    # For non-Python languages, treat contiguous leading comment(s) as the docstring.
    comments: list[str] = []
    sibling = node.prev_sibling
    while sibling is not None and sibling.type == "comment":
        comments.insert(0, source[sibling.start_byte:sibling.end_byte].decode("utf-8", "replace"))
        sibling = sibling.prev_sibling
    return "\n".join(comments) if comments else None


def chunk_source(source: bytes, language: str) -> list[CodeChunk]:
    node_types = SYMBOL_NODE_TYPES.get(language)
    if not node_types:
        return []

    parser = get_parser(language)
    tree = parser.parse(source)
    chunks: list[CodeChunk] = []

    def walk(node) -> None:
        if node.type in node_types:
            name_node = node.child_by_field_name("name")
            symbol_name = (
                source[name_node.start_byte:name_node.end_byte].decode("utf-8", "replace")
                if name_node is not None
                else None
            )
            chunks.append(
                CodeChunk(
                    symbol_name=symbol_name,
                    symbol_type=node_types[node.type],
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    code=source[node.start_byte:node.end_byte].decode("utf-8", "replace"),
                    docstring=_extract_docstring(node, language, source),
                )
            )
        for child in node.children:
            walk(child)

    walk(tree.root_node)

    if not chunks:
        # No function/class boundaries found (e.g. a small script) — keep the
        # whole file as a single chunk rather than dropping it silently.
        text = source.decode("utf-8", "replace")
        line_count = text.count("\n") + 1
        chunks.append(
            CodeChunk(
                symbol_name=None,
                symbol_type="module",
                start_line=1,
                end_line=line_count,
                code=text,
                docstring=None,
            )
        )

    return chunks
