import asyncio
import os
import sys
import threading
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

CREDENTIAL_FILE = os.path.join(_PROJECT_ROOT, "bili_sess.json")


def _run_async(coro):
    """Run an async coroutine safely regardless of whether an event loop is running.

    CrewAI runs its own async event loop, so asyncio.run() would raise
    'This event loop is already running'. Running in a fresh thread avoids that.
    """
    exc: list = [None]

    def target():
        try:
            asyncio.run(coro)
        except Exception as e:
            exc[0] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join()
    if exc[0]:
        raise exc[0]


class BilibiliUploadInput(BaseModel):
    tasks_json: str = Field(
        default="tasks.json",
        description=(
            "Path to the tasks JSON file. Each entry must have 'audio_path', 'title', "
            "'desc', 'tags', 'tid', 'copyright', 'source', and 'bili_cover_path'."
        ),
    )
    cleanup: bool = Field(
        default=False,
        description="If True, delete source audio, generated video, and image files after a successful upload",
    )


class BilibiliUploadTool(BaseTool):
    name: str = "Bilibili Batch Uploader"
    description: str = (
        "Reads tasks from tasks.json, looks up each completed karaoke video in the database, "
        "and uploads it to Bilibili with title, description, tags, and cover image. "
        "Requires a valid 'bili_sess.json' credential file (run: python bili_upload.py --login). "
        "Returns a summary of upload results."
    )
    args_schema: Type[BaseModel] = BilibiliUploadInput

    def _run(self, tasks_json: str = "tasks.json", cleanup: bool = False) -> str:
        try:
            if not os.path.exists(CREDENTIAL_FILE):
                return (
                    "ERROR: bili_sess.json not found. "
                    "Please authenticate first: python bili_upload.py --login"
                )
            if not os.path.exists(tasks_json):
                return f"ERROR: Tasks file not found: '{tasks_json}'"

            from bili_upload import batch_upload  # noqa: E402

            _run_async(batch_upload(tasks_json, cleanup=cleanup))
            return (
                f"Bilibili batch upload completed from '{tasks_json}'. "
                "Check console output above for per-video status."
            )
        except Exception as e:
            return f"ERROR: Upload failed — {e}"
