"""Content chunking for RAG-ready document segments.

Splits cleaned Markdown content into chunks of appropriate size
for retrieval-augmented generation, respecting section boundaries
and maintaining heading path context.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


@dataclass
class ChunkResult:
    content: str
    heading_path: str
    chunk_index: int
    token_count: int
    content_hash: str


def estimate_tokens(text: str) -> int:
    """Estimate token count using a simple word-based heuristic.

    Roughly 1 token per 0.75 words for English text, or ~4 chars per token.
    This is an approximation — exact counts depend on the tokenizer used later.
    """
    return max(1, len(text) // 4)


def content_hash(text: str) -> str:
    """Generate a deterministic SHA-256 hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_case_law(
    text: str,
    case_citation: str,
    heading_path: str,
    max_tokens: int = 1500,
    overlap_tokens: int = 100,
) -> list[ChunkResult]:
    """Chunk a court opinion for RAG retrieval.

    Strategy:
    - Short opinions (≤ max_tokens): single chunk with full text.
    - Long opinions: split at paragraph boundaries (double newlines),
      prepending the case citation header to each continuation chunk
      so every chunk is self-identifying.

    Args:
        text: Full text of the court opinion.
        case_citation: Canonical citation (e.g., "Tameny v. Atlantic Richfield Co. (1980) 27 Cal.3d 167").
        heading_path: Hierarchy path for the opinion.
        max_tokens: Maximum tokens per chunk.
        overlap_tokens: Overlap tokens when splitting long opinions.

    Returns:
        List of ChunkResult objects.
    """
    if not text.strip():
        return []

    tokens = estimate_tokens(text)

    if tokens <= max_tokens:
        return [
            ChunkResult(
                content=text,
                heading_path=heading_path,
                chunk_index=0,
                token_count=tokens,
                content_hash=content_hash(text),
            )
        ]

    # Long opinion — split at paragraph boundaries with citation headers
    citation_header = f"[{case_citation}]\n\n"
    paragraphs = re.split(r"\n\n+", text)
    chunks: list[ChunkResult] = []
    current_parts: list[str] = []
    current_tokens = 0
    citation_tokens = estimate_tokens(citation_header)

    for para in paragraphs:
        para_tokens = estimate_tokens(para)

        # Handle oversized paragraphs
        if para_tokens > max_tokens:
            # Flush accumulated parts first
            if current_parts:
                chunk_text = "\n\n".join(current_parts)
                if chunks:
                    chunk_text = citation_header + chunk_text
                chunks.append(
                    ChunkResult(
                        content=chunk_text,
                        heading_path=heading_path,
                        chunk_index=len(chunks),
                        token_count=estimate_tokens(chunk_text),
                        content_hash=content_hash(chunk_text),
                    )
                )
                current_parts = []
                current_tokens = 0

            # Split oversized paragraph by sentences
            sub_chunks = _split_by_sentences(
                para, heading_path, len(chunks), max_tokens, overlap_tokens,
            )
            # Prepend citation header to sub-chunks if not the first chunk overall
            for sc in sub_chunks:
                if chunks:
                    new_content = citation_header + sc.content
                    sc = ChunkResult(
                        content=new_content,
                        heading_path=sc.heading_path,
                        chunk_index=len(chunks),
                        token_count=estimate_tokens(new_content),
                        content_hash=content_hash(new_content),
                    )
                else:
                    sc = ChunkResult(
                        content=sc.content,
                        heading_path=sc.heading_path,
                        chunk_index=len(chunks),
                        token_count=sc.token_count,
                        content_hash=sc.content_hash,
                    )
                chunks.append(sc)
            continue

        if current_tokens + para_tokens > max_tokens and current_parts:
            # Flush current chunk
            chunk_text = "\n\n".join(current_parts)
            if chunks:
                chunk_text = citation_header + chunk_text
            chunks.append(
                ChunkResult(
                    content=chunk_text,
                    heading_path=heading_path,
                    chunk_index=len(chunks),
                    token_count=estimate_tokens(chunk_text),
                    content_hash=content_hash(chunk_text),
                )
            )

            # Overlap: keep trailing paragraphs up to overlap_tokens
            overlap_parts: list[str] = []
            overlap_count = 0
            for part in reversed(current_parts):
                part_tokens = estimate_tokens(part)
                if overlap_count + part_tokens > overlap_tokens:
                    break
                overlap_parts.insert(0, part)
                overlap_count += part_tokens

            current_parts = overlap_parts
            current_tokens = overlap_count + citation_tokens

        current_parts.append(para)
        current_tokens += para_tokens

    # Flush remaining
    if current_parts:
        chunk_text = "\n\n".join(current_parts)
        if chunks:
            chunk_text = citation_header + chunk_text
        chunks.append(
            ChunkResult(
                content=chunk_text,
                heading_path=heading_path,
                chunk_index=len(chunks),
                token_count=estimate_tokens(chunk_text),
                content_hash=content_hash(chunk_text),
            )
        )

    return chunks


