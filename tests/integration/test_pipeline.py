"""End-to-end pipeline tests (these DO call the model).

Run with: uv run pytest tests/integration/test_pipeline.py -q
"""

import pytest
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import root_agent

CLEAN_DIFF = """--- a/app/formatting.py
+++ b/app/formatting.py
@@ -1,2 +1,4 @@
 def title(s):
-    return s
+    # capitalize each word for display
+    return s.title()
"""

SECRET_DIFF = """--- a/app/config.py
+++ b/app/config.py
@@ -1,1 +1,2 @@
 DEBUG = True
+AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"
"""


async def _review(diff: str) -> str:
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="app", user_id="t", session_id="s", state={"diff": diff}
    )
    runner = Runner(
        agent=root_agent, app_name="app", session_service=session_service
    )
    out = ""
    async for event in runner.run_async(
        user_id="t",
        session_id="s",
        new_message=types.Content(
            role="user", parts=[types.Part.from_text(text="review this")]
        ),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    out = part.text
    return out


@pytest.mark.asyncio
async def test_clean_diff_gets_a_verdict_and_vibe_diff():
    out = await _review(CLEAN_DIFF)
    assert "Repo Guardian" in out
    assert "Vibe Diff" in out
    # a trivial formatting change should not be blocked
    assert "REQUEST_CHANGES" not in out


@pytest.mark.asyncio
async def test_secret_diff_is_blocked_without_calling_model():
    out = await _review(SECRET_DIFF)
    assert "REQUEST_CHANGES" in out
    # the secret value must never appear in output
    assert "AKIAIOSFODNN7EXAMPLE" not in out
