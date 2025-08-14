from flask import Flask, request, jsonify
import openai
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from datetime import datetime

app = Flask(__name__)

# Configs
AZURE_OPENAI_KEY = "6opq3dVom794ZZWcn1qflev786NF1o81LffwRhwWNWKHteoXKGwFJQQJ99BHACrIdLPXJ3w3AAABACOGNK8i"
AZURE_OPENAI_ENDPOINT = "https://jeliv-tender-oai-dev-sn.openai.azure.com/"
AZURE_OPENAI_API_VERSION = "turbo-2024-04-09"
AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4"

SEARCH_ENDPOINT = "https://jeliv-poc-ais-dev-sn.search.windows.net"
SEARCH_KEY = "OJYtmoCAxBgIhNIXaMOyO6izzYHHnud5swVZe7XiQnAzSeCJXa3"
SEARCH_INDEX_NAME = "jeliv-gold-tenders-rag-indexer"

def build_filter_expression(params: dict) -> str:
    """
    Build OData filter string based on provided filter parameters.
    Handles strings and date for metadata_storage_last_modified.
    """
    filters = []
    
    if 'tender_number' in params and params['tender_number']:
        filters.append(f"tender_number eq '{params['tender_number']}'")
        
    if 'document_type' in params and params['document_type']:
        filters.append(f"document_type eq '{params['document_type']}'")
        
    if 'metadata_storage_name' in params and params['metadata_storage_name']:
        filters.append(f"metadata_storage_name eq '{params['metadata_storage_name']}'")
        
    if 'metadata_storage_path' in params and params['metadata_storage_path']:
        filters.append(f"metadata_storage_path eq '{params['metadata_storage_path']}'")
        
    if 'metadata_storage_last_modified' in params and params['metadata_storage_last_modified']:
        # Expecting ISO 8601 date string, e.g. "2025-08-12T00:00:00Z"
        # Filter example: metadata_storage_last_modified ge 2025-08-01T00:00:00Z and metadata_storage_last_modified le 2025-08-31T23:59:59Z
        # For simplicity, here we filter for exact date match or you can modify as needed
        date_val = params['metadata_storage_last_modified']
        # Optionally validate date format here
        filters.append(f"metadata_storage_last_modified eq {date_val}")
    
    return " and ".join(filters) if filters else None

def query_azure_search(query, top=5, search_fields=None, filter_expr=None):
    client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
       # index_name=SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_KEY)
    )

    search_kwargs = {"top": top}
    if search_fields:
        if isinstance(search_fields, str):
            search_fields = [f.strip() for f in search_fields.split(",")]
        search_kwargs["search_fields"] = search_fields
    
    if filter_expr:
        search_kwargs["filter"] = filter_expr
    
    results = client.search(query, **search_kwargs)
    passages = [result.get("content", "") for result in results]
    return "\n\n".join(passages)

def generate_answer(user_query, top=5, search_fields=None, filter_expr=None):
    context = query_azure_search(user_query, top=top, search_fields=search_fields, filter_expr=filter_expr)
    prompt = (
        f"Answer the question based on the context below:\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {user_query}"
    )

    openai.api_type = "azure"
    openai.api_base = AZURE_OPENAI_ENDPOINT
    openai.api_key = AZURE_OPENAI_KEY
    openai.api_version = AZURE_OPENAI_API_VERSION

    response = openai.ChatCompletion.create(
        engine=AZURE_OPENAI_DEPLOYMENT_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1000
    )
    return response.choices[0].message.content

@app.route("/ask", methods=["POST"])
def ask():
    data = request.json
    if not data or "question" not in data:
        return jsonify({"error": "Please provide a JSON body with a 'question' field."}), 400

    question = data["question"]
    top = int(data.get("top", 5))
    search_fields = data.get("search_fields")  # Optional comma-separated string or list

    # Build filter expression from possible filters
    filter_params = {
        "tender_number": data.get("tender_number"),
        "document_type": data.get("document_type"),
        "metadata_storage_name": data.get("metadata_storage_name"),
        "metadata_storage_path": data.get("metadata_storage_path"),
        "metadata_storage_last_modified": data.get("metadata_storage_last_modified"),
    }
    filter_expr = build_filter_expression(filter_params)

    answer = generate_answer(question, top=top, search_fields=search_fields, filter_expr=filter_expr)
    return jsonify({"question": question, "answer": answer, "filters": filter_expr})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
