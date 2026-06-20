"""Query the DEPLOYED Repo Guardian on Vertex AI Agent Runtime.

Proves the live cloud endpoint reviews a diff end-to-end. Run:
    uv run python test_live.py
"""

import json

import vertexai
from vertexai import agent_engines

PROJECT = "fifth-glazing-490707-v0"
LOCATION = "us-east1"
RESOURCE = "projects/788528493953/locations/us-east1/reasoningEngines/3084860191632523264"

vertexai.init(project=PROJECT, location=LOCATION)

SECRET_DIFF = """--- a/app/config.py
+++ b/app/config.py
@@ -1,1 +1,2 @@
 DEBUG = True
+AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"
"""


def main() -> None:
    remote = agent_engines.get(RESOURCE)
    print(f"Querying live agent: {RESOURCE}\n")

    events = list(remote.stream_query(user_id="live-test", message=SECRET_DIFF))
    print(f"received {len(events)} event(s)\n")

    final_text = ""
    for i, event in enumerate(events):
        print(f"--- event {i} ---")
        print(json.dumps(event, indent=2, default=str)[:1500])
        content = event.get("content") if isinstance(event, dict) else None
        if content and content.get("parts"):
            for part in content["parts"]:
                if part.get("text"):
                    final_text = part["text"]

    print("\n=== FINAL TEXT ===")
    print(final_text or "(none)")


if __name__ == "__main__":
    main()
