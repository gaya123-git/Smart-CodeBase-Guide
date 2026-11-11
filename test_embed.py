from sentence_transformers import SentenceTransformer

from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

vectors = model.encode(
    [
        "How do I set up notifications?",
        "Configure push alerts on my phone",
        "Pizza recipe with cheese",
    ],
    normalize_embeddings=True,   # <- the new part, inside the brackets of encode
)

print(vectors[0] @ vectors[1])   # sentence 1 vs sentence 2
print(vectors[1] @ vectors[2])
# add the other two comparisons here (1 vs 3, and 2 vs 3)