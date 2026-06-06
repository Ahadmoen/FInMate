from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer
from app.utils.logger import logger
from typing import List, Dict
import os

# ── Initialize ChromaDB (saves data to disk) ──────────────────
client = PersistentClient(path="./chroma_db")

# ── Initialize Embedding Model ────────────────────────────────
# This model converts text into numbers (vectors)
# so we can do similarity search
logger.info("Loading embedding model...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
logger.info("Embedding model loaded successfully!")

# ── Get or Create Collection ──────────────────────────────────
collection = client.get_or_create_collection(
    name="finmate_docs",
    metadata={"hnsw:space": "cosine"}
)

def add_documents(texts: List[str], metadatas: List[Dict], ids: List[str]):
    """
    Add documents to the vector database.
    Converts text to embeddings and stores them.
    """
    try:
        logger.info(f"Adding {len(texts)} documents to vector store...")

        # Convert texts to embeddings (numbers)
        embeddings = embedding_model.encode(texts).tolist()

        # Store in ChromaDB
        collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )

        logger.info(f"Successfully added {len(texts)} documents!")
        return True

    except Exception as e:
        logger.error(f"Error adding documents: {e}")
        return False


def search_documents(query: str, n_results: int = 5) -> List[Dict]:
    """
    Search for similar documents using the query.
    This is the RAG retrieval step.
    """
    try:
        logger.info(f"Searching vector store for: {query}")

        # Convert query to embedding
        query_embedding = embedding_model.encode([query]).tolist()

        # Search ChromaDB for similar documents
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=min(n_results, collection.count() or 1)
        )

        # Format results
        documents = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                documents.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0
                })

        logger.info(f"Found {len(documents)} relevant documents")
        return documents

    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return []


def get_collection_count() -> int:
    """Returns total number of documents in vector store."""
    try:
        return collection.count()
    except:
        return 0