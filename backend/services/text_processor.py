"""Text processing service for document chunking and extraction."""

import re
from pathlib import Path

import structlog
from pypdf import PdfReader

from backend.config import get_settings

settings = get_settings()
logger = structlog.get_logger(__name__)


class TextProcessor:
    """Service for extracting and chunking text from documents."""

    def __init__(
        self,
        chunk_size: int = settings.chunk_size,
        chunk_overlap: int = settings.chunk_overlap,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text content from a PDF file."""
        reader = PdfReader(file_path)
        text_parts = []

        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        full_text = "\n\n".join(text_parts)
        logger.info(
            "pdf_text_extracted",
            file_path=file_path,
            pages=len(reader.pages),
            text_length=len(full_text),
        )
        return full_text

    def extract_text_from_file(self, file_path: str) -> str:
        """Extract text from any supported file type."""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".pdf":
            return self.extract_text_from_pdf(file_path)
        elif ext in [".txt", ".md"]:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            logger.info(
                "text_file_extracted",
                file_path=file_path,
                text_length=len(text),
            )
            return text
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        # Remove NUL characters that break PostgreSQL
        text = text.replace("\x00", "")
        # Remove other control characters except newlines and tabs
        text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        return text

    def _is_quality_chunk(self, content: str) -> bool:
        """Check if chunk has sufficient quality (not TOC, not mostly dots/spaces)."""
        if len(content) < 50:  # Too short
            return False
        
        # Count dots (table of contents indicator)
        dot_ratio = content.count('.') / len(content)
        if dot_ratio > 0.3:  # More than 30% dots = likely TOC
            return False
        
        # Count actual words vs special characters
        words = re.findall(r'\b\w+\b', content)
        if len(words) < 10:  # Too few words
            return False
        
        # Check for repetitive patterns (TOC indicators)
        if content.count('....') > 3:
            return False
        
        return True

    def chunk_text(self, text: str) -> list[dict]:
        """
        Split text into overlapping chunks.

        Args:
            text: Full text content

        Returns:
            List of chunk dictionaries with content and metadata
        """
        text = self.clean_text(text)

        if len(text) <= self.chunk_size:
            chunk_content = text
            if self._is_quality_chunk(chunk_content):
                return [
                    {
                        "content": chunk_content,
                        "chunk_index": 0,
                        "start_char": 0,
                        "end_char": len(text),
                    }
                ]
            else:
                return []

        chunks = []
        start = 0
        chunk_index = 0
        skipped_chunks = 0

        while start < len(text):
            end = start + self.chunk_size

            if end < len(text):
                break_point = self._find_break_point(text, start, end)
                if break_point > start:
                    end = break_point

            chunk_content = text[start:end].strip()

            # Only add quality chunks
            if chunk_content and self._is_quality_chunk(chunk_content):
                chunks.append(
                    {
                        "content": chunk_content,
                        "chunk_index": chunk_index,
                        "start_char": start,
                        "end_char": end,
                    }
                )
                chunk_index += 1
            elif chunk_content:
                skipped_chunks += 1

            start = end - self.chunk_overlap
            if start >= len(text) - self.chunk_overlap:
                break

        logger.info(
            "text_chunked",
            original_length=len(text),
            num_chunks=len(chunks),
            skipped_chunks=skipped_chunks,
            chunk_size=self.chunk_size,
            overlap=self.chunk_overlap,
        )

        return chunks

    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """Find a natural break point (sentence/paragraph end) near the end position."""
        search_start = max(start, end - 100)
        segment = text[search_start:end]

        for delimiter in ["\n\n", ".\n", ". ", "\n", "? ", "! "]:
            last_pos = segment.rfind(delimiter)
            if last_pos != -1:
                return search_start + last_pos + len(delimiter)

        return end
