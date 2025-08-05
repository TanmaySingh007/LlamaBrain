#!/usr/bin/env python3
"""
Document Upload Helper for RAG Brain
"""

import os
import shutil
from pathlib import Path

def upload_document_to_rag():
    """Helper function to upload documents to the RAG system"""
    
    print("📚 RAG Brain - Document Upload Helper")
    print("=" * 50)
    
    # Check if data directory exists
    data_dir = "data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"📁 Created {data_dir} directory")
    
    # List current documents
    print("\n📋 Current documents in the system:")
    documents = []
    for file in os.listdir(data_dir):
        if file.endswith(('.pdf', '.txt', '.md', '.docx')):
            file_path = os.path.join(data_dir, file)
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            documents.append((file, size_mb))
            print(f"   📄 {file} ({size_mb:.2f} MB)")
    
    if not documents:
        print("   No documents found")
    
    print("\n📤 To upload new documents:")
    print("   1. Copy your PDF/TXT/MD files to the 'data' folder")
    print("   2. The system will automatically index them")
    print("   3. You can then search through them via the web interface")
    
    print("\n📁 Data directory location:")
    print(f"   {os.path.abspath(data_dir)}")
    
    print("\n🌐 Access your RAG Brain at: http://localhost:8000")
    print("📊 Features available:")
    print("   • Upload documents via web interface")
    print("   • Search through all documents")
    print("   • Download answers in PDF/TXT/JSON")
    print("   • Real-time performance monitoring")
    
    return documents

if __name__ == "__main__":
    upload_document_to_rag() 