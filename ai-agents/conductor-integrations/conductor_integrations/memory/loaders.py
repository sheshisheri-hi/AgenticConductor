"""Load glossary, ownership, and triples from consumer data files."""

from __future__ import annotations

from pathlib import Path

import yaml

from conductor_integrations.memory.models import DefectTriple, OwnershipEntry, TermCard


def load_glossary(path: Path | str) -> list[TermCard]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    terms = data.get("terms", data if isinstance(data, list) else [])
    return [TermCard.model_validate(t) for t in terms]


def load_ownership(path: Path | str) -> list[OwnershipEntry]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    components = data.get("components", data if isinstance(data, list) else [])
    return [OwnershipEntry.model_validate(c) for c in components]


def load_triples(path: Path | str) -> list[DefectTriple]:
    raw = Path(path).read_text(encoding="utf-8")
    # JSON preferred; YAML also accepted
    if str(path).endswith((".yaml", ".yml")):
        data = yaml.safe_load(raw) or []
    else:
        import json

        data = json.loads(raw)
    if isinstance(data, dict):
        data = data.get("triples", [])
    return [DefectTriple.model_validate(t) for t in data]


def ownership_lookup(
    entries: list[OwnershipEntry],
    components: list[str],
) -> dict:
    """Return owners + repos for matched components."""
    by_name = {e.component.lower(): e for e in entries}
    owners: list[str] = []
    repos: list[str] = []
    teams: list[str] = []
    matched: list[str] = []
    for comp in components:
        entry = by_name.get(comp.lower())
        if not entry:
            continue
        matched.append(entry.component)
        owners.extend(entry.owners)
        repos.extend(entry.repos)
        if entry.team:
            teams.append(entry.team)
    # de-dupe preserve order
    def uniq(xs: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    return {
        "matched_components": uniq(matched),
        "owners": uniq(owners),
        "repos": uniq(repos),
        "teams": uniq(teams),
    }
