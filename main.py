"""
StreamFluent — CrewAI pipeline entry point

Pipeline:
  1. Scanner Agent  — scans a podcast directory, generates missing images, writes tasks.json
  2. Producer Agent — transcribes audio (Whisper), renders karaoke MP4 videos (FFmpeg)
  3. Publisher Agent — uploads completed videos to Bilibili

Usage:
  python main.py --dir ../PodCast
  python main.py --dir ../PodCast --tasks tasks.json
  python main.py --dir ../PodCast --skip-upload
"""

import argparse
import os
import sys

from crewai import Crew, Process

from crew.agents import scanner_agent, producer_agent, publisher_agent
from crew.tasks import scan_task, produce_task, publish_task


def build_crew(skip_upload: bool = False) -> Crew:
    agents = [scanner_agent, producer_agent]
    tasks = [scan_task, produce_task]

    if not skip_upload:
        agents.append(publisher_agent)
        tasks.append(publish_task)

    return Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="StreamFluent CrewAI Pipeline — scan → produce → publish"
    )
    parser.add_argument(
        "--dir",
        default="../PodCast",
        help="Directory containing podcast audio files (default: ../PodCast)",
    )
    parser.add_argument(
        "--tasks",
        default="tasks.json",
        help="Output path for the tasks JSON file (default: tasks.json)",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Stop after video production; skip the Bilibili upload step",
    )
    args = parser.parse_args()

    podcast_dir = os.path.abspath(args.dir)
    if not os.path.isdir(podcast_dir):
        print(f"Error: Directory not found: {podcast_dir}")
        sys.exit(1)

    print(f"\n=== StreamFluent CrewAI Pipeline ===")
    print(f"  Podcast dir : {podcast_dir}")
    print(f"  Tasks file  : {args.tasks}")
    print(f"  Upload step : {'disabled' if args.skip_upload else 'enabled'}")
    print("=====================================\n")

    crew = build_crew(skip_upload=args.skip_upload)
    result = crew.kickoff(inputs={"podcast_dir": podcast_dir})

    print("\n=== Pipeline Complete ===")
    print(result)


if __name__ == "__main__":
    main()
