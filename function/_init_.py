import azure.functions as func
import openai
import json
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

# Configs
AZURE_OPENAI_KEY = "6opq3dVom794ZZWcn1qflev786NF1o81LffwRhwWNWKHteoXKGwFJQQJ99BHACrIdLPXJ3w3AAABACOGNK8i"
AZURE_OPENAI_ENDPOINT = "https://jeliv-tender-oai-dev-sn.openai.azure.com/"
AZURE_OPENAI_API_VERSION = "turbo-2024-04-09"
AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4"

SEARCH_ENDPOINT = "https://jeliv-poc-ais-dev-sn.search.windows.net"
SEARCH_KEY = "OJYtmoCAxBgIhNIXaMOyO6izzYHHnud5swVZe7XiQnAzSeCJXa3"
SEARCH_INDEX_NAME = "jeliv-gold-tenders-rag-indexer"


def build_filter_expression(params: dict) -> str:
    filters = []
    if params.get('tender_number'):
        filters.append(f"tender_number eq '{params['tender_number']}'")
    if params.get('document_type'):
        filters.append(f"document_type eq '{params['document_type']}'")
    if params.get('metadata_storage_name'):
        filters.append(f"metadata_storage_name eq '{params['metadata_storage_name']}'")
    if params.get('metadata_storage_path'):
        filters.append(f"metadata_storage_path eq '{params['metadata_storage_path']}'")
    if params.get('metadata_storage_last_modified'):
        date_val = params['metadata_storage_last_modified']
        filters.append(f"metadata_storage_last_modified eq {date_val}")
    return " and ".join(filters) if filters else None


def query_azure_search(query, top=5, search_fields=None, filter_expr=None):
    client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=SEARCH_INDEX_NAME,
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


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()
    except ValueError:
        return func.HttpResponse(json.dumps({"error": "Invalid JSON"}), status_code=400)

    if not data or "question" not in data:
        return func.HttpResponse(json.dumps({"error": "Please provide 'question'"}), status_code=400)

    question = data["question"]
    top = int(data.get("top", 5))
    search_fields = data.get("search_fields")

    filter_params = {
        "tender_number": data.get("tender_number"),
        "document_type": data.get("document_type"),
        "metadata_storage_name": data.get("metadata_storage_name"),
        "metadata_storage_path": data.get("metadata_storage_path"),
        "metadata_storage_last_modified": data.get("metadata_storage_last_modified"),
    }
    filter_expr = build_filter_expression(filter_params)

    answer = generate_answer(question, top=top, search_fields=search_fields, filter_expr=filter_expr)

    return func.HttpResponse(
        json.dumps({"question": question, "answer": answer, "filters": filter_expr}),
        mimetype="application/json"
    )
