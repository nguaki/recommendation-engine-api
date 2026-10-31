
In your 40+ years of engineering, you’ve managed many different "Ship" procedures. It is perfectly natural to lose the thread of a deployment pipeline when you are managing two separate cloud ecosystems (Vercel and GCP) simultaneously.
As the "Ultimate Responsible" architect, here is the reminder of how your Data Plane (Restful API) moves from your laptop to the global public.
1. The Separation of Environments
First, let's re-establish the boundary:
Vercel: Hosts only your Control Plane (smartrecs.com). It handles the UI, the translations, and the Stripe billing automation.
GCP Cloud Run: Hosts your Data Plane (recommendation-engine-api). This is the high-performance engine that serves the actual recommendations to online stores.
2. How the Code Goes Public (The Pipeline)
When you execute your ship-prod alias (or git push origin main) from your local directory /mnt/c/Users/chkim/james/recommendation_restful_api, the following Automation Chain is triggered:
GitHub Receipt: Your code lands in the recommendation-engine-api repository.
GCP Cloud Build Trigger: Google Cloud is "watching" that specific GitHub repo. As soon as it sees the push, it wakes up a service called Cloud Build.
The Docker Build: Cloud Build reads your Dockerfile, installs the requirements from requirements.txt, and packages your FastAPI code into a "Container Image."
Cloud Run Revision: Once the image is built, GCP automatically creates a new Revision of your service and begins shifting traffic to it.
The Ingress Gate: Because we executed the command gcloud run services update ... --ingress all, the service is reachable via its public URL.
3. Your Production URL
Your API currently resides at this permanent Google address:
👉 https://recommendation-engine-api-1082432876184.us-central1.run.app
To check the health: Visit the URL directly in your browser. (It should show the "online" JSON message we added to the root @app.get("/")).
To check the documentation: Append /docs to the end to see the interactive Swagger UI.
4. How to Monitor/Verify in the GCP Console
If you want to see the status of the build or the deployment manually:
Go to the GCP Cloud Run Console.
Select your service: recommendation-engine-api.
Click the REVISIONS tab to see the history of your pushes.
Click the LOGS tab to see the "stdout" of your Python code running in the cloud.
🛡️ Why we didn't use Vercel for the API
As a veteran, you'll remember our reasoning for this architectural split:
Scale: Cloud Run allows your API to handle much higher concurrency for your 1 million potential clients.
Cost: Cloud Run's "Scale to Zero" logic is more precise for high-frequency API calls, protecting that 70% profit margin.
Security: By keeping the API in GCP, it sits right next to your Firestore database on the Google backbone, reducing internal latency.
Summary Checklist for your next Push:
Work in your recommendation_restful_api folder.
Test locally using uvicorn main:app --reload.
Push to GitHub using git push origin main.
Wait 2-3 minutes, then refresh .../docs to see the new changes live.
Does this "GCP-GitHub" link feel familiar again? You are essentially using GitHub as the "Remote Terminal" to tell Google Cloud to rebuild your engine.