def chunk_statute_section(
    text: str,
    citation: str,
    heading_path: str,
    max_tokens: int = 1500,
    overlap_tokens: int = 100,
) -> list[ChunkResult]:
    """Chunk a single statute section using section-boundary strategy.

    One code section = one chunk (default). If the section exceeds max_tokens,
    split at subdivision boundaries while preserving citation metadata on each chunk.

    Args:
        text: Full text of the statute section.
        citation: Canonical citation (e.g., "Cal. Lab. Code § 1102.5").
        heading_path: Hierarchy path for the section.
        max_tokens: Maximum tokens per chunk.
        overlap_tokens: Overlap tokens when splitting large sections.

    Returns:
        List of ChunkResult objects.
    """
    if not text.strip():
        return []

    tokens = estimate_tokens(text)

    if tokens <= max_tokens:
        return [
            ChunkResult(
                content=text,
                heading_path=heading_path,
                chunk_index=0,
                token_count=tokens,
                content_hash=content_hash(text),
            )
        ]

    # Section too large — split at subdivision boundaries
    return _split_at_subdivisions(text, citation, heading_path, max_tokens, overlap_tokens)


def _split_at_subdivisions(
    text: str,
    citation: str,
    heading_path: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[ChunkResult]:
    """Split a large statute section at subdivision boundaries.

    Keeps the citation prefix on each chunk for context.
    """
    # Split into subdivisions by looking for top-level markers (a), (b), etc.
    subdivision_pattern = re.compile(r"(?=^\([a-z]\)\s)", re.MULTILINE)
    parts = subdivision_pattern.split(text)

    # If no subdivision boundaries found, fall back to paragraph splitting
    if len(parts) <= 1:
        return _split_large_section(text, heading_path, 0, max_tokens, overlap_tokens)

    # Prefix text (before first subdivision) — keep with first chunk
    prefix = parts[0].strip()
    subdivision_parts = parts[1:]

    chunks: list[ChunkResult] = []
    current_parts: list[str] = []
    current_tokens = estimate_tokens(prefix) if prefix else 0
    if prefix:
        current_parts.append(prefix)

    citation_header = f"[{citation}]\n\n"
    citation_tokens = estimate_tokens(citation_header)

    for subdiv in subdivision_parts:
        subdiv_tokens = estimate_tokens(subdiv)

        if current_tokens + subdiv_tokens > max_tokens and current_parts:
            # Flush current chunk
            chunk_text = "\n\n".join(current_parts)
            # Add citation header if this isn't the first chunk
            if chunks:
                chunk_text = citation_header + chunk_text
                total_tokens = estimate_tokens(chunk_text)
            else:
                total_tokens = estimate_tokens(chunk_text)

            chunks.append(
                ChunkResult(
                    content=chunk_text,
                    heading_path=heading_path,
                    chunk_index=len(chunks),
                    token_count=total_tokens,
                    content_hash=content_hash(chunk_text),
                )
            )

            current_parts = []
            current_tokens = citation_tokens if chunks else 0

        current_parts.append(subdiv)
        current_tokens += subdiv_tokens

    # Flush remaining
    if current_parts:
        chunk_text = "\n\n".join(current_parts)
        if chunks:
            chunk_text = citation_header + chunk_text
        chunks.append(
            ChunkResult(
                content=chunk_text,
                heading_path=heading_path,
                chunk_index=len(chunks),
                token_count=estimate_tokens(chunk_text),
                content_hash=content_hash(chunk_text),
            )
        )

    return chunks


def chunk_document(
    markdown: str,
    min_tokens: int = 200,
    max_tokens: int = 1500,
    overlap_tokens: int = 100,
    document_title: str = "",
) -> list[ChunkResult]:
    """Split Markdown content into retrieval-ready chunks.

    Strategy:
    1. Split the document into sections based on headings.
    2. If a section fits within max_tokens, keep it as one chunk.
    3. If a section exceeds max_tokens, split by paragraphs with overlap.
    4. Small sections are merged with the next section if under min_tokens.

    Args:
        markdown: Cleaned Markdown text to chunk.
        min_tokens: Minimum target tokens per chunk (soft floor — very small
            sections will still be kept if they can't be merged).
        max_tokens: Maximum tokens per chunk (hard ceiling).
        overlap_tokens: Number of overlapping tokens between consecutive chunks
            when a section must be split.
        document_title: Title of the source document (used in heading path).

    Returns:
        List of ChunkResult with content, heading path, and metadata.
    """
    if not markdown.strip():
        return []

    sections = _split_into_sections(markdown)
    chunks: list[ChunkResult] = []
    chunk_index = 0

    pending_section: _Section | None = None

    for section in sections:
        # Try to merge small sections
        if pending_section is not None:
            merged_text = pending_section.text + "\n\n" + section.text
            if estimate_tokens(merged_text) <= max_tokens:
                # Merge: use the more specific heading path (the section with
                # more content, or the longer/deeper path)
                pending_tokens = estimate_tokens(pending_section.text)
                section_tokens = estimate_tokens(section.text)
                best_path = (
                    section.heading_path
                    if section_tokens > pending_tokens
                    else pending_section.heading_path
                )
                pending_section = _Section(
                    heading_path=best_path,
                    text=merged_text,
                )
                continue
            else:
                # Can't merge — flush the pending section
                new_chunks = _section_to_chunks(
                    pending_section, chunk_index, max_tokens, overlap_tokens, document_title,
                )
                chunks.extend(new_chunks)
                chunk_index += len(new_chunks)
                pending_section = None

        tokens = estimate_tokens(section.text)
        if tokens < min_tokens:
            pending_section = section
        else:
            new_chunks = _section_to_chunks(
                section, chunk_index, max_tokens, overlap_tokens, document_title,
            )
            chunks.extend(new_chunks)
            chunk_index += len(new_chunks)

    # Flush any remaining pending section
    if pending_section is not None:
        new_chunks = _section_to_chunks(
            pending_section, chunk_index, max_tokens, overlap_tokens, document_title,
        )
        chunks.extend(new_chunks)

    return chunks


@dataclass
class _Section:
    heading_path: str
    text: str


def _split_into_sections(markdown: str) -> list[_Section]:
    """Split Markdown into sections based on headings."""
    lines = markdown.split("\n")
    sections: list[_Section] = []
    current_headings: list[str] = []  # Stack of [h1, h2, h3, ...]
    current_lines: list[str] = []

    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)

        if heading_match:
            # Flush current section
            text = "\n".join(current_lines).strip()
            if text:
                path = " > ".join(current_headings) if current_headings else "Introduction"
                sections.append(_Section(heading_path=path, text=text))

            # Update heading stack
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            # Trim the stack to this level and set the new heading
            current_headings = current_headings[: level - 1]
            while len(current_headings) < level - 1:
                current_headings.append("")
            if len(current_headings) < level:
                current_headings.append(heading_text)
            else:
                current_headings[level - 1] = heading_text

            # Remove empty entries at the end
            while current_headings and not current_headings[-1]:
                current_headings.pop()

            current_lines = [line]  # Include the heading in the section text
        else:
            current_lines.append(line)

    # Flush last section
    text = "\n".join(current_lines).strip()
    if text:
        path = " > ".join(current_headings) if current_headings else "Introduction"
        sections.append(_Section(heading_path=path, text=text))

    return sections


