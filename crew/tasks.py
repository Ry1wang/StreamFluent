from crewai import Task

from .agents import scanner_agent, producer_agent, publisher_agent

scan_task = Task(
    description=(
        "Scan the podcast directory at '{podcast_dir}' for all audio files "
        "(mp3, wav, m4a, flac). For each audio file, find or generate its background "
        "image and Bilibili cover image. Write all task metadata to 'tasks.json'. "
        "Report how many tasks were discovered."
    ),
    expected_output=(
        "A confirmation message stating that tasks.json has been written, "
        "the total number of audio tasks found, and the path to the file."
    ),
    agent=scanner_agent,
)

produce_task = Task(
    description=(
        "Read all tasks from 'tasks.json'. For each task: add it to the karaoke job queue, "
        "transcribe its audio with Faster-Whisper (word-level timestamps), "
        "generate an ASS karaoke subtitle file, and render the final MP4 video with FFmpeg. "
        "Report the number of successfully completed and failed videos."
    ),
    expected_output=(
        "A summary showing how many karaoke MP4 videos were successfully produced, "
        "how many failed, and any error details for failed tasks."
    ),
    agent=producer_agent,
    context=[scan_task],
)

publish_task = Task(
    description=(
        "Read all tasks from 'tasks.json'. For each completed video found in the karaoke database, "
        "upload it to Bilibili using the title, description, tags, cover image, and tid from the task. "
        "Report upload results for every video."
    ),
    expected_output=(
        "A summary listing which videos were successfully uploaded to Bilibili "
        "and which failed, with any relevant error messages."
    ),
    agent=publisher_agent,
    context=[produce_task],
)
