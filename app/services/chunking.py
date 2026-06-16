from uuid import uuid4

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.config import Settings
from app.services.keyword_extract import extract_keywords

HEADER_KEYS = ("Header 1", "Header 2", "Header 3")

MARKDOWN_HEADERS = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
]

CHINESE_RECURSIVE_SEPARATORS = [
    "\n\n",
    "\n|",
    "\n",
    "。",
    "！",
    "？",
    "；",
    "，",
    " ",
    "",
]


def build_heading_path(metadata: dict) -> str | None:
    parts = [str(metadata[key]).strip() for key in HEADER_KEYS if metadata.get(key)]
    if not parts:
        return None
    return " > ".join(parts)


def _recursive_splitter(settings: Settings) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=CHINESE_RECURSIVE_SEPARATORS,
    )


def _merge_doc_metadata(base: dict, extra: dict) -> dict:
    merged = dict(base)
    merged.update(extra)
    return merged


def _split_with_recursive(docs: list[Document], settings: Settings) -> list[Document]:
    return _recursive_splitter(settings).split_documents(docs)


def split_markdown_documents(docs: list[Document], settings: Settings) -> list[Document]:
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=MARKDOWN_HEADERS,
        strip_headers=False,
    )
    section_docs: list[Document] = []
    for doc in docs:
        sections = header_splitter.split_text(doc.page_content)
        for section in sections:
            section.metadata = _merge_doc_metadata(doc.metadata, section.metadata)
            section_docs.append(section)

    if not section_docs:
        return []

    return _split_with_recursive(section_docs, settings)


def split_plain_documents(docs: list[Document], settings: Settings) -> list[Document]:
    return _split_with_recursive(docs, settings)


def enrich_chunks(chunks: list[Document]) -> list[Document]:
    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = index
        chunk.metadata["chunk_id"] = str(uuid4())
        heading_path = build_heading_path(chunk.metadata)
        if heading_path:
            chunk.metadata["heading_path"] = heading_path
        keywords = extract_keywords(chunk.page_content)
        if keywords:
            chunk.metadata["keywords"] = keywords
    return chunks
