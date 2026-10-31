# 🧪 SmartRecs API: Testing & Validation SOP (v1.0)
**Document Purpose:** Standard Operating Procedure for verifying the "Apex" Recommendation Engine. Covers local development and remote production environments.

---
cd james/reco...api/
bash
source venv/bin/activate

uvicorn main:app --reload --port 8001   (whatever available port)
INFO:     Will watch for changes in these directories: ['/mnt/c/Users/chkim/james/recommendation_restful_api']

## 1. Environment Checklist
Before testing, ensure the following are available:
*   **Base URL:** `http://127.0.0.1:8001` (Local) or `https://api.smartrecshub.com` (Prod).
*   **API Key:** Found in Firestore `API_status` collection (e.g., `sr_live_777`).
*   **Store ID:** The Document ID of the `API_status` record (e.g., `ABC`).
*   **Target Item:** An ID existing in the `models` collection (e.g., `ABC#coke`).

---

## 2. Method A: Interactive Swagger UI
FastAPI automatically generates a testing dashboard. This is the fastest way to verify logic and see the **Latency Metric**.

### Steps:
1.  **Open Docs:** Navigate to `http://127.0.0.1:8001/docs` in your browser.
2.  **Authorize (The Lock):**
    *   Click the **Authorize** button (top right).
    *   Enter your `api_key` in the `Value` box.
    *   Click **Authorize** then **Close**.
3.  **Execute Request:**
    *   Find the `GET /recommend` endpoint and click **Try it out**.
    *   **items:** Enter `ABC#coke`.
    *   **referer:** Enter `http://localhost` (Matches `SYSTEM_DOMAINS` logic).
4.  **Review Output:**
    *   Check `latency_ms`. 
    *   *First call:* ~150ms. 
    *   *Second call:* < 2ms (Verification of RAM Cache) i haven't seen this fast????.

---

## 3. Method B: Terminal (cURL)
Use this method for raw infrastructure testing or testing from your WSL terminal.

### The Standard Command:
```bash
curl -X 'GET' \
  'http://127.0.0.1:8001/recommend?items=ABC%23coke' \    <==%23 must be used instead of #
  -H 'accept: application/json' \
  -H 'X-API-KEY: sr_live_777' \
  -H 'referer: http://localhost'
```

### Testing Multiple Items (Parallel Burst Test):
```bash
curl -X 'GET' \
  'http://127.0.0.1:8001/recommend?items=ABC%23coke&items=ABC%23chips' \
  -H 'X-API-KEY: sr_live_777' \
  -H 'referer: http://localhost'
```

---

## 4. Critical Troubleshooting (Error Codes)

| Status Code | Meaning | Fix |
| :--- | :--- | :--- |
| **401 Unauthorized** | API Key Missing | Ensure the `X-API-KEY` header is sent. |
| **403 Forbidden** | Invalid Key or Domain | Check if `api_key` exists in `API_status`. Check if `referer` is in `SYSTEM_DOMAINS` or `online_url`. |
| **402 Payment Required** | Inactive Subscription | Go to Firestore and change `status` to `"active"`. |
| **400 Bad Request** | ID Formatting | Ensure you are using `StoreName#ItemID` format. |
| **404 Not Found** | Empty Result | Verify that the Document ID exists exactly in the `models` collection. |

---

## 5. The "Hash" Rule (# vs %23)
The `#` character is a special "Fragment" character in URLs. To ensure the server receives the full string:
*   **Client-Side (React):** Use `encodeURIComponent("ABC#coke")`.
*   **Manual Testing:** Manually replace `#` with **`%23`**.
*   **Server-Side:** The Python code splits by `#` once received, so the internal data remains consistent.

---

## 6. Performance Validation
To verify the **O(1) Moat**, run three consecutive tests:
1.  **Run 1:** Note the latency (Initial Handshake).
2.  **Run 2:** Note the latency (Should be < 5ms).
3.  **Run 3 (Wait 5 mins):** Note the latency (Verifies `TTLCache` expiration).

**Architect's Note:** If latency is consistently > 200ms in a local environment, check the physical distance to the GCP project region or check for bottlenecked ISP traffic.


local setting
code
Bash

curl -X 'GET' 'http://127.0.0.1:8001/recommend?items=coke' \
  -H 'X-API-KEY: sr_live_777' \
  -H 'referer: ' 

  the above test must result in 
              status_code=403, 
            detail="Security Violation: Referer header is missing."
