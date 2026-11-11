import chromadb
from sentence_transformers import SentenceTransformer
from load_docs import load_all_chunks

DB_PATH = "chroma_db"
COLLECTION = "readme_docs"
MODEL_NAME = "BAAI/bge-small-en-v1.5"

chunks = load_all_chunks()

client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection(
    name=COLLECTION, metadata={"hnsw:space": "cosine"}
)

stored_ids = set(collection.get()["ids"])
current_ids = {c["id"] for c in chunks}


old_ids = list(stored_ids - current_ids)
if old_ids:
    collection.delete(ids=old_ids)


new_chunks = [c for c in chunks if c["id"] not in stored_ids]
print(f"{len(chunks)} chunks, {len(stored_ids & current_ids)} already stored, "
      f"{len(new_chunks)} to embed")

if new_chunks:
    model = SentenceTransformer(MODEL_NAME)
    for start in range(0, len(new_chunks), 64):
        batch = new_chunks[start:start + 64]
        vectors = model.encode([c["text"] for c in batch], normalize_embeddings=True)
        collection.add(
            ids=[c["id"] for c in batch],
            embeddings=vectors.tolist(),
            documents=[c["text"] for c in batch],
            metadatas=[
                {"file": c["file"], "title": c["title"], "heading": c["heading"]}
                for c in batch
            ],
        )

print("Database now holds", collection.count(), "chunks")