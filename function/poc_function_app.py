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

@app.function_name(name="function")
@app.route(route="function")
def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing tender search request...")

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
    filters = []
    filter_fields = [
        "tender_number",
        "document_type",
        "procuring_entity",
        "description",
        "closing_date"
    ]

    for field in filter_fields:
        if req_body.get(field):
            value = req_body[field]
            if field in ["closing_date"]:
                filters.append(f"{field} eq {value}")
            else:
                filters.append(f"{field} eq '{value}'")

    filter_expr = " and ".join(filters) if filters else None

    # ---------------- SEARCH AZURE ----------------
    try:
        search_kwargs = {"top": 5}
        if filter_expr:
            search_kwargs["filter"] = filter_expr

        results = search_client.search(search_text=query, **search_kwargs)
        tenders = []
        for doc in results:
            tenders.append({
                "tender_number": doc.get("tender_number"),
                "procuring_entity": doc.get("procuring_entity"),
                "description": doc.get("description"),
                "closing_date": doc.get("closing_date")
            })
    except Exception as e:
        logging.error(f"Error querying Azure Search: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Azure Search error: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )

    # If no tenders found
    if not tenders:
        return func.HttpResponse(
            json.dumps({"query": query, "filters": filter_expr, "answer": "No tenders found matching your query."}),
            status_code=200,
            mimetype="application/json"
        )

    # ---------------- CALL OPENAI ----------------
    try:
        context_text = "\n".join([
            f"Tender Number: {t['tender_number']}, Procuring Entity: {t['procuring_entity']}, Description: {t['description']}, Closing Date: {t['closing_date']}"
            for t in tenders
        ])

        completion = openai.ChatCompletion.create(
            engine=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant summarizing tender search results."},
                {"role": "user", "content": f"Based on the following tenders, summarize the key results:\n\n{context_text}\n\nQuestion: {query}"}
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

    # ---------------- RETURN RESPONSE ----------------
    return func.HttpResponse(
        json.dumps({
            "query": query,
            "filters": filter_expr,
            "tenders": tenders,
            "answer": answer
        }, indent=2),
        status_code=200,
        mimetype="application/json"
    )





