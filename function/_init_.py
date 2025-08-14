import azure.functions as func
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import openai

# Azure OpenAI and Search configs
AZURE_OPENAI_KEY = "<your-key>"
AZURE_OPENAI_ENDPOINT = "<your-endpoint>"
AZURE_OPENAI_API_VERSION = "turbo-2024-04-09"
AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4"

SEARCH_ENDPOINT = "<your-search-endpoint>"
SEARCH_KEY = "<your-search-key>"
SEARCH_INDEX_NAME = "<your-index>"

def build_filter_expression(params):
    filters = []
    for key, value in params.items():
        if value:
            filters.append(f"{key} eq '{value}'")
    return " and ".join(filters) if filters else None

def query_azure_search(query, top=5, search_fields=None, filter_expr=None):
    client = SearchClient(endpoint=SEARCH_ENDPOINT,
                          index_name=SEARCH_INDEX_NAME,
                          credential=AzureKeyCredential(SEARCH_KEY))
    search_kwargs = {"top": top}
    if search_fields:
        if isinstance(search_fields, str):
            search_fields = [f.strip() for f in search_fields.split(",")]
        search_kwargs["search_fields"] = search_fields
    if filter_expr:
        search_kwargs["filter"] = filter_expr
    results = client.search(query, **search_kwargs)
    return "\n\n".join([r.get("content", "") for r in results])

def generate_answer(question, top=5, search_fields=None, filter_expr=None):
    context = query_azure_search(question, top, search_fields, filter_expr)
    prompt = f"Answer based on context:\n\n{context}\n\nQuestion: {question}"

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
        return func.HttpResponse("Invalid JSON", status_code=400)

    question = data.get("question")
    if not question:
        return func.HttpResponse("Missing 'question' field", status_code=400)

    filter_params = {
        "tender_number": data.get("tender_number"),
        "document_type": data.get("document_type"),
        "metadata_storage_name": data.get("metadata_storage_name"),
        "metadata_storage_path": data.get("metadata_storage_path"),
        "metadata_storage_last_modified": data.get("metadata_storage_last_modified")
    }
    filter_expr = build_filter_expression(filter_params)

    answer = generate_answer(question, filter_expr=filter_expr)
    return func.HttpResponse(
        body=f'{{"question":"{question}", "answer":"{answer}", "filters":"{filter_expr}"}}',
        mimetype="application/json"
    )

