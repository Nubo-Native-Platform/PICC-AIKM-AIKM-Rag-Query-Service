import logging
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Any, List, Optional
from src.core.config import settings
from src.core.milvus_vectorstore import search
from src.services.rag_summarizer import (
    format_rag_results,
    summarise_rag_output,
)
from src.services.rag_response_builder import collect_rag_images, collect_rag_sources


for noisy_logger in (
    "httpx",
    "httpcore",
    "huggingface_hub",
    "sentence_transformers",
):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)


app = FastAPI(
    title="NNP RAG Access API",
    version="1.0.0"
)

# Request body model
class QuestionRequest(BaseModel):
    question: str
    collectionNames: List[str] = Field(default_factory=list)
    sourceCount: int = Field(default=3, ge=1)
    similarityThreshold: float = Field(default=0.0, ge=0.0)
    extendPublicInfo: bool = True
    modelType: str = "public"
    ModelName: Optional[str] = None
    APIKey: Optional[str] = None

# Response model (optional but recommended)
class RAGResult(BaseModel):
    score: float
    text: Optional[str]
    metadata: Optional[dict[str, Any]] = None
    source: Optional[str] = None
    doc_type: Optional[str] = None
    collection: Optional[str] = None

class RAGImage(BaseModel):
    url: str
    asset_id: Optional[str] = None
    type: Optional[str] = None
    label: Optional[str] = None
    caption: Optional[str] = None
    summary: Optional[str] = None
    bucket: Optional[str] = None
    object_key: Optional[str] = None
    page_number: Optional[int] = None
    figure_index: Optional[int] = None
    doc_name: Optional[str] = None
    mime_type: Optional[str] = None
    bbox: Optional[list[float]] = None

class RAGSource(BaseModel):
    score: float
    source: Optional[str] = None
    doc_type: Optional[str] = None
    collection: Optional[str] = None
    doc_name: Optional[str] = None
    page_number: Optional[int] = None

class AskResponse(BaseModel):
    answer: List[RAGResult]
    images: List[RAGImage] = Field(default_factory=list)
    sources: List[RAGSource] = Field(default_factory=list)

@app.get("/")
def health_check():
    return {
        "app": settings.RAG_SERVICE_APP_NAME,
        "env": settings.APP_ENV,
        "status": "OK"
    }

@app.post("/ask", response_model=AskResponse)
def ask_question(request: QuestionRequest):
    print(f"Received /ask request: {request.model_dump(exclude={'APIKey'})}")
    model_type = (
        'local' if (request.modelType or '').lower() == 'local' else 'public'
    )
    rag_results = search(
        request.question, 
        names=request.collectionNames, 
        top_k=request.sourceCount,
        threshold=request.similarityThreshold, 
        model_type=model_type
    )
    rag_text = format_rag_results(rag_results)
    print(f"RAG pulled {len(rag_results)} chunks")
    images = collect_rag_images(rag_results)
    sources = collect_rag_sources(rag_results)

    summary = summarise_rag_output(
        rag_text,
        question=request.question,
        extend_public_info=request.extendPublicInfo,
        model_type=model_type,
        model_name=request.ModelName,
        api_key=request.APIKey,
    )
    print(f"Summary generated with length: {len(summary)}")
    if not summary:
        return {
            "answer": rag_results,
            "images": images,
            "sources": sources,
        }

    return {
        "answer": [
            {
                "score": 1.0,
                "text": summary
            }
        ],
        "images": images,
        "sources": sources,
    }


def main():
    print("Hello from ai-rag-query-service!")


if __name__ == "__main__":
    main()

# ==============================================================================
# OLDER VERSION - ask_question: ONLY accept question and return raw RAG output
# ==============================================================================
# @app.post("/ask", response_model=AskResponse)
# def ask_question(request: QuestionRequest):
#     ans = search(request.question)
#     return {"answer": ans}
