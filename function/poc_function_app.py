import logging
import azure.functions as func
import openai
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import json

# Configs
AZURE_OPENAI_KEY = "6opq3dVom794ZZWcn1qflev786NF1o81LffwRhwWNWKHteoXKGwFJQQJ99BHACrIdLPXJ3w3AAABACOGNK8i"
AZURE_OPENAI_ENDPOINT = "https://jeliv-tender-oai-dev-sn.openai.azure.com/"
AZURE_OPENAI_API_VERSION = "2024-04-09"  # Correct format
AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4"

SEARCH_ENDPOINT = "https://jeliv-poc-ais-dev-sn.search.windows.net"
SEARCH_KEY = "OJYtmoCAxBgIhNIXaMOyO6izzYHHnud5swVZe7XiQnAzSeCJXa3"
SEARCH_INDEX_NAME = "jeliv-gold-tenders-rag-indexer"

# Query Azure Cognitive Search
def query_search(query: str) -> str:
    client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    results = client.search(query, top=5)
    passages = [doc.get("content", "") for doc in results]
    return "\n\n".join(passages)

# Generate answer using Azure OpenAI
def generate_answer(user_query: str) -> str:
    context = query_search(user_query)
    prompt = f"""Answer the question based on the context below:
    
Context:
{context}

Question: {user_query}"""

    openai.api_type = "azure"
    openai.api_base = AZURE_OPENAI_ENDPOINT
    openai.api_key = AZURE_OPENAI_KEY
    openai.api_version = AZURE_OPENAI_API_VERSION

    response = openai.ChatCompletion.create(
        engine=AZURE_OPENAI_DEPLOYMENT_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    return response["choices"][0]["message"]["content"]

# Azure Function entry point
app = func.FunctionApp()

@app.function_name(name="HttpTriggerRagFunction")
@app.route(route="rag", auth_level=func.AuthLevel.ANONYMOUS)
def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("RAG Azure Function triggered.")

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            mimetype="application/json",
            status_code=400
        )

    user_query = req_body.get("query")
    if not user_query:
        return func.HttpResponse(
            json.dumps({"error": "Missing 'query' field"}),
            mimetype="application/json",
            status_code=400
        )

    try:
        answer = generate_answer(user_query)
        return func.HttpResponse(
            json.dumps({"answer": answer}),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        logging.exception("Error generating answer.")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500
        )
