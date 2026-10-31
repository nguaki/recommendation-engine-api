import asyncio
import os
import time
from typing import List, Dict
from fastapi import FastAPI, Query, HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import firestore
from cachetools import TTLCache

#from fastapi import FastAPI, Query, HTTPException, Security, Depends, status, Request, Header


app = FastAPI(title="SmartRecs Hub - Explicit Architecture")

# --- 1. INFRASTRUCTURE ---
PROJECT_ID = "recommendation-machine-f393e"
db = firestore.AsyncClient(project=PROJECT_ID)

api_key_header = APIKeyHeader(
    name="X-API-KEY", 
    auto_error=False,
    description="Enter your SmartRecs API Key (e.g., sr_live_777)"
)

# Triple Cache remains the same (Memory efficiency is key)
identity_cache = TTLCache(maxsize=10000, ttl=3600)
model_cache = TTLCache(maxsize=20000, ttl=600)

SYSTEM_DOMAINS = ["localhost", "127.0.0.1", "smartrecshub.com", "www.smartrecshub.com", "recommendation-engine-api-1082432876184.us-central1.run.app" ]

# --- 2. THE EXPLICIT GUARD FUNCTION ---
# We removed the FastAPI-specific 'Security' and 'Header' parameters.
# Now we simply pass the standard 'request' object.
async def verify_access_manually(request: Request):
    """
    Standard Python function to verify the request. 
    Explicitly extracts data from the request object.
    """
    # A. Manually extract the API Key from headers
    x_api_key = request.headers.get("X-API-KEY")
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-KEY header missing")

    # B. Identity & Cache Lookup
    identity = identity_cache.get(x_api_key)
    if not identity:
        doc = await db.collection("api_id2store").document(x_api_key).get()
        if not doc.exists:
            raise HTTPException(status_code=403, detail="Invalid API Key")
        identity = doc.to_dict()
        identity_cache[x_api_key] = identity

    # C. Status Check
    if identity.get("status") != "active":
        raise HTTPException(status_code=402, detail="Subscription inactive")


    # Ensure actual_referer is a string to avoid 'in' comparison errors
    
    # D. Domain Verification

    # Extract the authorized site from the identity document
    authorized_site = identity.get("online_url", "")

    # 1. Get the referer strictly. If missing, it's an empty string.
    # Do NOT provide a default like "localhost" here.
    # e.g.  actual_referer = 'https://www.clientsite.com/page' 
    # Important to understand that actual_referer can be a full URL, not just a domain.
    actual_referer = request.headers.get("referer", "")

    # 2. Extract our own hostname for the "Self" check
    #How it is used here: .hostname extracts just the domain name or IP address from that URL.
    # The breakdown:
	# .hostname: The specific domain name of your server (e.g., ://example.com or localhost). 
    # It strips out the protocol (https://) and the port number (like :8000).
    my_api_hostname = request.base_url.hostname or ""

    # 3. If there is NO referer, we must decide if we allow it.
    # ARCHITECT'S DECISION: In production, no referer = no entry.
    if not actual_referer:
        # Exception: You might want to allow your Hub to call without a referer 
        # during specific server-to-server tasks, but for /recommend, 
        # we should be strict.
        raise HTTPException(
            status_code=403, 
            detail="Security Violation: Referer header is missing."
        )

    # 4. Now perform the substring matching against the list
    # Because actual_referer is guaranteed to be a real string from the client
    # 'in' is a substring check, so we need to ensure actual_referer is a string
    # 'www.smartrecshub.com' in 'https://www.smartrecshub.com/some/path' will return True
    is_system = any(domain in actual_referer for domain in SYSTEM_DOMAINS)
    
    #e.g. 'localhost' in 'http://localhost:8000/page' will return True
    is_self = my_api_hostname in actual_referer if my_api_hostname else False

    # Client Verification: Check if the referer matches the authorized site
    # 'www.clientsite.com' in 'https://www.clientsite.com/page' will return True    
    is_client = authorized_site in actual_referer if authorized_site else False

    # 5. Final Gate
    if not (is_system or is_self or is_client):
        raise HTTPException(
            status_code=403, 
            detail=f"Domain unauthorized. Origin identified as: {actual_referer}"
        )


    # Return the store_name to be used in the next step
    return identity.get("store_name")

# --- 3. THE CORE ENDPOINT ---
@app.get("/recommend")
async def recommend(
    request: Request, 
    items: List[str] = Query(...),
    _ui_auth: str = Security(api_key_header) 
):
    """
    The flow is now 100% visible. No hidden parameters.
    """
    # STEP 1: CALL THE GUARD EXPLICITLY (The First Line)
    # This replaces Depends(). If it fails, it raises an exception and stops here.
    store_name = await verify_access_manually(request)

    # STEP 2: PROCEED WITH LOGIC
    start_time = time.perf_counter()
    
    # Transformation: Simple ID -> Internal Keyed ID
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

@app.get("/")
async def root():
    return {
        "status": "online", 
        "version": "1.0.3-security-fix", # Change this string every time you push
        "message": "Can test from https://recommendation-engine-api-1082432876184.us-central1.run.app/docs. Empty headers are now rejected. Referer must be present for security.  "
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)