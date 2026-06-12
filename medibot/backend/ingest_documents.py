"""
Run this script ONCE to ingest all documents into Qdrant before starting the server.

Usage:
    cd backend
    python ingest_documents.py

    # Force re-ingest (deletes and recreates collection):
    python ingest_documents.py --force
"""
import sys
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def main():
    parser = argparse.ArgumentParser(description="Ingest MediAssist documents into Qdrant")
    parser.add_argument("--force", action="store_true", help="Force re-ingestion even if collection exists")
    parser.add_argument("--data-dir", default="../data", help="Path to data directory")
    args = parser.parse_args()

    from app.ingestion.ingest import ingest_all_documents

    print("\n" + "=" * 60)
    print("  MediBot Document Ingestion Pipeline")
    print("=" * 60)
    print(f"  Data directory: {args.data_dir}")
    print(f"  Force re-ingest: {args.force}")
    print("=" * 60 + "\n")

    result = ingest_all_documents(data_dir=args.data_dir, force_reingest=args.force)

    print("\n" + "=" * 60)
    print("  Ingestion Complete")
    print("=" * 60)
    for k, v in result.items():
        print(f"  {k}: {v}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