def _section_to_chunks(
    section: _Section,
    start_index: int,
    max_tokens: int,
    overlap_tokens: int,
    document_title: str,
) -> list[ChunkResult]:
    """Convert a section to one or more chunks."""
    tokens = estimate_tokens(section.text)

    # Build the full heading path
    heading_path = section.heading_path
    if document_title and not heading_path.startswith(document_title):
        heading_path = f"{document_title} > {heading_path}" if heading_path else document_title

    if tokens <= max_tokens:
        return [
            ChunkResult(
                content=section.text,
                heading_path=heading_path,
                chunk_index=start_index,
                token_count=tokens,
                content_hash=content_hash(section.text),
            )
        ]

    # Section too large — split by paragraphs
    return _split_large_section(section.text, heading_path, start_index, max_tokens, overlap_tokens)


def _split_large_section(
    text: str,
    heading_path: str,
    start_index: int,
    max_tokens: int,
    overlap_tokens: int,
) -> list[ChunkResult]:
    """Split a large section into overlapping chunks by paragraph boundaries."""
    paragraphs = re.split(r"\n\n+", text)
    chunks: list[ChunkResult] = []
    current_parts: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)

        # Handle oversized paragraphs that exceed max_tokens on their own
        if para_tokens > max_tokens:
            # Flush any accumulated parts first
            if current_parts:
                chunk_text = "\n\n".join(current_parts)
                chunks.append(
                    ChunkResult(
                        content=chunk_text,
                        heading_path=heading_path,
                        chunk_index=start_index + len(chunks),
                        token_count=estimate_tokens(chunk_text),
                        content_hash=content_hash(chunk_text),
                    )
                )
                current_parts = []
                current_tokens = 0

            # Split the oversized paragraph by sentences
            sub_chunks = _split_by_sentences(
                para, heading_path, start_index + len(chunks), max_tokens, overlap_tokens,
            )
            chunks.extend(sub_chunks)
            continue

        if current_tokens + para_tokens > max_tokens and current_parts:
            # Flush current chunk
            chunk_text = "\n\n".join(current_parts)
            chunks.append(
                ChunkResult(
                    content=chunk_text,
                    heading_path=heading_path,
                    chunk_index=start_index + len(chunks),
                    token_count=estimate_tokens(chunk_text),
                    content_hash=content_hash(chunk_text),
                )
            )

            # Overlap: keep the last paragraph(s) up to overlap_tokens
            overlap_parts: list[str] = []
            overlap_count = 0
            for part in reversed(current_parts):
                part_tokens = estimate_tokens(part)
                if overlap_count + part_tokens > overlap_tokens:
                    break
                overlap_parts.insert(0, part)
                overlap_count += part_tokens

            current_parts = overlap_parts
            current_tokens = overlap_count

        current_parts.append(para)
        current_tokens += para_tokens

    # Flush remaining — if still over max_tokens, split by sentences
    if current_parts:
        chunk_text = "\n\n".join(current_parts)
        remaining_tokens = estimate_tokens(chunk_text)
        if remaining_tokens <= max_tokens:
            chunks.append(
                ChunkResult(
                    content=chunk_text,
                    heading_path=heading_path,
                    chunk_index=start_index + len(chunks),
                    token_count=remaining_tokens,
                    content_hash=content_hash(chunk_text),
                )
            )
        else:
            # Safety: accumulated text exceeds max_tokens — cascade to sentences
            sub_chunks = _split_by_sentences(
                chunk_text, heading_path, start_index + len(chunks),
                max_tokens, overlap_tokens,
            )
            chunks.extend(sub_chunks)

    return chunks


