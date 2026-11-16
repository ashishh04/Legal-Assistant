"""Command line for the document sync: ``python -m ferrero.sync``."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import Counter
from pathlib import Path

from ..casemodel import CaseModel
from ..config import get_settings
from .index import DocumentIndex
from .runner import run_sync
from .sources import LocalFolderSource, SharePointSource, load_manifest, manifest_next_to


def build_source(kind: str, path: Path | None, model: CaseModel, manifest: dict | None):
    settings = get_settings()
    if kind == "local":
        def library_path_for(name: str) -> str | None:
            entry = model.catalogue_entry(name)
            return entry["library_path"] if entry else None
        return LocalFolderSource(path or settings.documents_dir, library_path_for=library_path_for, manifest=manifest)
    env = os.environ
    missing = [k for k in ("FERRERO_SP_TENANT_ID", "FERRERO_SP_CLIENT_ID", "FERRERO_SP_CLIENT_SECRET", "FERRERO_SP_HOSTNAME")
               if not env.get(k)]
    if missing:
        raise SystemExit(f"SharePoint sync needs: {', '.join(missing)} (see .env.example)")
    return SharePointSource(
        env["FERRERO_SP_TENANT_ID"], env["FERRERO_SP_CLIENT_ID"], env["FERRERO_SP_CLIENT_SECRET"], env["FERRERO_SP_HOSTNAME"],
        site_path=env.get("FERRERO_SP_SITE_PATH", "Legal"), library=env.get("FERRERO_SP_LIBRARY", "Cases"),
    )


def compare_with_manifest(index: DocumentIndex, manifest: dict[str, dict[str, str]]) -> list[str]:
    """How our status for each manifest file compares with the status the corpus expects."""
    ours = {d["file_name"]: d for d in index.catalogue()}
    pairs = Counter()
    for name, row in manifest.items():
        got = ours.get(name)
        actual = f"{got['index_status']}" + (f" – {got['skip_reason']}" if got and got["skip_reason"] else "") if got else "not found"
        pairs[(row.get("index_status") or "?", actual)] += 1
    lines = ["Compared with the manifest (expected -> this sync):"]
    lines += [f"  {n:4d}  {expected} -> {actual}" for (expected, actual), n in sorted(pairs.items(), key=lambda kv: -kv[1])]
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ferrero-sync", description="Sync case documents into the Ferrero search index.")
    parser.add_argument("--source", choices=("local", "sharepoint"), default="local")
    parser.add_argument("--path", type=Path, help="folder for --source local (default: the pack's documents/)")
    parser.add_argument("--manifest", type=Path,
                        help="corpus manifest mapping files to cases (default: <folder>_meta/manifest.csv if present)")
    parser.add_argument("--full", action="store_true", help="reprocess every file, ignoring stored versions and cursors")
    parser.add_argument("--no-verify-content", action="store_true",
                        help="index files whose text does not mention their case's mark or parties (flagged, not skipped)")
    parser.add_argument("--status-csv", type=Path, help="where to write per-document status (default: data/sync_status.csv)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()
    model = CaseModel(settings.csv_dir, settings.demo_today, catalogue=settings.catalogue_path)
    index = DocumentIndex(settings.index_path)
    folder = args.path or settings.documents_dir
    manifest_path = args.manifest or (manifest_next_to(folder) if args.source == "local" else None)
    manifest = load_manifest(manifest_path) if manifest_path else None
    if manifest:
        print(f"Using manifest {manifest_path} ({len(manifest)} files)")
    source = build_source(args.source, folder, model, manifest)
    from ..ocr.engines import sync_reader

    ocr = sync_reader(settings)
    result = run_sync(source, index, model, full=args.full, verify_content=not args.no_verify_content,
                      status_csv=args.status_csv or settings.data_dir / "sync_status.csv", ocr=ocr)
    print(result.summary())
    stats = index.stats()
    catalogue = len(model.tables["fact_document"].rows)
    print(f"Index: {stats['indexed']} searchable documents, {stats['passages']} passages ({settings.index_path})")
    print(f"Catalogue: {catalogue} documents listed in fact_document; {catalogue - stats['indexed']} have no searchable file yet")
    if manifest:
        print("\n".join(compare_with_manifest(index, manifest)))
    return 1 if result.pending else 0  # scans waiting for text recognition are expected, not a failure


if __name__ == "__main__":
    raise SystemExit(main())
