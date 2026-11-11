from sentence_transformers import SentenceTransformer
from load_docs import load_all_chunks

model = SentenceTransformer("BAAI/bge-small-en-v1.5")
print("Model limit:", model.max_seq_length)

chunks = load_all_chunks()
token_counts = [len(model.tokenizer.encode(c["text"])) for c in chunks]

too_long = sum(1 for n in token_counts if n > model.max_seq_length)
print("Chunks:", len(chunks))
print("Over the limit:", too_long)
print("Largest:", max(token_counts))

order = sorted(range(len(chunks)), key=lambda i: token_counts[i], reverse=True)
over = [i for i, n in enumerate(token_counts) if n > model.max_seq_length]
for i in sorted(over, key=lambda i: token_counts[i], reverse=True):
    print(token_counts[i], chunks[i]["file"], "|", chunks[i]["heading"], "|", repr(chunks[i]["text"][:30]))