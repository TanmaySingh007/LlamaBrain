# RAG API System

A Retrieval-Augmented Generation (RAG) system built with FastAPI and LlamaIndex. This system allows you to upload documents and query them using natural language.

## Features

- **Modern Web Interface**: Beautiful, responsive web UI for easy interaction
- **Document Upload**: Upload various document formats (TXT, PDF, MD, DOCX)
- **Document Management**: List, upload, and delete documents
- **Natural Language Queries**: Ask questions about your uploaded documents
- **Source Attribution**: Get answers with references to source documents
- **RESTful API**: Clean API endpoints for easy integration
- **Health Monitoring**: Detailed system health and status information
- **Persistent Indexing**: Automatic index persistence and loading
- **Docker Support**: Easy deployment with Docker and docker-compose

## Project Structure

```
rag_api/
├── main.py              # FastAPI application
├── config.py            # Configuration management
├── static/
│   └── index.html      # Web interface
├── data/               # Directory for uploaded documents
├── storage/            # Persistent index storage
├── test_comprehensive.py # Comprehensive test suite
└── .env                # Environment variables (create this file)

requirements.txt        # Python dependencies
README.md              # This file
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the `rag_api/` directory with your OpenAI API key:

```
OPENAI_API_KEY=your_actual_openai_api_key_here
```

**Important**: Replace `your_actual_openai_api_key_here` with your real OpenAI API key.

### 3. Add Sample Documents

Place some documents in the `rag_api/data/` directory. Supported formats:
- `.txt` files
- `.pdf` files  
- `.md` files
- `.docx` files

### 4. Run the Application

```bash
cd rag_api
python main.py
```

The application will be available at:
- **Web Interface**: `http://localhost:8000`
- **API Documentation**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`

## API Endpoints

### Health Check
- **GET** `/health` - Check system status

### Document Management
- **GET** `/documents` - List all uploaded documents
- **POST** `/upload-documents` - Upload a new document
- **DELETE** `/documents/{filename}` - Delete a specific document

### Query System
- **POST** `/query` - Query the RAG system

### System Management
- **POST** `/rebuild-index` - Manually rebuild the index

## Usage Examples

### 1. Check System Health
```bash
curl http://localhost:8000/health
```

### 2. Upload a Document
```bash
curl -X POST -F "file=@your_document.txt" http://localhost:8000/upload-documents
```

### 3. Query the System
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"query": "What is the main topic of the documents?", "top_k": 3}' \
  http://localhost:8000/query
```

### 4. List Documents
```bash
curl http://localhost:8000/documents
```

### 5. Delete a Document
```bash
curl -X DELETE http://localhost:8000/documents/sample_document.txt
```

### 6. Rebuild Index
```bash
curl -X POST http://localhost:8000/rebuild-index
```

## API Documentation

Once the server is running, you can access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Configuration Options

The system uses the following default configurations:
- **LLM Model**: GPT-3.5-turbo
- **Temperature**: 0.1 (for consistent responses)
- **Top-k Retrieval**: 3 (default, configurable per query)

## Troubleshooting

### Common Issues

1. **OpenAI API Key Not Set**
   - Ensure your `.env` file contains a valid OpenAI API key
   - Check that the key is not the placeholder value

2. **No Documents Found**
   - Upload documents using the `/upload-documents` endpoint
   - Ensure documents are in supported formats

3. **Import Errors**
   - Make sure all dependencies are installed: `pip install -r requirements.txt`
   - Check Python version compatibility (Python 3.8+ recommended)

## Next Steps

This is a basic RAG system. You can extend it with:
- Advanced document processing
- Custom embedding models
- Vector database persistence
- User authentication
- Rate limiting
- Advanced query processing

## License

This project is open source and available under the MIT License. 