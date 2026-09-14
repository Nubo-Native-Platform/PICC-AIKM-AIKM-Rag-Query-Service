from pymilvus import (
    connections,
    Collection,
    utility
)
from openai import OpenAI
from langchain_huggingface import HuggingFaceEmbeddings

from src.core.config import settings

# ---------- Embedding Models ----------
# Initialize HF embedder lazily to save resources if not used
_hf_embedder = None

def get_hf_embedder():
    global _hf_embedder
    if _hf_embedder is None:
        _hf_embedder = HuggingFaceEmbeddings(
            model_name=settings.LOCAL_EMBEDDING_MODEL,
            encode_kwargs={"normalize_embeddings": True},
        )
    return _hf_embedder

# ---------- Milvus Connection ----------
connections.connect(
    db_name=settings.MILVUS_DB_NAME,
    host=settings.MILVUS_HOST,
    port=settings.MILVUS_PORT
)

# ---------- OpenAI Client ----------
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# ---------- Embedding ----------
def embed_text(text: str, model_type: str = 'public') -> list[float]:
    if model_type == 'local':
        print(f"🧬 Using Local Embedding Model (HuggingFace: {settings.LOCAL_EMBEDDING_MODEL})")
        embedder = get_hf_embedder()
        return embedder.embed_query(text)
    
    # Default to public (OpenAI)
    print(f"🌐 Using Public Embedding Model (OpenAI: {settings.EMBEDDING_MODEL})")
    response = client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=text
    )
    return response.data[0].embedding

# ---------- Collection Resolution ----------
def resolve_collections(names: list[str] | None = None, model_type: str = 'public') -> list[str]:
    """
    Validate requested collection names against what actually exists in Milvus.
    Never raises — always falls back to the default collection if no
    valid names are found (or none were provided).
    """
    existing = set(utility.list_collections())
    print(f"📦 Existing collections: {existing}")

    if not names:
        # User requirement: if modelType is 'public' and no names, default to 'ai_knowledge_base_embeddings'
        if model_type == 'public'or model_type == 'openai':
            default_collection = settings.MILVUS_COLLECTION_NAME
        else:
            default_collection = settings.MILVUS_COLLECTION_NAME_LOCAL
        
        print(f"ℹ️ No collection names provided. Defaulting to: {default_collection} (modelType: {model_type})")
        return [default_collection]

    valid = [name for name in names if name in existing]
    missing = [name for name in names if name not in existing]

    if missing:
        print(f"⚠️ Skipping unknown collections: {missing}")

    if not valid:
        # Determine the correct default based on model_type
        fallback = settings.MILVUS_COLLECTION_NAME if model_type == 'public' else settings.MILVUS_COLLECTION_NAME_LOCAL
        print(f"⚠️ No valid collections in {names}, falling back to default: {fallback} (modelType: {model_type})")
        return [fallback]

    return valid

# ---------- Search V2: multiple sources----------
def search(query: str, names: list[str] | None = None, top_k: int = 3, threshold: float = 0.0, model_type: str = 'public'):
    print(f"🔍 Search started | modelType: {model_type} | threshold: {threshold} | top_k: {top_k} | names: {names}")
    
    collection_names = resolve_collections(names, model_type=model_type)
    query_embedding = embed_text(query, model_type=model_type)

    all_hits = []

    for name in collection_names:
        collection = Collection(name)
        collection.load()

        # Proactively check for dimension mismatch before searching
        vector_field = next((f for f in collection.schema.fields if f.name == "embedding"), None)
        if vector_field:
            expected_dim = vector_field.params.get("dim")
            actual_dim = len(query_embedding)
            if expected_dim != actual_dim:
                print(f"⚠️ Skipping collection '{name}': Dimension mismatch (Expected {expected_dim}, got {actual_dim}).")
                continue

        try:
            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"ef": 64}},
                limit=top_k,
                output_fields=["content", "metadata", "source", "doc_type"]
            )

            for hit in results[0]:
                if hit.score >= threshold:
                    metadata = hit.entity.get("metadata") or {}
                    all_hits.append({
                        "score": hit.score,
                        "text": hit.entity.get("content"),
                        "metadata": metadata,
                        "source": hit.entity.get("source"),
                        "doc_type": hit.entity.get("doc_type"),
                        "collection": name,
                    })
        except Exception as e:
            print(f"❌ Collection '{name}' search failed: {e}")

    # Merge results across collections, keep the overall best top_k
    all_hits.sort(key=lambda h: h["score"], reverse=True)

    return all_hits[:top_k]


# ==============================================================================
# OLDER VERSIONS - embed_text and search
# ==============================================================================
# def embed_text(text: str) -> list[float]:
#     response = client.embeddings.create(
#         model=settings.EMBEDDING_MODEL,
#         input=text
#     )
#     return response.data[0].embedding
#
# # ---------- Search ----------
# def search(query: str, top_k: int = 3):
#     collections = utility.list_collections()
#     print("📦 Existing collections:", collections)
#     collection = Collection(settings.MILVUS_COLLECTION_NAME)
#     collection.load()

#     query_embedding = embed_text(query)

#     results = collection.search(
#         data=[query_embedding],
#         anns_field="embedding",
#         param={"metric_type": "COSINE", "params": {"ef": 64}},
#         limit=top_k,
#         output_fields=["content"]
#     )

#     print(results.count)
#     for hit in results[0]:
#         print(hit.entity.keys())
    
#     return [
#         {
#             "score": hit.score,
#             "text": hit.entity.get("content")
#         }
#         for hit in results[0]
#     ]
