import json
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

from app.config import Settings, get_settings
from app.services.chunking import enrich_chunks, split_markdown_documents, split_plain_documents
from app.services.vectorstore import VectorStoreService


class IngestService:
    def __init__(
        self,
        vectorstore: VectorStoreService,
        settings: Settings | None = None,
    ) -> None:
        self.vectorstore = vectorstore
        self.settings = settings or get_settings()
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings.upload_dir.mkdir(parents=True, exist_ok=True)
        self.settings.ingest_index_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> dict[str, float]:
        if not self.settings.ingest_index_path.exists():
            return {}
        with self.settings.ingest_index_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save_index(self, index: dict[str, float]) -> None:
        with self.settings.ingest_index_path.open("w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def _normalize_source(self, path: Path) -> str:
        return str(path.resolve())

    def _load_documents(self, path: Path) -> list[Document]:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            loader = PyPDFLoader(str(path))
        elif suffix in {".txt", ".md"}:
            loader = TextLoader(str(path), encoding="utf-8")
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

        docs = loader.load()
        source = self._normalize_source(path)
        for doc in docs:
            doc.metadata["source"] = source
        return docs

    def _split_documents(self, docs: list[Document], file_type: str) -> list[Document]:
        if file_type == ".md":
            chunks = split_markdown_documents(docs, self.settings)
        else:
            chunks = split_plain_documents(docs, self.settings)
        return enrich_chunks(chunks)

    def _persist_chunks(self, path: Path, source: str, chunks: list[Document]) -> None:
        self.vectorstore.delete_by_source(source)
        for chunk in chunks:
            chunk.metadata.setdefault("filename", path.name)
            chunk.metadata.setdefault("file_type", path.suffix.lower())
            chunk.metadata.setdefault("mtime", path.stat().st_mtime)
        self.vectorstore.add_documents(chunks)

    def ingest_file(self, path: Path, *, force: bool = False) -> tuple[int, str]:
        path = path.resolve()
        if path.suffix.lower() not in self.settings.allowed_extensions:
            raise ValueError(f"Unsupported file type: {path.suffix}")

        source = self._normalize_source(path)
        mtime = path.stat().st_mtime
        index = self._load_index()

        if not force and index.get(source) == mtime:
            return 0, source

        docs = self._load_documents(path)
        chunks = self._split_documents(docs, path.suffix.lower())
        self._persist_chunks(path, source, chunks)

        index[source] = mtime
        self._save_index(index)
        return len(chunks), source

    def ingest_directory(
        self,
        directory: Path | None = None,
        *,
        force: bool = False,
    ) -> tuple[int, int, list[str]]:
        directory = (directory or self.settings.data_dir).resolve()
        files_processed = 0
        chunks_added = 0
        skipped: list[str] = []

        if not directory.exists():
            return files_processed, chunks_added, skipped

        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in self.settings.allowed_extensions:
                continue

            try:
                added, _ = self.ingest_file(path, force=force)
                if added == 0:
                    skipped.append(str(path))
                else:
                    files_processed += 1
                    chunks_added += added
            except Exception as exc:
                skipped.append(f"{path} ({exc})")

        return files_processed, chunks_added, skipped

    def save_upload(self, filename: str, content: bytes) -> Path:
        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.lower()
        if suffix not in self.settings.allowed_extensions:
            raise ValueError(f"Unsupported file type: {suffix}")

        target = self.settings.upload_dir / safe_name
        target.write_bytes(content)
        return target