def _split_by_sentences(
    text: str,
    heading_path: str,
    start_index: int,
    max_tokens: int,
    overlap_tokens: int,
) -> list[ChunkResult]:
    """Split an oversized paragraph into chunks at sentence boundaries.

    Falls back to _hard_split() when no sentence boundaries exist.
    """
    sentences = re.split(r"(?<=[.?!])\s+", text)

    # If no sentence boundaries found, hard-split by character
    if len(sentences) <= 1:
        return _hard_split(text, heading_path, start_index, max_tokens)

    chunks: list[ChunkResult] = []
    current_parts: list[str] = []
    current_tokens = 0

    for sent in sentences:
        sent_tokens = estimate_tokens(sent)

        # Single sentence exceeds max — hard-split it
        if sent_tokens > max_tokens and not current_parts:
            sub_chunks = _hard_split(
                sent, heading_path, start_index + len(chunks), max_tokens,
            )
            chunks.extend(sub_chunks)
            continue

        if current_tokens + sent_tokens > max_tokens and current_parts:
            chunk_text = " ".join(current_parts)
            chunks.append(
                ChunkResult(
                    content=chunk_text,
                    heading_path=heading_path,
                    chunk_index=start_index + len(chunks),
                    token_count=estimate_tokens(chunk_text),
                    content_hash=content_hash(chunk_text),
                )
            )

            # Overlap: keep trailing sentences up to overlap_tokens
            overlap_parts: list[str] = []
            overlap_count = 0
            for part in reversed(current_parts):
                part_tokens = estimate_tokens(part)
                if overlap_count + part_tokens > overlap_tokens:
                    break
                overlap_parts.insert(0, part)
                overlap_count += part_tokens

            current_parts = overlap_parts
            current_tokens = overlap_count

        current_parts.append(sent)
        current_tokens += sent_tokens

    if current_parts:
        chunk_text = " ".join(current_parts)
        chunks.append(
            ChunkResult(
                content=chunk_text,
                heading_path=heading_path,
                chunk_index=start_index + len(chunks),
                token_count=estimate_tokens(chunk_text),
                content_hash=content_hash(chunk_text),
            )
        )

    return chunks


def _hard_split(
    text: str,
    heading_path: str,
    start_index: int,
    max_tokens: int,
) -> list[ChunkResult]:
    """Last-resort character-based split when no sentence boundaries exist."""
    max_chars = max_tokens * 4  # ~4 chars per token estimate
    chunks: list[ChunkResult] = []

    for i in range(0, len(text), max_chars):
        fragment = text[i : i + max_chars]
        chunks.append(
            ChunkResult(
                content=fragment,
                heading_path=heading_path,
                chunk_index=start_index + len(chunks),
                token_count=estimate_tokens(fragment),
                content_hash=content_hash(fragment),
            )
        )

    return chunks
