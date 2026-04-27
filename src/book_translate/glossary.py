from __future__ import annotations

import json
import re
from pathlib import Path


def empty_glossary() -> dict:
    return {"terms": {}, "conflicts": []}


def merge_glossary_terms(existing: dict, incoming: dict) -> dict:
    merged = {"terms": dict(existing.get("terms", {})), "conflicts": list(existing.get("conflicts", []))}
    for term, translation in incoming.get("terms", {}).items():
        key = str(term).strip()
        value = str(translation).strip()
        if not key or not value:
            continue
        if key in merged["terms"] and merged["terms"][key] != value:
            conflict = {"term": key, "existing": merged["terms"][key], "incoming": value}
            if conflict not in merged["conflicts"]:
                merged["conflicts"].append(conflict)
            continue
        merged["terms"][key] = value
    return merged


def load_glossary(path: Path | str) -> dict:
    glossary_path = Path(path)
    if not glossary_path.exists():
        return empty_glossary()
    text = glossary_path.read_text(encoding="utf-8").strip()
    if not text:
        return empty_glossary()
    if text.startswith("{"):
        return json.loads(text)
    return _parse_simple_yaml(text)


def save_glossary(path: Path | str, glossary: dict) -> None:
    Path(path).write_text(_dump_simple_yaml(glossary), encoding="utf-8")


def parse_glossary_response(text: str) -> dict:
    fenced = re.search(r"```(?:json|yaml|yml)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    payload = fenced.group(1).strip() if fenced else text.strip()
    if payload.startswith("{"):
        return json.loads(payload)
    return _parse_simple_yaml(payload)


def _dump_simple_yaml(glossary: dict) -> str:
    lines = ["terms:"]
    terms = glossary.get("terms", {})
    if terms:
        for term in sorted(terms):
            lines.append(f"  {term}: {terms[term]}")
    else:
        lines[-1] = "terms: {}"
    conflicts = glossary.get("conflicts", [])
    if conflicts:
        lines.append("conflicts:")
        for item in conflicts:
            lines.append(f"  - term: {item['term']}")
            lines.append(f"    existing: {item['existing']}")
            lines.append(f"    incoming: {item['incoming']}")
    else:
        lines.append("conflicts: []")
    return "\n".join(lines) + "\n"


def _parse_simple_yaml(text: str) -> dict:
    result = empty_glossary()
    section = None
    current_conflict = None
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("terms:"):
            section = "terms"
            continue
        if stripped.startswith("conflicts:"):
            section = "conflicts"
            continue
        if section == "terms" and ":" in stripped:
            key, value = stripped.split(":", 1)
            if key.strip() != "{}":
                result["terms"][key.strip().strip('"')] = value.strip().strip('"')
        elif section == "conflicts":
            if stripped.startswith("- term:"):
                current_conflict = {"term": stripped.split(":", 1)[1].strip(), "existing": "", "incoming": ""}
                result["conflicts"].append(current_conflict)
            elif current_conflict and ":" in stripped:
                key, value = stripped.split(":", 1)
                current_conflict[key.strip()] = value.strip()
    return result
