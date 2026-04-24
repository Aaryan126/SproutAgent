import difflib


def generate_diff(original: str, proposed: str, filename: str = "doc.md") -> str:
    diff_lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        proposed.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=3,
    )
    diff_text = "".join(diff_lines)
    return f"```diff\n{diff_text}\n```"


def apply_section_replacement(
    full_doc: str,
    original_section: str,
    proposed_section: str,
) -> str:
    if original_section not in full_doc:
        preview = original_section[:80]
        raise ValueError(f"Section not found in document: '{preview}...'")
    return full_doc.replace(original_section, proposed_section, 1)
