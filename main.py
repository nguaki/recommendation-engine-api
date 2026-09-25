import asyncio
from fastapi import FastAPI, Query
from typing import List, Dict
from google.cloud import firestore

app = FastAPI(title="Recommendation Machine API")

# Initialize Firestore Client (Async)
db = firestore.AsyncClient()

async def get_item_model(subject_key: str):
    """Retrieves a single item's co-purchase data from Firestore."""
    doc_ref = db.collection("models").document(subject_key)
    doc = await doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

@app.get("/recommend")
async def recommend(items: List[str] = Query(...)):
    """
    Takes a list of items (e.g., ["ABC#hot dog", "ABC#coke"])
    Returns merged, filtered, and sorted recommendations.
    """
    # 1. Fetch all models in parallel (Asyncio Gather)
    # This is the "Low Latency" secret: querying all items at once.
    tasks = [get_item_model(item) for item in items]
    results = await asyncio.gather(*tasks)

    # 2. Extract raw item names from the input to filter them out later
    # e.g., "ABC#hot dog" -> "hot dog"
    input_item_names = [item.split("#")[1] for item in items if "#" in item]

    merged_recommendations: Dict[str, float] = {}

    # 3. Processing & Merging Logic
    for model in results:
        if not model:
            continue
        
        # Iterate through the 5 co-purchase slots defined in your schema
        for i in range(1, 6):
            item_key = f"co_purchase{i}"
            coeff_key = f"co_purchase{i}_coeff"
            
            rec_name = model.get(item_key)
            rec_coeff = model.get(coeff_key)

            if rec_name and rec_coeff is not None:
                # Rule: Remove item if it's already in the basket
                if rec_name in input_item_names:
                    continue

                # Rule: Merge duplicates by keeping the highest score
                if rec_name in merged_recommendations:
                    if rec_coeff > merged_recommendations[rec_name]:
                        merged_recommendations[rec_name] = rec_coeff
                else:
                    merged_recommendations[rec_name] = rec_coeff

    # 4. Sort by coefficient in descending order
    sorted_recs = sorted(
        merged_recommendations.items(), 
        key=lambda x: x[1], 
        reverse=True
    )

    # 5. Format for the client
    return {
        "basket": input_item_names,
        "recommendations": [{"item": k, "confidence": v} for k, v in sorted_recs]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)