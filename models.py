from pydantic import BaseModel

# BaseModel basically helps FastAPI validate incoming JSON and defines the expected format for each cart item.

class CartItem(BaseModel):
    name:str
    price:float
    rating:float
    category:str

