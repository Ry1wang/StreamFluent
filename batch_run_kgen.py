import os
import sys

# Ensure current directory is in sys.path to allow importing karaoke_gen
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from karaoke_gen import KaraokeGenerator

# Default hardcoded tasks (fallback)
default_tasks = [
    {
        "audio_path": "sample_audio.mp3",
        "image_path": "sample_image.jpg"
    },
    # ... (You can keep your old test data here if you want)
]

import json

def load_tasks_from_json(json_path="tasks.json"):
    if os.path.exists(json_path):
        print(f"Loading tasks from {json_path}...")
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading {json_path}: {e}")
            return []
    return []

# Priority: tasks.json > hardcoded default_tasks
tasks = load_tasks_from_json()
if not tasks:
    print("No tasks.json found (or empty), using default hardcoded list.")
    tasks = default_tasks


def main():
    print(f"Initializing Batch Processor using KaraokeGenerator...")
    gen = KaraokeGenerator()
    
    print(f"Adding {len(tasks)} tasks to the queue...")
    for i, task in enumerate(tasks):
        audio = task.get("audio_path")
        image = task.get("image_path")
        
        if not os.path.exists(audio):
            print(f"Warning: Audio file not found: {audio}, skipping add.")
            continue
            
        # We don't strictly check image existence here as karaoke_gen might handle it differently,
        # but good practice to check if possible.
        
        task_id = gen.add_task(audio, image)
        print(f"  [{i+1}/{len(tasks)}] Used Add Task -> ID: {task_id}")

    print("\nStarting Serial Execution...")
    print("Why Serial? \n1. Avoiding SQLite database lock contentions.\n2. Preventing Mac CPU/Memory thermal throttling from running multiple AI models simultaneously.\n")
    
    # process_pending_tasks() in karaoke_gen automatically loops through ALL pending tasks
    # sequentially. This is exactly what we want for stability.
    gen.process_pending_tasks()
    
    print("\nBatch processing complete.")

if __name__ == "__main__":
    main()