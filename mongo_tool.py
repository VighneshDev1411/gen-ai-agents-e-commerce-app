from pymongo import MongoClient
from typing import List, Dict
import os
from dotenv import load_dotenv


load_dotenv()

client = MongoClient(os.getenv("MONGODB_URI"))
db = client["VOLT_DB"]
collection = db["all_products"]

def query_cheaper_alternatives(category: str, max_price:float, min_rating: float) -> List[Dict]:
    """
    This function queries MongoDB for cheaper products in the same category.
    - category: the product type (e.g., "Whey Protein")
    - max_price: we want cheaper products below this price
    - min_rating: we want products with rating >= this
    """
    results = list(collection.find({
        "category": category,
        "price": {"$lt": max_price},
        "rating": {"$gte", min_rating}
    }).sort("price", 1).limit(3))

    return [
        {
            "name": p["name"],
            "price": p["price"],
            "rating": p["rating"]
        }
        for p in results
    ]