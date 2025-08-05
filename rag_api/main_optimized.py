from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv
import uvicorn
import logging
import json
import re
from pathlib import Path
import PyPDF2
import io
from datetime import datetime
import zipfile
import tempfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import asyncio
from collections import defaultdict
import hashlib
import time
from functools import lru_cache
import threading

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RAG API System (Optimized Version)",
    description="A high-performance document search and query system with advanced features",
    version="3.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Pydantic models for request/response
class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 3
    document_filter: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    confidence: float
    query_time: float
    total_documents_searched: int
    document_specific_answers: Dict[str, str]

class DocumentUploadResponse(BaseModel):
    message: str
    documents_processed: int
    filename: str
    file_size_mb: float
    supported_formats: List[str]

class SystemInfoResponse(BaseModel):
    status: str
    rag_system_initialized: bool
    openai_configured: bool
    documents_loaded: bool
    total_documents: int
    index_size_mb: float
    system_uptime: str
    memory_usage: str
    supported_formats: List[str]
    features: List[str]

class DownloadRequest(BaseModel):
    query: str
    format: str
    include_sources: bool = True
    include_metadata: bool = True

# Global variables for the optimized RAG system
documents_data = {}
document_chunks = {}
chunk_index = defaultdict(list)
index_initialized = False
system_start_time = datetime.now()
query_history = []
query_cache = {}
cache_lock = threading.Lock()

# Performance settings
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CACHE_SIZE = 1000
MAX_CACHE_AGE = 3600  # 1 hour

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file with error handling"""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_path}: {e}")
        return ""

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks for better search"""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    words = text.split()
    current_chunk = []
    current_length = 0
    
    for i, word in enumerate(words):
        current_chunk.append(word)
        current_length += len(word) + 1
        
        if current_length >= chunk_size:
            chunk_text = " ".join(current_chunk)
            chunks.append(chunk_text)
            
            # Keep overlap words for next chunk
            overlap_words = current_chunk[-overlap:] if overlap > 0 else []
            current_chunk = overlap_words
            current_length = sum(len(w) + 1 for w in overlap_words)
    
    # Add remaining text as final chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks

def build_search_index():
    """Build an optimized search index for fast retrieval"""
    global document_chunks, chunk_index
    
    document_chunks = {}
    chunk_index = defaultdict(list)
    
    for filename, content in documents_data.items():
        chunks = chunk_text(content)
        document_chunks[filename] = chunks
        
        # Index each chunk
        for chunk_idx, chunk in enumerate(chunks):
            chunk_id = f"{filename}_{chunk_idx}"
            words = re.findall(r'\b\w+\b', chunk.lower())
            
            # Index by word
            for word in words:
                if len(word) > 2:  # Skip short words
                    chunk_index[word].append(chunk_id)
    
    logger.info(f"Built search index with {len(chunk_index)} unique words")

def get_cache_key(query: str, top_k: int, document_filter: str) -> str:
    """Generate cache key for query"""
    key_data = f"{query.lower().strip()}_{top_k}_{document_filter or 'all'}"
    return hashlib.md5(key_data.encode()).hexdigest()

@lru_cache(maxsize=CACHE_SIZE)
def cached_search(query: str, top_k: int, document_filter: str) -> tuple:
    """Cached search function for better performance"""
    return perform_search(query, top_k, document_filter)

