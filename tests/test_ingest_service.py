import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document

from app.config import Settings
from app.services.ingest import IngestService


class _FakeVectorStore:
    def __init__(self) -> None:
        self.deleted_sources: list[str] = []
        self.added_batches: list[list[Document]] = []

    def delete_by_source(self, source: str) -> None:
        self.deleted_sources.append(source)

    def add_documents(self, docs: list[Document]) -> list[str]:
        self.added_batches.append(docs)
        return [str(d.metadata.get("chunk_id", "")) for d in docs]


class IngestServiceTests(unittest.TestCase):
    def _build_settings(self, root: Path) -> Settings:
        return Settings(
            data_dir=root / "data",
            upload_dir=root / "uploads",
            ingest_index_path=root / "ingest_index.json",
        )

    def test_ingest_file_skips_unchanged_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            settings = self._build_settings(root)
            vectorstore = _FakeVectorStore()
            service = IngestService(vectorstore, settings)
            file_path = settings.data_dir / "sample.md"
            file_path.write_text("# Title\ncontent", encoding="utf-8")

            chunks = [Document(page_content="chunk", metadata={"chunk_id": "c1"})]
            with (
                patch.object(service, "_load_documents", return_value=[Document(page_content="doc")]),
                patch.object(service, "_split_documents", return_value=chunks),
            ):
                added_first, _ = service.ingest_file(file_path)
                added_second, _ = service.ingest_file(file_path)

            self.assertEqual(added_first, 1)
            self.assertEqual(added_second, 0)
            self.assertEqual(len(vectorstore.added_batches), 1)

    def test_save_upload_rejects_unsupported_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = self._build_settings(Path(tmpdir))
            service = IngestService(_FakeVectorStore(), settings)
            with self.assertRaises(ValueError):
                service.save_upload("malicious.exe", b"123")


if __name__ == "__main__":
    unittest.main()
