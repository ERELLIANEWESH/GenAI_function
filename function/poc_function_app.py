import openai
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import azure.functions as func

# Configs
AZURE_OPENAI_KEY = "6opq3dVom794ZZWcn1qflev786NF1o81LffwRhwWNWKHteoXKGwFJQQJ99BHACrIdLPXJ3w3AAABACOGNK8i"
AZURE_OPENAI_ENDPOINT = "https://jeliv-tender-oai-dev-sn.openai.azure.com/"
AZURE_OPENAI_API_VERSION = "2024-04-09"
AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4"

SEARCH_ENDPOINT = "https://jeliv-poc-ais-dev-sn.search.windows.net"
SEARCH_KEY = "OJYtmoCAxBgIhNIXaMOyO6izzYHHnud5swVZe7XiQnAzSeCJXa3"
SEARCH_INDEX_NAME = "jeliv-gold-tenders-rag-indexer"

# Query Azure Cognitive Search
def query_search(query):
    client = SearchClient(endpoint=SEARCH_ENDPOINT,
                          index_name=SEARCH_INDEX_NAME,
                          credential=AzureKeyCredential(SEARCH_KEY))
    results = client.search(query, top=5)
    passages = []
    for result in results:
        passages.append(result["content"])
    return "\n\n".join(passages)

# Generate answer using Azure OpenAI
def generate_answer(user_query):
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

# Azure Function HTTP Trigger
def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        user_query = req.params.get('q')
        if not user_query:
            return func.HttpResponse(
                "Please pass a 'q' parameter in the query string",
                status_code=400
            )

        answer = generate_answer(user_query)
        return func.HttpResponse(answer, status_code=200)

    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )
