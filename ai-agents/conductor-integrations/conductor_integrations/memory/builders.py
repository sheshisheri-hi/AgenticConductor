"""Offline builders: glossary/triples → SQLite indexes."""

from __future__ import annotations

import argparse
from pathlib import Path

from conductor_integrations.memory.defect_index import DefectMemory
from conductor_integrations.memory.loaders import load_glossary, load_triples
from conductor_integrations.memory.term_index import TermIndex


def build_term_index(glossary_path: Path | str, out_path: Path | str) -> Path:
    terms = load_glossary(glossary_path)
    idx = TermIndex(out_path)
    idx.build(terms)
    return Path(out_path)


def build_defect_index(triples_path: Path | str, out_path: Path | str) -> Path:
    triples = load_triples(triples_path)
    mem = DefectMemory(out_path)
    mem.build(triples)
    return Path(out_path)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build RCA memory indexes")
    sub = parser.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("terms", help="Build term_index.sqlite from glossary YAML")
    t.add_argument("--glossary", required=True)
    t.add_argument("--out", required=True)

    d = sub.add_parser("defects", help="Build defect_index.sqlite from triples JSON")
    d.add_argument("--triples", required=True)
    d.add_argument("--out", required=True)

    a = sub.add_parser("all", help="Build both indexes for a grafana-rca style pack")
    a.add_argument("--pack-dir", required=True, help="Directory with docs/glossary.yaml and data/triples.json")

    e = sub.add_parser("from-export", help="issues_raw.json → triples.json → defect_index.sqlite")
    e.add_argument("--issues-raw", required=True)
    e.add_argument("--triples-out", required=True)
    e.add_argument("--defect-index-out", required=True)
    e.add_argument("--limit", type=int, default=None)

    args = parser.parse_args(argv)
    if args.cmd == "terms":
        path = build_term_index(args.glossary, args.out)
        print(f"Wrote {path}")
    elif args.cmd == "defects":
        path = build_defect_index(args.triples, args.out)
        print(f"Wrote {path}")
    elif args.cmd == "all":
        pack = Path(args.pack_dir)
        term_out = pack / "data" / "term_index.sqlite"
        defect_out = pack / "data" / "defect_index.sqlite"
        build_term_index(pack / "docs" / "glossary.yaml", term_out)
        build_defect_index(pack / "data" / "triples.json", defect_out)
        print(f"Wrote {term_out}")
        print(f"Wrote {defect_out}")
    elif args.cmd == "from-export":
        from conductor_integrations.memory.extract_triples import extract_triples, write_triples

        triples = extract_triples(args.issues_raw, limit=args.limit)
        triples_path = write_triples(args.triples_out, triples)
        defect_path = build_defect_index(triples_path, args.defect_index_out)
        print(f"Wrote {triples_path}")
        print(f"Wrote {defect_path}")


if __name__ == "__main__":
    main()
