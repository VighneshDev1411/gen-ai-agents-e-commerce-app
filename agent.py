from langchain.agents import initialize_agent
from langchain_openai import ChatOpenAI
from langchain.agents.agent_types import AgentType
from dotenv import load_dotenv
from pymongo import MongoClient
from langchain.tools import Tool
import os
import json

load_dotenv()  


def suggest_cheaper_alternatives(cart_input: str) -> str:
    try:
        # Parse input
        try:
            cart = json.loads(cart_input)
            if isinstance(cart, dict) and 'cart_json' in cart:
                cart = cart['cart_json']
            if not isinstance(cart, list):
                return json.dumps({"error": "Input must be an array of cart items"})
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON input format"})

        # MongoDB connection
        client = MongoClient(os.getenv("MONGODB_URI"))
        db = client[os.getenv("DB_NAME")]
        collection = db["all_products"]

        suggestions = []

        for item in cart:
            try:
                # Extract and validate fields
                name = str(item.get("name", "")).strip()
                category = str(item.get("category", "")).strip()
                price = float(item.get("price", 0))
                rating = float(item.get("rating", 0))  # Note: Your DB uses 'rating'

                if not all([name, category, price > 0]):
                    continue

                # MongoDB query
                query = {
                    "category": category,
                    "price": {"$lt": price},
                    "rating": {"$gte": max(rating - 0.5, 0)},  # Ensure rating doesn't go negative
                    "name": {"$exists": True, "$ne": None}
                }

                # Debug print the query
                print(f"Querying MongoDB with: {query}")

                cheaper = list(collection.find(query).sort("price", 1).limit(2))

                # Debug print results
                print(f"Found {len(cheaper)} alternatives for {name}")

                for product in cheaper:
                    try:
                        product_name = str(product["name"]).strip()
                        product_price = float(product["price"])
                        product_rating = float(product["rating"])

                        suggestions.append({
                            "original": name,
                            "suggestion": product_name,
                            "original_price": price,
                            "suggested_price": product_price,
                            "original_rating": rating,
                            "suggested_rating": product_rating,
                            "savings": round(price - product_price, 2),
                            "brand": product.get("brand", "Unknown")
                        })
                    except Exception as e:
                        print(f"Error formatting product {product.get('_id')}: {str(e)}")
                        continue

            except Exception as e:
                print(f"Error processing cart item {item.get('name')}: {str(e)}")
                continue

        if not suggestions:
            return json.dumps({"message": "No cheaper alternatives found matching all criteria."})

        return json.dumps({
            "success": True,
            "suggestions": suggestions,
            "count": len(suggestions)
        })

    except Exception as e:
        print(f"Critical error: {str(e)}")
        return json.dumps({
            "success": False,
            "error": "Internal server error",
            "details": str(e)
        })
# 🛠️ Define this function as a LangChain tool
tools = [
    Tool.from_function(
        name="SuggestCheaperAlternatives",
        func=suggest_cheaper_alternatives,
        description="Suggests cheaper supplement alternatives with similar ratings. Input must be a JSON string of cart items."
    )
]

# 💬 Use OpenAI Chat model (replace with GPT-4 if you prefer)
llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)

# 🧠 Create the agent using LangChain
agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)


test_input = {
    "cart_json": [{
        "name": "Premium Whey Protein",
        "category": "Whey Isolate",
        "price": 40.0,
        "rating": 4.5
    }]
}
result = suggest_cheaper_alternatives(json.dumps(test_input))
print(result)