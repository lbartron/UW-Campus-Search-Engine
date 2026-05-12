import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv


def load_snapshot(snapshot_path: Path) -> List[Dict[str, Any]]:
    with snapshot_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Build local embedding index.")
    parser.add_argument(
        "--snapshot",
        default="data/snapshots/latest.json",
        help="Snapshot JSON file to index",
    )
    parser.add_argument(
        "--out-dir",
        default="data/index",
        help="Output directory for index files",
    )
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    if not snapshot_path.exists():
        raise SystemExit(f"Snapshot not found: {snapshot_path}")

    docs = load_snapshot(snapshot_path)
    texts = [doc.get("text", "") for doc in docs]

    model_name = os.getenv("LOCAL_EMBED_MODEL", "all-MiniLM-L6-v2")
    model = SentenceTransformer(model_name)
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    emb_path = out_dir / "embeddings.npz"
    docs_path = out_dir / "docs.json"
    meta_path = out_dir / "index_meta.json"

    np.savez_compressed(emb_path, embeddings=embeddings.astype(np.float32))

    with docs_path.open("w", encoding="utf-8") as handle:
        json.dump(docs, handle, ensure_ascii=True, indent=2)

    meta = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "doc_count": len(docs),
        "snapshot": str(snapshot_path),
        "model": model_name,
        "embedding_dim": int(embeddings.shape[1]) if len(docs) else 0,
    }

    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=True, indent=2)

    print(f"Wrote embeddings: {emb_path}")
    print(f"Wrote docs: {docs_path}")


if __name__ == "__main__":
    main()
