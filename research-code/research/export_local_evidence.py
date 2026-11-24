"""Export the local evidence input from a matching archival source snapshot."""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import re
import tokenize


SNAPSHOT = {
    "operation_context.py": "ac544ddc74488bbbde6906a43ba2bbb3a162174c3114c4c20c333360f37d5873",
    "episode_relations.py": "0f3be1b0ad0bddb09530a69c5b18967db0c8d31fd2fb14af0ea6dd62ddfb1a2f",
    "compare_operation_contexts.py": "6d7f95a8174ca79918a0642ee90be0ae467cea00755e722ec35a935cf184c0c4",
}
LEGACY_HEADING = re.compile(r"[\u3400-\u9fff]")


def original_source(source_dir: Path, name: str) -> str:
    source = (source_dir / name).read_text(encoding="utf-8-sig")
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != SNAPSHOT[name]:
        raise ValueError(f"{name} is not the matching archival source snapshot")
    return source


def operation_notes(source: str) -> dict:
    assignments = [
        statement.value
        for statement in ast.parse(source).body
        if isinstance(statement, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "NOTES" for target in statement.targets)
    ]
    if len(assignments) != 1 or not isinstance(assignments[0], ast.Dict):
        raise ValueError("The archival operation notes are missing")
    mapping = {}
    for key, value in zip(assignments[0].keys, assignments[0].values):
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "dict"
            and not value.args
            and all(item.arg for item in value.keywords)
        ):
            raise ValueError("An archival operation note is not a literal dictionary")
        mapping[ast.literal_eval(key)] = {
            item.arg: ast.literal_eval(item.value) for item in value.keywords
        }
    if len(mapping) != 38:
        raise ValueError("Expected 38 archival operation notes")
    return mapping


def historical_texts(source: str, stem: str) -> dict[str, str]:
    values = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.STRING and LEGACY_HEADING.search(token.string):
            line, column = token.start
            value = ast.literal_eval(token.string)
            if not isinstance(value, str):
                raise ValueError(f"Expected archival text at {stem}:{line}:{column}")
            values[f"{stem}:{line}:{column}"] = value
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-research", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    config = parser.parse_args()
    notes = operation_notes(original_source(config.legacy_research, "operation_context.py"))
    texts = {}
    for name in ("episode_relations.py", "compare_operation_contexts.py"):
        source = original_source(config.legacy_research, name)
        texts.update(historical_texts(source, Path(name).stem))
    config.out.parent.mkdir(parents=True, exist_ok=True)
    with config.out.open("x", encoding="utf-8") as handle:
        json.dump(
            {"schema": "multicam-local-evidence-v1", "operation_notes": notes, "texts": texts},
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")
    print(f"Exported {len(notes)} records to the local evidence input.")


if __name__ == "__main__":
    main()
