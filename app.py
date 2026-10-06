from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pymongo
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
import os
import certifi
import uvicorn
from contextlib import asynccontextmanager

# Global DB variables
db = None
users_col = None
items_col = None
sold_col = None

# Naya Lifespan method (DeprecationWarning theek karne ke liye)
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, users_col, items_col, sold_col
    try:
        print("MongoDB se connect ho raha hai...")
        # Render Environment Variable se URL lega
        MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://atulverma73077_db_user:eaRbkkjVagEPVjLy@cluster2.iapf8i3.mongodb.net/?appName=Cluster2")
        
        client = pymongo.MongoClient(MONGO_URL, tlsCAFile=certifi.where())
        db = client["mourya_furniture"]
        users_col = db["users"]
        items_col = db["items"]
        sold_col = db["sold_items"]
        
        # Default Admin Setup
        if not users_col.find_one({"email": "admin@gmail.com"}):
            users_col.insert_one({"email": "admin@gmail.com", "password": generate_password_hash("ritesh123"), "role": "owner"})
        print(">>> MongoDB Connected Successfully! <<<")
    except Exception as e:
        print("=========================================")
        print(f"MONGODB CONNECTION ERROR: {e}")
        print("=========================================")
    
    yield # App jab tak chalega yahan pause rahega
    print("Server band ho raha hai...")

# FastAPI app ko naye lifespan ke sath initialize karna
app = FastAPI(title="Shop Management Backend", lifespan=lifespan)

# Models
class LoginRequest(BaseModel):
    email: str
    password: str

class ItemRequest(BaseModel):
    name: str
    company: str
    price: float
    quantity: int

class SellRequest(BaseModel):
    item_id: str
    quantity: int
    price: float
    customer: str
    invoice_id: str = None

# --- API Endpoints ---

@app.post("/api/login")
def login(data: LoginRequest):
    if users_col is None:
        raise HTTPException(status_code=500, detail="Database connection failed")
    user = users_col.find_one({"email": data.email})
    if user and check_password_hash(user["password"], data.password):
        return {"status": "success", "message": "Login successful"}
    raise HTTPException(status_code=401, detail="Galat Email ya Password!")

@app.get("/api/items")
def get_items():
    if items_col is None:
        return {"items": []}
    items = list(items_col.find())
    for item in items:
        item["_id"] = str(item["_id"])
    return {"items": items}

@app.post("/api/items")
def add_item(data: ItemRequest):
    if items_col is None:
        raise HTTPException(status_code=500, detail="Database connection failed")
    existing = items_col.find_one({"name": data.name, "company": data.company})
    if existing:
        items_col.update_one({"_id": existing["_id"]}, {"$inc": {"quantity": data.quantity}, "$set": {"price": data.price}})
    else:
        items_col.insert_one(data.model_dump())
    return {"status": "success", "message": "Item saved successfully"}

@app.post("/api/sell")
def sell_item(data: SellRequest):
    if items_col is None:
        raise HTTPException(status_code=500, detail="Database connection failed")
    from bson.objectid import ObjectId
    itm = items_col.find_one({"_id": ObjectId(data.item_id)})
    if not itm:
        raise HTTPException(status_code=404, detail="Item nahi mila")
    if itm["quantity"] < data.quantity:
        raise HTTPException(status_code=400, detail="Stock kam hai!")

    nq = itm["quantity"] - data.quantity
    if nq > 0:
        items_col.update_one({"_id": itm["_id"]}, {"$set": {"quantity": nq}})
    else:
        items_col.delete_one({"_id": itm["_id"]})

    inv = data.invoice_id or str(uuid.uuid4())[:8].upper()
    now = datetime.now()
    date_str = now.strftime("%A, %d-%m-%Y | %I:%M %p")

    sold_col.insert_one({
        "invoice_id": inv,
        "name": itm["name"],
        "company": itm["company"],
        "quantity_sold": data.quantity,
        "price": data.price,
        "total": data.quantity * data.price,
        "customer": data.customer or "Unknown",
        "date": date_str,
        "timestamp": now.timestamp()
    })

    return {"status": "success", "invoice_id": inv}

@app.get("/api/history")
def get_history():
    if sold_col is None:
        return {"history": []}
    history = list(sold_col.find().sort("timestamp", -1))
    for s in history:
        s["_id"] = str(s["_id"])
    return {"history": history}

@app.get("/api/receipt/{invoice_id}")
def get_receipt(invoice_id: str):
    if sold_col is None:
        return {"items": []}
    b_items = list(sold_col.find({"invoice_id": invoice_id}))
    for i in b_items:
        i["_id"] = str(i["_id"])
    return {"items": b_items}

# Yeh block app ko continuously run karne ke liye zaroori hai
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=10000)
