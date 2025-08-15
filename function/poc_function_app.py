import logging
import json
import azure.functions as func
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import openai

# ---------------- CONFIGURATION ----------------
AZURE_OPENAI_KEY = "6opq3dVom794ZZWcn1qflev786NF1o81LffwRhwWNWKHteoXKGwFJQQJ99BHACrIdLPXJ3w3AAABACOGNK8i"
AZURE_OPENAI_ENDPOINT = "https://jeliv-tender-oai-dev-sn.openai.azure.com/"
AZURE_OPENAI_API_VERSION = "2024-04-09"  # Correct format
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
@app.route(route="chat")  # e.g., POST https://<functionapp>.azurewebsites.net/api/chat
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

    try:
        # Step 1: Search in Azure Cognitive Search
        search_results = search_client.search(query, top=3)
        docs = [doc for doc in search_results]
        context_text = "\n".join([json.dumps(doc, indent=2) for doc in docs])

        # Step 2: Call Azure OpenAI
        completion = openai.ChatCompletion.create(
            engine=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers using search results."},
                {"role": "user", "content": f"Answer the following based on the context:\n\nContext: {context_text}\n\nQuestion: {query}"}
            ],
            max_tokens=500
        )

        answer = completion.choices[0].message["content"]

        return func.HttpResponse(
            json.dumps({"query": query, "answer": answer}),
            mimetype="application/json",
            status_code=200
        )

    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500
        )
