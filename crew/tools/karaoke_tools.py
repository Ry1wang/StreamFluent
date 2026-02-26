import json
import os
import sys
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from karaoke_gen import JobManager, KaraokeGenerator, Task as KaraokeTask  # noqa: E402


class ProcessKaraokeTasksInput(BaseModel):
    tasks_json: str = Field(
        default="tasks.json",
        description="Path to the tasks JSON file produced by the directory scanner",
    )


class ProcessKaraokeTasksTool(BaseTool):
    name: str = "Process Karaoke Tasks"
    description: str = (
        "Reads a tasks.json file and processes each audio+image pair into a karaoke MP4 video. "
        "For each task it: (1) transcribes the audio with Faster-Whisper, "
        "(2) generates an ASS karaoke subtitle file with word-level timing, "
        "(3) renders the final MP4 with FFmpeg (static image + audio + subtitles). "
        "All jobs are tracked in a SQLite database. "
        "Returns a summary of completed and failed tasks."
    )
    args_schema: Type[BaseModel] = ProcessKaraokeTasksInput

    def _run(self, tasks_json: str = "tasks.json") -> str:
        try:
            if not os.path.exists(tasks_json):
                return f"ERROR: Tasks file not found: '{tasks_json}'"

            with open(tasks_json, "r", encoding="utf-8") as f:
                tasks = json.load(f)

            if not tasks:
                return "ERROR: Tasks file is empty."

            gen = KaraokeGenerator()
            added, skipped = 0, 0

            for task in tasks:
                audio = task.get("audio_path", "")
                image = task.get("image_path", "")
                if not audio or not os.path.exists(audio):
                    skipped += 1
                    continue
                gen.add_task(audio, image)
                added += 1

            if added == 0:
                return f"No valid tasks to process (skipped {skipped} with missing audio)."

            gen.process_pending_tasks()

            # Report final DB counts
            manager = JobManager()
            session = manager.Session()
            completed = session.query(KaraokeTask).filter_by(status="completed").count()
            failed = session.query(KaraokeTask).filter_by(status="failed").count()
            session.close()

            return (
                f"Karaoke processing complete. "
                f"Added: {added}, Skipped (missing audio): {skipped}. "
                f"DB totals — Completed: {completed}, Failed: {failed}."
            )
        except Exception as e:
            return f"ERROR: Karaoke processing failed — {e}"
