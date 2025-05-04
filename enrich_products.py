import pandas as pd
import numpy as np
from pymongo import MongoClient

# Load the CSV file into a DataFrame
csv_file_path = 'VOLT_DB.all_products.csv'
df = pd.read_csv(csv_file_path)

# Replace NaN values in 'category' and 'name' with an empty string to avoid TypeError
df['category'] = df['category'].fillna('').astype(str)
df['name'] = df['name'].fillna('').astype(str)

# MongoDB connection setup (modify with your connection details)
client = MongoClient('mongodb+srv://vignesh_dev:JZL7rlOXai0QbWQd@vitalfuel.3vwxsut.mongodb.net/?retryWrites=true&w=majority&appName=VitalFuel')  # Change to your MongoDB URI
db = client['VOLT_DB']
collection = db['all_products']

# Function to enrich product data
def enrich_product(row):
    # Add goal, diet_type, suitable_for, and tags based on category and product features
    if 'Whey' in row['category']:
        goal = 'muscle gain'
        diet_type = 'keto-friendly'
        suitable_for = 'athletes, bodybuilders'
        tags = ['high protein', 'muscle gain', 'keto', 'whey protein']
    elif 'Biotin' in row['name']:
        goal = 'hair and skin health'
        diet_type = 'vegetarian'
        suitable_for = 'women, elderly'
        tags = ['hair growth', 'collagen', 'skin health', 'biotin']
    else:
        goal = 'general health'
        diet_type = 'vegan'
        suitable_for = 'everyone'
        tags = ['health', 'supplement', 'nutrition']
    
    # Generate product description
    description = f"{row['name']} by {row['brand']} is a {goal} supplement. It contains {row['protein_per_serving']} of protein per serving, ideal for those looking to improve their {goal}. It's {diet_type}, and suitable for {suitable_for}."
    
    # Generate embedding text
    embedding_text = f"{row['name']} by {row['brand']} is a {diet_type} supplement that helps with {goal}. It contains {row['protein_per_serving']} of protein per serving and is perfect for {suitable_for}."
    
    return {
        "image": row['image'],
        "name": row['name'],
        "brand": row['brand'],
        "category": row['category'],
        "size": row['size'],
        "protein_per_serving": row['protein_per_serving'],
        "rating": row['rating'],
        "price": row['price'],
        "discount": row['discount'],
        "goal": goal,
        "diet_type": diet_type,
        "suitable_for": suitable_for,
        "tags": tags,
        "description": description,
        "embedding_text": embedding_text
    }

# Apply the enrichment function to all products
enriched_products = df.apply(enrich_product, axis=1)

# Convert to list of dictionaries
enriched_products_list = enriched_products.tolist()

# Update MongoDB with enriched products (optional)
# You can either insert new documents or update existing ones
for product in enriched_products_list:
    # If the product already exists in the database, update it, otherwise insert it
    collection.update_one(
        {"name": product["name"], "brand": product["brand"]}, 
        {"$set": product}, 
        upsert=True
    )

# Print out the first 2 enriched products as an example
for i, product in enumerate(enriched_products_list[:2]):
    print(f"Enriched Product {i+1}:")
    print(product)
    print("\n" + "-"*50 + "\n")

print("Enrichment process complete!")
