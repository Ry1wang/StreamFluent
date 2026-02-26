import json
import os
import sys
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# Ensure project root is importable regardless of where this module is loaded from
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scan_tasks import scan_directory  # noqa: E402


class ScanDirectoryInput(BaseModel):
    base_dir: str = Field(
        ...,
        description="Absolute or relative path to the directory containing audio and image files",
    )
    output_json: str = Field(
        default="tasks.json",
        description="File path where the discovered tasks will be written as JSON",
    )


class ScanDirectoryTool(BaseTool):
    name: str = "Scan Directory for Tasks"
    description: str = (
        "Scans a directory recursively for audio files (mp3, wav, m4a, flac). "
        "For each audio file it finds or generates a matching background image and "
        "Bilibili cover image. Writes all task metadata (audio path, image paths, "
        "title, tags, etc.) to a tasks.json file. "
        "Use this to prepare a batch of podcast episodes for karaoke processing."
    )
    args_schema: Type[BaseModel] = ScanDirectoryInput

    def _run(self, base_dir: str, output_json: str = "tasks.json") -> str:
        try:
            tasks = scan_directory(base_dir)
            if not tasks:
                return f"No audio tasks found in '{base_dir}'."

            with open(output_json, "w", encoding="utf-8") as f:
                json.dump(tasks, f, indent=4, ensure_ascii=False)

            preview = tasks[0].get("audio_path", "N/A")
            return (
                f"Scan complete. Found {len(tasks)} audio task(s). "
                f"Written to '{output_json}'. "
                f"First entry: {preview}"
            )
        except Exception as e:
            return f"ERROR: Directory scan failed — {e}"
