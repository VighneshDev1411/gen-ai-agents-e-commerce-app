# main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pymongo import MongoClient
from agent import agent  # importing the initialized LangChain agent
import json

app = FastAPI()

# CORS settings to allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the expected structure for cart items
class CartItem(BaseModel):
    name: str
    category: str  # corresponds to 'Type' in MongoDB
    price: float
    rating: float

@app.post("/suggest-alternatives")
async def suggest_alternatives(cart: list[CartItem]):
    try:
        # Convert to list of dicts
        cart_dicts = [item.dict() for item in cart]
        
        # Debug: Print input from FastAPI
        print(f"Received cart items: {cart_dicts}")
        
        # Create input in the simplest format
        input_json = json.dumps(cart_dicts)
        
        # Debug: Print what we're sending to the agent
        print(f"Sending to agent: {input_json}")
        
        # Call the agent
        result = agent.run(input=input_json)
        
        # Debug: Print raw result
        print(f"Raw result from agent: {result}")
        
        # Parse and return the result
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"result": result}

    except Exception as e:
        print(f"Endpoint error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "details": str(e)}
        )
    
@app.get("/validate-mongodb")
async def validate_mongodb():
    """Endpoint to validate MongoDB data quality"""
    try:
        client = MongoClient(os.getenv("MONGODB_URI"))
        db = client[os.getenv("DB_NAME")]
        collection = db["all_products"]
        
        # Check for documents with null/empty names
        null_names = collection.count_documents({"name": {"$in": [None, ""]}})
        
        # Check for documents with invalid prices
        invalid_prices = collection.count_documents({
            "$or": [
                {"price": {"$exists": False}},
                {"price": {"$lte": 0}},
                {"price": {"$type": "string"}}
            ]
        })
        
        # Get sample of problematic documents
        sample_problems = list(collection.find({
            "$or": [
                {"name": {"$in": [None, ""]}},
                {"price": {"$lte": 0}},
                {"category": {"$exists": False}}
            ]
        }).limit(5))
        
        return {
            "total_products": collection.count_documents({}),
            "products_with_null_names": null_names,
            "products_with_invalid_prices": invalid_prices,
            "sample_problems": sample_problems
        }
    except Exception as e:
        return {"error": str(e)}