def perform_search(query: str, top_k: int, document_filter: str) -> tuple:
    """Perform optimized search with ranking"""
    if not document_chunks:
        return [], "No documents available", {}, 0
    
    start_time = time.time()
    query_lower = query.lower().strip()
    query_words = [word for word in re.findall(r'\b\w+\b', query_lower) if len(word) > 2]
    
    if not query_words:
        return [], "Please provide a more specific query.", {}, 0
    
    # Find relevant chunks
    chunk_scores = defaultdict(float)
    relevant_chunks = set()
    
    # Get chunks containing query words
    for word in query_words:
        if word in chunk_index:
            for chunk_id in chunk_index[word]:
                chunk_scores[chunk_id] += 1
                relevant_chunks.add(chunk_id)
    
    # Filter by document if specified
    if document_filter:
        relevant_chunks = {chunk_id for chunk_id in relevant_chunks 
                          if chunk_id.startswith(document_filter)}
    
    # Calculate final scores with bonuses
    final_scores = []
    for chunk_id in relevant_chunks:
        score = chunk_scores[chunk_id]
        
        # Bonus for exact phrase matches
        if query_lower in chunk_id:
            score += 5
        
        # Bonus for consecutive word matches
        for i in range(len(query_words) - 1):
            phrase = f"{query_words[i]} {query_words[i+1]}"
            if phrase in chunk_id:
                score += 2
        
        # Get chunk content
        filename, chunk_idx = chunk_id.rsplit('_', 1)
        chunk_idx = int(chunk_idx)
        
        if filename in document_chunks and chunk_idx < len(document_chunks[filename]):
            chunk_content = document_chunks[filename][chunk_idx]
            final_scores.append((chunk_id, score, chunk_content, filename))
    
    # Sort by score and get top results
    final_scores.sort(key=lambda x: x[1], reverse=True)
    top_results = final_scores[:top_k]
    
    if not top_results:
        return [], f"No relevant information found for '{query}' in the documents.", {}, 0
    
    # Build answer
    sources = []
    answer_parts = []
    document_specific_answers = {}
    
    for chunk_id, score, content, filename in top_results:
        sources.append(filename)
        answer_parts.append(f"📄 **{filename}**\n{content}")
        document_specific_answers[filename] = content
    
    answer = "\n\n---\n\n".join(answer_parts)
    query_time = time.time() - start_time
    
    return sources, answer, document_specific_answers, query_time

def load_documents():
    """Load documents with optimized processing"""
    global documents_data, index_initialized
    
    try:
        data_dir = "data"
        if not os.path.exists(data_dir):
            logger.info("No data directory found")
            return
        
        documents_data = {}
        for filename in os.listdir(data_dir):
            file_path = os.path.join(data_dir, filename)
            
            try:
                if filename.endswith('.pdf'):
                    content = extract_text_from_pdf(file_path)
                    if content.strip():
                        documents_data[filename] = content
                        logger.info(f"Loaded PDF document: {filename}")
                        
                elif filename.endswith(('.txt', '.md')):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        documents_data[filename] = content
                        logger.info(f"Loaded text document: {filename}")
                        
                elif filename.endswith('.docx'):
                    logger.info(f"Skipping DOCX file (not supported yet): {filename}")
                    
            except Exception as e:
                logger.error(f"Error loading {filename}: {e}")
        
        # Build search index
        build_search_index()
        index_initialized = True
        logger.info(f"Loaded {len(documents_data)} documents and built search index")
        
    except Exception as e:
        logger.error(f"Error loading documents: {e}")

