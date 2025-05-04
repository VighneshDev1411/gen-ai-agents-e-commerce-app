from langchain.agents import initialize_agent
from langchain_openai import ChatOpenAI
from langchain.agents.agent_types import AgentType
from langchain.document_loaders import MongodbLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.tools import Tool
from langchain.schema import Document
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import json

load_dotenv()

# ========== RAG Agent Components ==========
def load_product_data():
    """Load product data from MongoDB and format as documents"""
    client = MongoClient(os.getenv("MONGODB_URI"))
    db = client["VOLT_DB"]
    collection = db["all_products"]
    documents = []

    for product in collection.find():
        page_content = f"""
        Product: {product.get('name', 'N/A')}
        Brand: {product.get('brand', 'N/A')}
        Category: {product.get('category', 'N/A')}
        Description: {product.get('description', 'No description available')}
        Benefits: {', '.join(product.get('tags', []))}
        Suitable for: {product.get('suitable_for', 'N/A')}
        Goals: {product.get('goal', 'N/A')}
        Dietary: {product.get('diet_type', 'N/A')}
        """
        metadata = {
            "product_id": str(product.get("_id", "")),
            "name": product.get("name", "N/A"),
            "brand": product.get("brand", "N/A"),
            "category": product.get("category", "N/A"),
            "price": product.get("price", 0),
            "rating": product.get("rating", 0),
            "diet_type": product.get("diet_type", "N/A"),
            "goal": product.get("goal", "N/A"),
            "suitable_for": product.get("suitable_for", "N/A"),
            "tags": ", ".join(product.get("tags", []))
        }
        documents.append(Document(page_content=page_content, metadata=metadata))
    return documents

def process_documents(documents):
    """Split documents into chunks"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    return text_splitter.split_documents(documents)

def create_vector_store(chunks):
    """Create and persist Chroma vector store"""
    embeddings = OpenAIEmbeddings(
        model="text-embedding-ada-002",
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory="./chroma_db"
    )
    vector_store.persist()
    return vector_store

def setup_rag_chain(vector_store):
    """Initialize RAG chain"""
    llm = ChatOpenAI(
        model_name="gpt-3.5-turbo",
        temperature=0.7,
        max_tokens=1000
    )
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4}
    )
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True
    )

def query_rag_system(rag_chain, query):
    """Query the RAG system and format results with deduplicated sources"""
    result = rag_chain({"query": query})
    response = {
        "answer": result["result"],
        "sources": []
    }

    seen_ids = set()
    for doc in result["source_documents"]:
        product_id = doc.metadata.get("product_id")
        if product_id not in seen_ids:
            seen_ids.add(product_id)
            source_info = {
                "product_name": doc.metadata.get("name", "N/A"),
                "brand": doc.metadata.get("brand", "N/A"),
                "price": f"${doc.metadata.get('price', 'N/A')}",
                "rating": doc.metadata.get("rating", "N/A"),
                "diet_type": doc.metadata.get("diet_type", "N/A"),
                "goals": doc.metadata.get("goal", "N/A"),
                "tags": doc.metadata.get("tags", "N/A")
            }
            response["sources"].append(source_info)

    return response

# ========== Suggestion Agent Components ==========
def suggest_cheaper_alternatives(cart_input: str) -> str:
    """Find cheaper alternatives for cart items"""
    try:
        cart = json.loads(cart_input)
        if isinstance(cart, dict) and 'cart_json' in cart:
            cart = cart['cart_json']
        if not isinstance(cart, list):
            return json.dumps({"error": "Input must be an array of cart items"})

        client = MongoClient(os.getenv("MONGODB_URI"))
        db = client[os.getenv("DB_NAME")]
        collection = db["all_products"]
        suggestions = []

        for item in cart:
            name = str(item.get("name", "")).strip()
            category = str(item.get("category", "")).strip()
            price = float(item.get("price", 0))
            rating = float(item.get("rating", 0))

            if not all([name, category, price > 0]):
                continue

            query = {
                "category": category,
                "price": {"$lt": price},
                "rating": {"$gte": max(rating - 0.5, 0)},
                "name": {"$exists": True, "$ne": None}
            }

            cheaper = list(collection.find(query).sort("price", 1).limit(2))

            for product in cheaper:
                suggestions.append({
                    "original": name,
                    "suggestion": str(product["name"]).strip(),
                    "original_price": price,
                    "suggested_price": float(product["price"]),
                    "original_rating": rating,
                    "suggested_rating": float(product["rating"]),
                    "savings": round(price - float(product["price"]), 2),
                    "brand": product.get("brand", "Unknown")
                })

        return json.dumps({
            "success": True,
            "suggestions": suggestions,
            "count": len(suggestions)
        }) if suggestions else json.dumps({"message": "No cheaper alternatives found"})

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

# ========== Initialize Agents ==========
# Initialize RAG components (called once at startup)
product_docs = load_product_data()
document_chunks = process_documents(product_docs)
vector_store = create_vector_store(document_chunks)
rag_chain = setup_rag_chain(vector_store)

# Initialize suggestion agent
suggestion_tools = [
    Tool.from_function(
        name="SuggestCheaperAlternatives",
        func=suggest_cheaper_alternatives,
        description="Suggests cheaper supplement alternatives with similar ratings"
    )
]
suggestion_agent = initialize_agent(
    tools=suggestion_tools,
    llm=ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0),
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# ========== Public API ==========
def ask_rag(query: str):
    """Public interface for RAG queries"""
    return query_rag_system(rag_chain, query)

def suggest_alternatives(cart_input: str):
    """Public interface for suggestion agent"""
    return suggest_cheaper_alternatives(cart_input)