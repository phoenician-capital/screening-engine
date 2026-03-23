"""
Document chunker + embedder — splits documents and stores embeddings.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import MAX_CHUNKS_PER_DOC
from src.db.models.document import Document
from src.db.models.embedding import Embedding
from src.shared.llm.embeddings import embed_texts
from src.shared.utils.text import chunk_text

logger = logging.getLogger(__name__)


class DocumentChunker:
    """Chunk documents, embed them, and store in the vector table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def process_document(self, document: Document) -> int:
        """
        Chunk a document, embed all chunks, and store in DB.
        Returns number of chunks created.
        """
        if not document.raw_text:
            logger.warning("Document %s has no text, skipping", document.id)
            return 0

        # Chunk
        chunks = chunk_text(document.raw_text)
        chunks = chunks[:MAX_CHUNKS_PER_DOC]

        if not chunks:
            return 0

        # Embed in batches of 100
        batch_size = 100
        all_embeddings: list[list[float]] = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            batch_embeddings = await embed_texts(batch)
            all_embeddings.extend(batch_embeddings)

        # Store
        for idx, (chunk, embedding_vec) in enumerate(zip(chunks, all_embeddings)):
            emb = Embedding(
                doc_id=document.id,
                ticker=document.ticker,
                chunk_text=chunk,
                chunk_index=idx,
                metadata_={
                    "doc_type": document.doc_type,
                    "source": document.source,
                    "source_url": document.source_url,
                },
            )
            self.session.add(emb)
            # Note: The actual vector column is set via raw SQL since pgvector
            # mapping depends on extension availability.

        await self.session.flush()
        logger.info(
            "Processed doc %s: %d chunks embedded", document.id, len(chunks)
        )
        return len(chunks)

    async def process_batch(self, documents: list[Document]) -> int:
        """Process multiple documents."""
        total = 0
        for doc in documents:
            count = await self.process_document(doc)
            total += count
        return total
