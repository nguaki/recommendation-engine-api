import asyncio
import os
from typing import List, Dict
from fastapi import FastAPI, Query, HTTPException, Security, Depends, status, Request, Header
from fastapi.security.api_key import APIKeyHeader
from google.cloud import firestore
from cachetools import TTLCache
import time 

# --- 1. ARCHITECT'S INFRASTRUCTURE ---
app = FastAPI(title="SmartRecs Ultra-Low Latency API")

# Use ADC (Application Default Credentials) set up via gcloud auth
db = firestore.AsyncClient(project="recommendation-machine-f393e")

# CACHE: Store API keys in RAM for 1 hour to eliminate DB round-trips for Auth
# Key: StoreName (e.g., "ABC"), Value: {api_key: "...", status: "active"}
auth_cache = TTLCache(maxsize=5000, ttl=3600)

# NEW: Cache for Model Data (5 minutes)
# We cache the actual recommendation results for high-traffic items
model_cache = TTLCache(maxsize=10000, ttl=300) 

SYSTEM_DOMAINS = ["localhost", "127.0.0.1", "smartrecshub.com", "www.smartrecshub.com"]

#api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

api_key_header = APIKeyHeader(
    name="X-API-KEY", 
    auto_error=False,
    description="Enter your SmartRecs API Key (e.g., sr_live_777)"
)

# --- 1. TRIPLE CACHE INFRASTRUCTURE ---
# Cache 1: API_KEY -> {store_name, online_url, status} (1hr)
identity_cache = TTLCache(maxsize=10000, ttl=3600)

# Cache 2: Full Item ID (e.g., ABC#coke) -> Rec Model (10min)
model_cache = TTLCache(maxsize=20000, ttl=600)

# --- 2. THE IDENTITY & SECURITY GATE ---
async def verify_access(
    request: Request, 
    x_api_key: str = Security(api_key_header), 
    referer: str = Header(None)
):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-KEY missing")

    # A. Point Lookup for Identity (Cache-First)
    identity = identity_cache.get(x_api_key)
    
    if not identity:
        # Direct O(1) fetch using the API Key as the Doc ID
        doc = await db.collection("api_id2store").document(x_api_key).get()
        
        if not doc.exists:
            raise HTTPException(status_code=403, detail="Invalid API Key")
        
        identity = doc.to_dict()
        identity_cache[x_api_key] = identity # Map to RAM

    # B. Enforcement: Subscription Status
    if identity.get("status") != "active":
        raise HTTPException(status_code=402, detail="Subscription inactive")

    # C. Enforcement: Domain Origin Verification
    # We allow 'localhost' for your development and testing
    actual_referer = referer or request.headers.get("referer", "localhost")
    authorized_site = identity.get("online_url", "")

    is_system = any(domain in actual_referer for domain in SYSTEM_DOMAINS)
    is_client = authorized_site in actual_referer if authorized_site else False

    if not (is_system or is_client):
        raise HTTPException(
            status_code=403, 
            detail=f"Domain unauthorized. Origin: {actual_referer}"
        )
        
    # Return the store name for list reconstruction
    return identity.get("store_name")

# --- 3. THE RECONSTRUCTION ENGINE ---
@app.get("/recommend")
async def recommend(
    items: List[str] = Query(...), 
    store_name: str = Depends(verify_access)
):
    start_time = time.perf_counter()

    # THE MAPPING TRANSFORMATION: Simple ID -> Internal Keyed ID
    # Example: ['coke'] -> ['ABC#coke']
    internal_keys = [f"{store_name}#{item}" for item in items]

    async def fetch_doc(internal_key):
        cached = model_cache.get(internal_key)
        if cached: return cached
        
        doc = await db.collection("models").document(internal_key).get()
        if doc.exists:
            data = doc.to_dict()
            model_cache[internal_key] = data
            return data
        return None

    # Execute Parallel O(1) Lookups
    results = await asyncio.gather(*[fetch_doc(k) for k in internal_keys])
    










    # ... Same Merging & Sorting Logic as before ...
    # (Filtering logic now checks against the original 'items' list)
    


 # 2. Aggregation Logic
    #input_names = [i.split("#")[1] for i in items if "#" in i]
    input_names = set(items)
    
    merged: Dict[str, float] = {}

    for model in results:
        if not model: continue
        
        # Pull top 5 co-purchases (Already sorted by coefficient in DB)
        for i in range(1, 6):
            name = model.get(f"co_purchase{i}")
            score = model.get(f"co_purchase{i}_coeff")
            
            if name and score:
                if name in input_names: continue # Don't recommend what's already in hand
                
                # Deduplicate: Keep highest score
                if name in merged:
                    if score > merged[name]: merged[name] = score
                else:
                    merged[name] = score

    # 3. Final Sort
    recommendations = sorted(merged.items(), key=lambda x: x[1], reverse=True)

    # Calculate execution time in milliseconds
    latency_ms = (time.perf_counter() - start_time) * 1000 

    return {
        "store": store_name,
        "latency_ms": round(latency_ms, 2), # Return the key metric
        "recommendations": [{"item": k, "score": v} for k, v in recommendations]
    }



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)