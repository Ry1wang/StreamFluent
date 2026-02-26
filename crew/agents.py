import os
from dotenv import load_dotenv
from crewai import Agent, LLM

from .tools.scan_tools import ScanDirectoryTool
from .tools.karaoke_tools import ProcessKaraokeTasksTool
from .tools.upload_tools import BilibiliUploadTool

# 加载环境变量
load_dotenv()

# 初始化 DeepSeek LLM（使用 CrewAI 原生 LLM，底层为 LiteLLM）
deepseek_llm = LLM(
    model="openai/deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
    temperature=0,
)

scan_tool = ScanDirectoryTool()
karaoke_tool = ProcessKaraokeTasksTool()
upload_tool = BilibiliUploadTool()

scanner_agent = Agent(
    role="Podcast Content Scanner",
    goal=(
        "Discover all podcast audio episodes in a given directory and prepare a "
        "structured task list ready for downstream processing."
    ),
    backstory=(
        "You are a meticulous content librarian. You scan directories to find audio files, "
        "match each with its artwork, generate any missing background or cover images, "
        "and produce a well-structured tasks.json file."
    ),
    tools=[scan_tool],
    llm=deepseek_llm,
    verbose=True,
)

producer_agent = Agent(
    role="Karaoke Video Producer",
    goal=(
        "Transform podcast audio episodes into karaoke-style MP4 videos "
        "with word-level synchronized lyrics."
    ),
    backstory=(
        "You are an expert audio-visual producer. You use Faster-Whisper to transcribe speech "
        "with word-level timestamps, generate precise ASS karaoke subtitle files, and render "
        "polished MP4 videos with FFmpeg. You process all tasks sequentially for stability."
    ),
    tools=[karaoke_tool],
    llm=deepseek_llm,
    verbose=True,
)

publisher_agent = Agent(
    role="Bilibili Content Publisher",
    goal="Upload completed karaoke videos to Bilibili with proper titles, tags, and cover images.",
    backstory=(
        "You are a social media publishing specialist focused on Bilibili. "
        "You upload videos with accurate metadata, respect platform rate limits, "
        "and keep the user informed of each upload's outcome."
    ),
    tools=[upload_tool],
    llm=deepseek_llm,
    verbose=True,
)
