import os
import json
import subprocess
import datetime
from typing import List, Dict, Any
import logging

# Fix for OMP: Error #15: Initializing libomp.dylib, but found libomp.dylib already initialized.
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Ensure FFmpeg is in PATH (Anaconda default)
if "/opt/anaconda3/bin" not in os.environ["PATH"]:
    os.environ["PATH"] = "/opt/anaconda3/bin:" + os.environ["PATH"]

from sqlalchemy import create_engine, Column, Integer, String, Enum, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from faster_whisper import WhisperModel
from tqdm import tqdm

# --- Configuration & Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "karaoke_tasks.db"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Database Model ---
Base = declarative_base()

class Task(Base):
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True)
    audio_path = Column(String, nullable=False)
    image_path = Column(String, nullable=False)
    output_path = Column(String, nullable=True)
    status = Column(String, default="pending") 
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# --- Components ---

class JobManager:
    def __init__(self, db_url=f"sqlite:///{DB_PATH}"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def add_task(self, audio_path: str, image_path: str) -> int:
        session = self.Session()
        task = Task(audio_path=audio_path, image_path=image_path, status="pending")
        session.add(task)
        session.commit()
        task_id = task.id
        session.close()
        logger.info(f"Task added: ID {task_id}")
        return task_id

    def update_status(self, task_id: int, status: str, output_path: str = None, error_msg: str = None):
        session = self.Session()
        task = session.get(Task, task_id)
        if task:
            task.status = status
            if output_path:
                task.output_path = output_path
            if error_msg:
                task.error_msg = error_msg
            session.commit()
            logger.info(f"Task {task_id} updated to {status}")
        session.close()

    def get_pending_tasks(self) -> List[Task]:
        session = self.Session()
        tasks = session.query(Task).filter_by(status="pending").all()
        session.expunge_all()
        session.close()
        return tasks

class Transcriber:
    def __init__(self, model_size="base"):
        logger.info(f"Loading Faster Whisper model: {model_size}...")
        # Use CPU + Int8 for compatibility on generic Mac hardware without specific setup
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio_path: str) -> List[Any]:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        logger.info(f"Transcribing {audio_path}...")
        segments, info = self.model.transcribe(audio_path, word_timestamps=True)
        # Convert generator to list
        segment_list = list(segments)
        logger.info(f"Transcription complete. Detected language: {info.language}")
        return segment_list

class SubtitleGenerator:
    @staticmethod
    def format_time_ass(seconds: float) -> str:
        """Converts seconds to ASS lists format: H:MM:SS.cs"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds * 100) % 100)
        return f"{h}:{m:02}:{s:02}.{cs:02}"

    def generate_ass(self, segments: List[Any], output_path: str):
        logger.info(f"Generating ASS subtitles to {output_path}...")
        
        header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial,72,&H17A0D4,&H001E1E1E,&H00000000,&H001E1E1E,-1,0,0,0,100,100,0,0,1,0,0,5,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []

        for segment in segments:
            # Faster Whisper segments are objects, not dicts
            start_time = segment.start
            end_time = segment.end
            
            ass_start = self.format_time_ass(start_time)
            ass_end = self.format_time_ass(end_time)
            
            line_text = ""
            current_seg_time = start_time
            
            words = segment.words
            if not words:
                line_text = segment.text.strip()
            else:
                for word_obj in words:
                    w_word = word_obj.word
                    w_start = word_obj.start
                    w_end = word_obj.end
                    
                    gap = w_start - current_seg_time
                    duration = w_end - w_start
                    
                    gap_cs = int(gap * 100)
                    dur_cs = int(duration * 100)
                    
                    if gap_cs > 0:
                        line_text += f"{{\\k{gap_cs}}}" 
                    
                    line_text += f"{{\\k{dur_cs}}}{w_word}"
                    
                    current_seg_time = w_end

            # Add \pos(960, 720) to force Y position. 960 is center of 1920.
            event_line = f"Dialogue: 0,{ass_start},{ass_end},Karaoke,,0,0,0,,{{\\pos(960,680)}}{line_text}"
            events.append(event_line)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(header + "\n".join(events))

class VideoRenderer:
    def render(self, audio_path: str, image_path: str, ass_path: str, output_video: str):
        logger.info(f"Rendering video to {output_video}...")
        
        if os.path.exists(output_video):
            os.remove(output_video)

        # Basic escaping for single quotes in path
        safe_ass_path = ass_path.replace("'", "'\\''")

        cmd = [
            "ffmpeg",
            "-y", 
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-vf", f"subtitles='{safe_ass_path}'",
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            output_video
        ]
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed: {e.stderr.decode()}")
            raise RuntimeError(f"FFmpeg rendering failed")

# --- Workflow Orchestrator ---

class KaraokeGenerator:
    def __init__(self):
        self.job_manager = JobManager()
        self.transcriber = Transcriber(model_size="base")
        self.subtitle_gen = SubtitleGenerator()
        self.renderer = VideoRenderer()

    def add_task(self, audio_path: str, image_path: str):
        return self.job_manager.add_task(audio_path, image_path)

    def process_pending_tasks(self):
        tasks = self.job_manager.get_pending_tasks()
        if not tasks:
            logger.info("No pending tasks.")
            return

        for task in tasks:
            logger.info(f"Processing Task {task.id}...")
            self.job_manager.update_status(task.id, "processing")
            
            try:
                # 1. Transcribe
                transcript_segments = self.transcriber.transcribe(task.audio_path)
                
                # Save plain text
                base_name = os.path.splitext(os.path.basename(task.audio_path))[0]
                timestamp = int(datetime.datetime.now().timestamp())
                txt_path = os.path.join(OUTPUT_DIR, f"{base_name}_{timestamp}.txt")
                ass_path = os.path.join(OUTPUT_DIR, f"{base_name}_{timestamp}.ass")
                vid_path = os.path.join(OUTPUT_DIR, f"{base_name}_{timestamp}.mp4")

                full_text = "".join([s.text for s in transcript_segments])
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(full_text)
                
                # 2. Generate ASS
                self.subtitle_gen.generate_ass(transcript_segments, ass_path)
                
                # 3. Render Video
                self.renderer.render(task.audio_path, task.image_path, ass_path, vid_path)
                
                self.job_manager.update_status(task.id, "completed", output_path=vid_path)
                logger.info(f"Task {task.id} completed successfully. Output: {vid_path}")

            except Exception as e:
                logger.exception(f"Task {task.id} failed.")
                self.job_manager.update_status(task.id, "failed", error_msg=str(e))

if __name__ == "__main__":
    import sys
    print("Karaoke Generator (Faster-Whisper Version) Initialized.")
    if len(sys.argv) == 3:
        audio = sys.argv[1]
        img = sys.argv[2]
        gen = KaraokeGenerator()
        gen.add_task(audio, img)
        gen.process_pending_tasks()
    else:
        print("\nUsage: python karaoke_gen.py <audio_path> <img_path>")
