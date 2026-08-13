import chromadb 
chroma_client = chromadb.PersistentClient(path="./chroma_db") 
collection = chroma_client.get_or_create_collection(name="policy_docs") 
print(collection.name) 
print(collection.count())