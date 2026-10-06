"""Load documents (.md, .txt, .pdf) and split them into heading-aware chunks."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SUPPORTED = {".md", ".markdown", ".txt", ".pdf"}
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    text: str
    source: str


@dataclass(frozen=True)
class Chunk:
    id: str
    doc_id: str
    title: str
    heading: str
    text: str
    source: str


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "doc"


def _read(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader  # optional dependency, only needed for PDFs

        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages[:200])
    return path.read_text(encoding="utf-8", errors="replace")


def load_documents(directory: str | Path) -> list[Document]:
    root = Path(directory)
    docs: list[Document] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        text = _COMMENT.sub("", _read(path)).strip()
        if not text:
            continue
        rel = path.relative_to(root)
        h1 = next((m.group(2) for line in text.splitlines() if (m := _HEADING.match(line)) and len(m.group(1)) == 1), None)
        title = h1 or path.stem.replace("-", " ").replace("_", " ").title()
        docs.append(Document(slugify(str(rel.with_suffix(""))), title, text, str(rel)))
    return docs


def _hard_split(text: str, max_chars: int) -> list[str]:
    parts, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > max_chars:
            parts.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        parts.append(cur)
    return parts


def _units(paragraph: str, max_chars: int) -> list[str]:
    """Break an oversized paragraph into lines, then sentences, then words."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    units: list[str] = []
    for line in paragraph.split("\n"):
        pieces = [line] if len(line) <= max_chars else [s for s in _SENTENCE.split(line) if s]
        for piece in pieces:
            units.extend([piece] if len(piece) <= max_chars else _hard_split(piece, max_chars))
    return units


def _sections(doc: Document) -> list[tuple[str, str]]:
    """Return (heading, body) pairs. The text before the first sub-heading uses the document title."""
    sections: list[tuple[str, list[str]]] = [(doc.title, [])]
    for line in doc.text.splitlines():
        m = _HEADING.match(line)
        if m and len(m.group(1)) > 1:
            sections.append((m.group(2), []))
        elif m and len(m.group(1)) == 1:
            continue  # the H1 is the title
        else:
            sections[-1][1].append(line)
    return [(h, "\n".join(body).strip()) for h, body in sections if "\n".join(body).strip()]


def chunk_document(doc: Document, max_chars: int = 800, overlap: int = 120) -> list[Chunk]:
    chunks: list[Chunk] = []
    for heading, body in _sections(doc):
        units: list[str] = []
        for para in re.split(r"\n\s*\n", body):
            if para.strip():
                units.extend(_units(para.strip(), max_chars))
        pieces: list[str] = []
        cur: list[str] = []
        size = 0
        for unit in units:
            if cur and size + len(unit) + 2 > max_chars:
                pieces.append("\n\n".join(cur))
                tail = cur[-1]
                cur, size = ([tail], len(tail)) if len(tail) <= overlap else ([], 0)
            cur.append(unit)
            size += len(unit) + 2
        if cur:
            pieces.append("\n\n".join(cur))
        if len(pieces) > 1 and len(pieces[-1]) < 120 and len(pieces[-2]) + len(pieces[-1]) <= max_chars * 1.3:
            pieces[-2] = pieces[-2] + "\n\n" + pieces.pop()
        for piece in pieces:
            chunks.append(Chunk(f"{doc.doc_id}#{len(chunks)}", doc.doc_id, doc.title, heading, piece, doc.source))
    return chunks


def chunk_all(docs: list[Document], max_chars: int = 800, overlap: int = 120) -> list[Chunk]:
    return [c for d in docs for c in chunk_document(d, max_chars, overlap)]
