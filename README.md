# Internal Policy Search Assistant

A RAG-based AI chatbot that allows compliance and risk teams to query 
internal policy documents in plain English and get accurate, cited answers instantly.

## Problem Statement
Finding specific policy answers across hundreds of pages of compliance 
documents takes hours. This bot does it in seconds.

## Features
- Conversational Q&A interface with memory
- Stays strictly within compliance and risk scope
- Admits when it doesn't have enough information
- Structured responses with policy area, answer, source and confidence level
- Powered by CFPB UDAAP Examination Manual

## Tech Stack
- Python
- Google Gemini API (gemini-2.5-flash)
- google-genai library
- Jupyter Notebook

## Project Status
🚧 Work in Progress — document loading complete, RAG retrieval coming next.

## Background
Built as part of an AI Engineer portfolio project, combining 7 years 
of financial services experience (5 years credit risk + 2 years controls) 
with applied AI engineering skills.

## Known Simplifications (v1) → Planned Improvements

This project is being built in intentional layers — starting with hand-rolled, simple implementations to build genuine understanding before adopting more advanced techniques. Current known simplifications:

- **Chunking**: Fixed-size, character-based chunking with overlap. Planned upgrade: token-based chunking (via `tiktoken`) and/or recursive chunking that respects paragraph/sentence boundaries — important for compliance docs where clauses shouldn't be cut mid-sentence.
- **Vector store**: Local ChromaDB, suitable for single-user/local demo. Production considerations (e.g. Pinecone, Weaviate) would apply at scale.
- **Retrieval**: Pure vector similarity search. Planned improvement: hybrid retrieval (keyword + vector) for exact regulatory term matching, which pure semantic similarity can miss.