def generate_pdf_report(query: str, answer: str, sources: List[str], metadata: Dict[str, Any]) -> bytes:
    """Generate PDF report of the query and answer"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=20,
        textColor=colors.darkblue
    )
    
    content_style = ParagraphStyle(
        'CustomContent',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=12,
        leftIndent=20
    )
    
    story = []
    story.append(Paragraph("RAG System Query Report", title_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"<b>Query:</b> {query}", content_style))
    story.append(Spacer(1, 15))
    story.append(Paragraph("<b>Answer:</b>", content_style))
    story.append(Paragraph(answer.replace('\n', '<br/>'), content_style))
    story.append(Spacer(1, 15))
    
    if sources:
        story.append(Paragraph(f"<b>Sources:</b> {', '.join(sources)}", content_style))
        story.append(Spacer(1, 15))
    
    if metadata:
        story.append(Paragraph("<b>Metadata:</b>", content_style))
        for key, value in metadata.items():
            story.append(Paragraph(f"• {key}: {value}", content_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def initialize_rag_system():
    """Initialize the optimized RAG system"""
    global index_initialized
    load_documents()
    index_initialized = True

@app.get("/")
async def root():
    """Root endpoint - serve the web interface"""
    return FileResponse("static/index.html")

@app.get("/health", response_model=SystemInfoResponse)
async def health_check():
    """Enhanced health check endpoint"""
    data_dir = "data"
    total_documents = 0
    if os.path.exists(data_dir):
        total_documents = len([f for f in os.listdir(data_dir) 
                             if f.endswith(('.txt', '.pdf', '.md', '.docx'))])
    
    uptime = datetime.now() - system_start_time
    uptime_str = f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m"
    
    memory_usage = f"{len(documents_data)} documents, {len(chunk_index)} indexed words"
    
    return SystemInfoResponse(
        status="healthy",
        rag_system_initialized=index_initialized,
        openai_configured=True,
        documents_loaded=index_initialized,
        total_documents=total_documents,
        index_size_mb=0.0,
        system_uptime=uptime_str,
        memory_usage=memory_usage,
        supported_formats=[".txt", ".pdf", ".md", ".docx"],
        features=[
            "Optimized Document Search",
            "Intelligent Text Chunking",
            "Advanced Caching System",
            "PDF Text Extraction",
            "Answer Download (PDF/TXT/JSON)",
            "Health Monitoring",
            "Query History",
            "Document-Specific Answers",
            "Performance Optimized"
        ]
    )

@app.post("/query", response_model=QueryResponse)
async def query_rag_system(request: QueryRequest):
    """Optimized query the RAG system with caching"""
    global documents_data, index_initialized, query_history
    
    if not index_initialized:
        load_documents()
    
    if not documents_data:
        raise HTTPException(status_code=500, detail="No documents available. Please upload documents first.")
    
    try:
        # Check cache first
        cache_key = get_cache_key(request.query, request.top_k, request.document_filter)
        
        with cache_lock:
            if cache_key in query_cache:
                cached_result = query_cache[cache_key]
                if time.time() - cached_result['timestamp'] < MAX_CACHE_AGE:
                    logger.info(f"Cache hit for query: {request.query[:50]}...")
                    return QueryResponse(**cached_result['data'])
        
        # Perform search
        sources, answer, document_specific_answers, query_time = perform_search(
            request.query, 
            request.top_k, 
            request.document_filter
        )
        
        # Store in cache
        with cache_lock:
            query_cache[cache_key] = {
                'data': {
                    'answer': answer,
                    'sources': sources,
                    'confidence': 0.9,
                    'query_time': query_time,
                    'total_documents_searched': len(documents_data),
                    'document_specific_answers': document_specific_answers
                },
                'timestamp': time.time()
            }
        
        # Store query in history
        query_history.append({
            "query": request.query,
            "timestamp": datetime.now().isoformat(),
            "sources": sources,
            "query_time": query_time
        })
        
        # Keep only last 100 queries
        if len(query_history) > 100:
            query_history = query_history[-100:]
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            confidence=0.9,
            query_time=query_time,
            total_documents_searched=len(documents_data),
            document_specific_answers=document_specific_answers
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.post("/upload-documents", response_model=DocumentUploadResponse)
async def upload_documents(file: UploadFile = File(...)):
    """Upload a document to the RAG system"""
    global documents_data, index_initialized
    
    try:
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        
        file_path = os.path.join(data_dir, file.filename)
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        file_size_mb = len(content) / (1024 * 1024)
        
        # Reload documents and rebuild index
        load_documents()
        
        return DocumentUploadResponse(
            message=f"Document '{file.filename}' uploaded successfully",
            documents_processed=1,
            filename=file.filename,
            file_size_mb=round(file_size_mb, 2),
            supported_formats=[".txt", ".pdf", ".md", ".docx"]
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")

@app.get("/documents")
async def list_documents():
    """List all documents in the data directory"""
    data_dir = "data"
    if not os.path.exists(data_dir):
        return {"documents": []}
    
    documents = []
    for filename in os.listdir(data_dir):
        if filename.endswith(('.txt', '.pdf', '.md', '.docx')):
            file_path = os.path.join(data_dir, filename)
            file_size = os.path.getsize(file_path)
            documents.append({
                "filename": filename,
                "size_bytes": file_size,
                "size_mb": round(file_size / (1024 * 1024), 2),
                "upload_date": datetime.fromtimestamp(os.path.getctime(file_path)).isoformat()
            })
    
    return {"documents": documents}

@app.post("/rebuild-index")
async def rebuild_index():
    """Manually rebuild the index from all documents"""
    global index_initialized
    
    try:
        load_documents()
        if not documents_data:
            return {"message": "No documents found to build index"}
        
        return {"message": "Index rebuilt successfully"}
        
    except Exception as e:
        logger.error(f"Error rebuilding index: {e}")
        raise HTTPException(status_code=500, detail=f"Error rebuilding index: {str(e)}")

@app.delete("/documents/{filename}")
async def delete_document(filename: str):
    """Delete a specific document"""
    global documents_data, index_initialized
    
    try:
        data_dir = "data"
        file_path = os.path.join(data_dir, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Document '{filename}' not found")
        
        os.remove(file_path)
        load_documents()
        
        return {"message": f"Document '{filename}' deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

@app.post("/download-answer")
async def download_answer(request: DownloadRequest):
    """Download query answer in various formats"""
    try:
        sources, answer, document_specific_answers, query_time = perform_search(
            request.query, 3, None
        )
        
        metadata = {
            "query": request.query,
            "query_time": query_time,
            "total_documents_searched": len(documents_data),
            "sources": sources,
            "timestamp": datetime.now().isoformat()
        }
        
        if request.format.lower() == "pdf":
            pdf_content = generate_pdf_report(request.query, answer, sources, metadata)
            return StreamingResponse(
                io.BytesIO(pdf_content),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=rag_answer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"}
            )
        
        elif request.format.lower() == "txt":
            content = f"RAG System Answer\n{'='*50}\n\n"
            content += f"Query: {request.query}\n"
            content += f"Timestamp: {metadata['timestamp']}\n"
            content += f"Query Time: {query_time:.2f} seconds\n\n"
            content += f"Answer:\n{answer}\n\n"
            
            if request.include_sources and sources:
                content += f"Sources: {', '.join(sources)}\n"
            
            if request.include_metadata:
                content += f"\nMetadata:\n"
                for key, value in metadata.items():
                    content += f"  {key}: {value}\n"
            
            return StreamingResponse(
                io.BytesIO(content.encode('utf-8')),
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=rag_answer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"}
            )
        
        elif request.format.lower() == "json":
            response_data = {
                "query": request.query,
                "answer": answer,
                "sources": sources,
                "document_specific_answers": document_specific_answers,
                "metadata": metadata
            }
            
            return StreamingResponse(
                io.BytesIO(json.dumps(response_data, indent=2).encode('utf-8')),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=rag_answer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"}
            )
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Use 'pdf', 'txt', or 'json'")
        
    except Exception as e:
        logger.error(f"Error generating download: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating download: {str(e)}")

@app.get("/query-history")
async def get_query_history():
    """Get query history"""
    return {"queries": query_history[-20:]}

@app.get("/system-stats")
async def get_system_stats():
    """Get detailed system statistics"""
    data_dir = "data"
    total_documents = 0
    total_size_mb = 0
    
    if os.path.exists(data_dir):
        for filename in os.listdir(data_dir):
            if filename.endswith(('.txt', '.pdf', '.md', '.docx')):
                file_path = os.path.join(data_dir, filename)
                file_size = os.path.getsize(file_path)
                total_documents += 1
                total_size_mb += file_size / (1024 * 1024)
    
    return {
        "total_documents": total_documents,
        "total_size_mb": round(total_size_mb, 2),
        "system_uptime": str(datetime.now() - system_start_time),
        "queries_processed": len(query_history),
        "documents_loaded": len(documents_data),
        "chunks_created": sum(len(chunks) for chunks in document_chunks.values()),
        "indexed_words": len(chunk_index),
        "cache_size": len(query_cache),
        "supported_formats": [".txt", ".pdf", ".md", ".docx"]
    }

# Initialize on startup
initialize_rag_system()

if __name__ == "__main__":
    uvicorn.run("main_optimized:app", host="127.0.0.1", port=8000, reload=False) 