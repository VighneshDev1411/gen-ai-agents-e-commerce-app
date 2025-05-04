from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from agents import ask_rag, suggest_alternatives
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CartItem(BaseModel):
    name: str
    category: str
    price: float
    rating: float

class AskQuery(BaseModel):
    question: str

@app.post("/suggest-alternatives")
async def suggest_alternatives_endpoint(cart: list[CartItem]):
    try:
        cart_dicts = [item.dict() for item in cart]
        result = suggest_alternatives(json.dumps(cart_dicts))
        return json.loads(result)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.post("/ask")
async def ask_agent(query: AskQuery):
    try:
        return ask_rag(query.question)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )