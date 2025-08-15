import logging
import json
import azure.functions as func
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import openai

# ---------------- CONFIGURATION ----------------
AZURE_OPENAI_KEY = "6opq3dVom794ZZWcn1qflev786NF1o81LffwRhwWNWKHteoXKGwFJQQJ99BHACrIdLPXJ3w3AAABACOGNK8i"
AZURE_OPENAI_ENDPOINT = "https://jeliv-tender-oai-dev-sn.openai.azure.com/"
AZURE_OPENAI_API_VERSION = "2024-04-09"
AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4"

SEARCH_ENDPOINT = "https://jeliv-poc-ais-dev-sn.search.windows.net"
SEARCH_KEY = "OJYtmoCAxBgIhNIXaMOyO6izzYHHnud5swVZe7XiQnAzSeCJXa3"
SEARCH_INDEX_NAME = "jeliv-gold-tenders-rag-indexer"

# ---------------- OPENAI CONFIG ----------------
openai.api_type = "azure"
openai.api_key = AZURE_OPENAI_KEY
openai.api_base = AZURE_OPENAI_ENDPOINT
openai.api_version = AZURE_OPENAI_API_VERSION

# ---------------- SEARCH CLIENT ----------------
search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=SEARCH_INDEX_NAME,
    credential=AzureKeyCredential(SEARCH_KEY)
)

# ---------------- AZURE FUNCTION ENTRY ----------------
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.function_name(name="chat_with_ai")
@app.route(route="chat")  # POST https://<functionapp>.azurewebsites.net/api/chat
def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing AI chat request...")

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON payload."}),
            status_code=400,
            mimetype="application/json"
        )

    query = req_body.get("query")
    if not query:
        return func.HttpResponse(
            json.dumps({"error": "Missing 'query' field."}),
            status_code=400,
            mimetype="application/json"
        )

    # ---------------- BUILD FILTERS ----------------
    params = req_body
    filters = []

    if params.get("tender_number"):
        filters.append(f"tender_number eq '{params['tender_number']}'")
    if params.get("document_type"):
        filters.append(f"document_type eq '{params['document_type']}'")
    if params.get("metadata_storage_name"):
        filters.append(f"metadata_storage_name eq '{params['metadata_storage_name']}'")
    if params.get("metadata_storage_path"):
        filters.append(f"metadata_storage_path eq '{params['metadata_storage_path']}'")
    if params.get("metadata_storage_last_modified"):
        filters.append(f"metadata_storage_last_modified eq {params['metadata_storage_last_modified']}")
    if params.get("procuring_entity"):
        filters.append(f"procuring_entity eq '{params['procuring_entity']}'")
    if params.get("description"):
        filters.append(f"description eq '{params['description']}'")
    if params.get("closing_date"):
        filters.append(f"closing_date eq {params['closing_date']}")

    filter_expr = " and ".join(filters) if filters else None

    # ---------------- SEARCH AZURE ----------------
    try:
        search_kwargs = {"top": 5}
        if filter_expr:
            search_kwargs["filter"] = filter_expr

        results = search_client.search(query, **search_kwargs)
        docs = [doc for doc in results]
        context_text = "\n".join([json.dumps(doc, indent=2) for doc in docs])
    except Exception as e:
        logging.error(f"Error querying Azure Search: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Azure Search error: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )

    # ---------------- CALL OPENAI ----------------
    try:
        completion = openai.ChatCompletion.create(
            engine=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers using search results."},
                {"role": "user", "content": f"Answer the following based on the context:\n\nContext: {context_text}\n\nQuestion: {query}"}
            ],
            max_tokens=500
        )
        answer = completion.choices[0].message["content"]
    except Exception as e:
        logging.error(f"Error calling OpenAI: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"OpenAI error: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )

    return func.HttpResponse(
        json.dumps({"query": query, "filters": filter_expr, "answer": answer}),
        status_code=200,
        mimetype="application/json"
    )

