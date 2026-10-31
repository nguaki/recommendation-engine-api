The Audit: Look at the column labeled "Traffic".
Does the top revision (the one from Oct 29, 9:24 PM) have 100% next to it?
If a previous revision has 100%, then your latest code is "Ready" but not "Active."

"Promote to Production"
To see your changes live right now, you must manually move the traffic:
Stay on that Revisions tab in the Cloud Run Console.
Click the "MANAGE TRAFFIC" button at the top of the list.
You will see a list of revisions. Find recommendation-engine-api-00006-zlz.
Change its traffic percentage from 0 to 100.
(The other older revision will automatically drop to 0).
Click SAVE.
