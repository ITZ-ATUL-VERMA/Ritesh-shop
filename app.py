from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pymongo
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
import os
import certifi
import uvicorn
from contextlib import asynccontextmanager

db = None
users_col = None
items_col = None
sold_col = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, users_col, items_col, sold_col
    try:
        MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://atulverma73077_db_user:eaRbkkjVagEPVjLy@cluster2.iapf8i3.mongodb.net/?appName=Cluster2")
        client = pymongo.MongoClient(MONGO_URL, tlsCAFile=certifi.where())
        db = client["mourya_furniture"]
        users_col = db["users"]
        items_col = db["items"]
        sold_col = db["sold_items"]
        if not users_col.find_one({"email": "admin@gmail.com"}):
            users_col.insert_one({"email": "admin@gmail.com", "password": generate_password_hash("ritesh123"), "role": "owner"})
    except Exception as e:
        print(f"ERROR: {e}")
    yield 

app = FastAPI(title="Shop Management Backend", lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
def read_root():
    return "<html><body style='text-align:center; padding:50px;'><h1>Ritesh Shop Server is Live 🟢</h1></body></html>"

class LoginRequest(BaseModel): email: str; password: str
class ItemRequest(BaseModel): name: str; company: str; price: float; quantity: int
class SellRequest(BaseModel): item_id: str; quantity: int; price: float; customer: str; invoice_id: str = None

@app.post("/api/login")
def login(data: LoginRequest):
    user = users_col.find_one({"email": data.email})
    if user and check_password_hash(user["password"], data.password): return {"status": "success"}
    raise HTTPException(status_code=401, detail="Galat Email ya Password!")

@app.get("/api/items")
def get_items():
    items = list(items_col.find())
    for item in items: item["_id"] = str(item["_id"])
    return {"items": items}

@app.post("/api/items")
def add_item(data: ItemRequest):
    existing = items_col.find_one({"name": data.name, "company": data.company})
    if existing:
        items_col.update_one({"_id": existing["_id"]}, {"$inc": {"quantity": data.quantity}, "$set": {"price": data.price}})
    else:
        items_col.insert_one(data.model_dump())
    return {"status": "success"}

@app.post("/api/sell")
def sell_item(data: SellRequest):
    from bson.objectid import ObjectId
    itm = items_col.find_one({"_id": ObjectId(data.item_id)})
    if not itm: raise HTTPException(status_code=404, detail="Item nahi mila")
    if itm["quantity"] < data.quantity: raise HTTPException(status_code=400, detail="Stock kam hai!")
    
    nq = itm["quantity"] - data.quantity
    if nq > 0: items_col.update_one({"_id": itm["_id"]}, {"$set": {"quantity": nq}})
    else: items_col.delete_one({"_id": itm["_id"]})

    inv = data.invoice_id or str(uuid.uuid4())[:8].upper()
    now = datetime.now()
    sold_col.insert_one({
        "invoice_id": inv, "name": itm["name"], "company": itm["company"], 
        "quantity_sold": data.quantity, "price": data.price, "total": data.quantity * data.price, 
        "customer": data.customer or "Unknown", "date": now.strftime("%A, %d-%m-%Y | %I:%M %p"), "timestamp": now.timestamp()
    })
    return {"status": "success", "invoice_id": inv}

@app.get("/api/history")
def get_history():
    history = list(sold_col.find().sort("timestamp", -1))
    for s in history: s["_id"] = str(s["_id"])
    return {"history": history}

@app.get("/api/receipt/{invoice_id}")
def get_receipt(invoice_id: str):
    b_items = list(sold_col.find({"invoice_id": invoice_id}))
    for i in b_items: i["_id"] = str(i["_id"])
    return {"items": b_items}

# --- NAYA DELETE ENDPOINT ADD KIYA GAYA HAI ---
@app.delete("/api/history/{record_id}")
def delete_history(record_id: str):
    from bson.objectid import ObjectId
    try:
        sold_col.delete_one({"_id": ObjectId(record_id)})
        return {"status": "success"}
    except Exception:
        raise HTTPException(status_code=400, detail="Error deleting record")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=10000)
