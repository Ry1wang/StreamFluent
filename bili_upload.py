import asyncio
import argparse
import json
import os
import sys
# Add current directory just in case
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bilibili_api.login_v2 import QrCodeLogin
from bilibili_api.video_uploader import VideoUploader, VideoUploaderPage, VideoMeta
from bilibili_api import Credential

CREDENTIAL_FILE = "bili_sess.json"

async def login():
    print("Initializing QR Code Login...")
    qr_login = QrCodeLogin()
    
    # Generate QR Code info
    await qr_login.generate_qrcode()
    
    # Extract URL using name mangling since it's private
    # We inspected source: self.__qr_link
    url = getattr(qr_login, "_QrCodeLogin__qr_link", None)
    
    if not url:
        print("[Error] Could not extract QR URL from QrCodeLogin object.")
        return

    print(f"\n[Login URL]: {url}\n")
    
    # Render with standard qrcode library
    import qrcode
    qr = qrcode.QRCode()
    qr.add_data(url)
    qr.print_ascii(invert=True)
    
    print("Please scan the QR code with your Bilibili App (or open URL above).")
    print("Waiting for scan...")
    
    try:
        # Polling loop
        while True:
            # check_state polls the API to update status
            # It seems to return a boolean, but it might just mean "request successful"
            # The real success flag is has_done()
            await qr_login.check_state()
            
            if hasattr(qr_login, 'has_done'):
                if qr_login.has_done():
                    print("\nLog in successful!")
                    break
            
            # Print feedback
            print(".", end="", flush=True)
            await asyncio.sleep(2)
            
        # Get credential (synchronous per inspection)
        credential = qr_login.get_credential()
        
        cookies = {
            "sessdata": credential.sessdata,
            "bili_jct": credential.bili_jct,
            "buvid3": credential.buvid3,
            "dedeuserid": credential.dedeuserid
        }
        
        with open(CREDENTIAL_FILE, "w") as f:
            json.dump(cookies, f)
            
        print(f"Login successful! Credentials saved to {CREDENTIAL_FILE}")
        
    except Exception as e:
        print(f"\nLogin failed: {e}")

async def upload(video_path, title, desc, tags, copyright=1, source="", cover_path=None, tid=181):
    if not os.path.exists(CREDENTIAL_FILE):
        print(f"Error: {CREDENTIAL_FILE} not found. Please run with --login first.")
        return

    with open(CREDENTIAL_FILE, "r") as f:
        cookies = json.load(f)
    
    cred = Credential(
        sessdata=cookies.get("sessdata"),
        bili_jct=cookies.get("bili_jct"),
        buvid3=cookies.get("buvid3"),
        dedeuserid=cookies.get("dedeuserid")
    )
    
    print(f"Prepare uploading {video_path}...")
    
    # 1. Prepare Page
    page = VideoUploaderPage(path=video_path, title=title, description=desc)
    
    # 2. Prepare Meta
    if not cover_path or not os.path.exists(cover_path):
        print(f"[WARN] No cover image found for {title}. Trying to proceed assuming library might extract it or fail.")
        if not cover_path:
             cover_path = video_path # Risky fallback
    
    tag_list = tags.split(',') if isinstance(tags, str) else tags
    if not tag_list:
        tag_list = ["Karaoke"]

    is_original = (int(copyright) == 1)
    source_url = source if not is_original else None

    meta = VideoMeta(
        tid=int(tid), 
        title=title,
        desc=desc,
        cover=cover_path,
        tags=tag_list,
        original=is_original,
        source=source_url
    )
    
    uploader = VideoUploader(pages=[page], meta=meta, credential=cred)
    
    @uploader.on("upload_chunk")
    async def on_upload_chunk(data):
        # Progress log
        pass 

    try:
        print("Starting upload...")
        await uploader.start()
        print(f"\nUpload successful for '{title}'!")
    except Exception as e:
        print(f"\nUpload failed for '{title}': {e}")

async def batch_upload(json_path, cleanup=False):
    if not os.path.exists(CREDENTIAL_FILE):
        print("Please login first using --login")
        return

    # Import DB models
    try:
        from karaoke_gen import JobManager, Task
    except ImportError:
        print("Error: Could not import karaoke_gen. Make sure you are in the project root.")
        return

    manager = JobManager()
    session = manager.Session()
    
    with open(json_path, 'r', encoding='utf-8') as f:
        tasks = json.load(f)
        
    print(f"Loaded {len(tasks)} tasks from {json_path}")
    
    for i, task in enumerate(tasks):
        title = task.get("title")
        audio_path = task.get("audio_path")
        
        if not title:
            print(f"Skipping task {i}: No title")
            continue

        if len(title) > 80:
             print(f"[WARN] Title too long ({len(title)} chars). Truncating.")
             title = title[:80]
            
        # 1. Get Video Path from DB
        db_task = session.query(Task).filter(
            Task.audio_path == audio_path, 
            Task.status == 'completed'
        ).order_by(Task.updated_at.desc()).first()
        
        if not db_task:
            print(f"Skipping '{title}': No completed video found in DB.")
            continue
            
        video_path = db_task.output_path
        if not video_path or not os.path.exists(video_path):
            print(f"Skipping '{title}': Video file missing at {video_path}")
            continue
            
        # 2. Get Cover Image from JSON (bili_cover_path is the Bilibili cover;
        #    image_path is the video background — they are different files)
        cover_path = task.get("bili_cover_path") or task.get("image_path")
        
        print(f"Found video: {video_path}")
        
        await upload(
            video_path=video_path,
            title=title,
            desc=task.get("desc", ""),
            tags=task.get("tags", ""),
            copyright=task.get("copyright", 1),
            source=task.get("source", ""),
            cover_path=cover_path,
            tid=task.get("tid", 181)
        )
        
        # 3. Cleanup after success (optional but requested)
        if cleanup:
            print(f"Cleaning up files for '{title}'...")
            files_to_delete = [
                video_path,
                video_path.replace(".mp4", ".ass"),
                audio_path,
                task.get("image_path"),
                task.get("bili_cover_path")
            ]
            for f_path in files_to_delete:
                if f_path and os.path.exists(f_path):
                    try:
                        os.remove(f_path)
                        print(f"  Deleted: {os.path.basename(f_path)}")
                    except Exception as e:
                        print(f"  Failed to delete {f_path}: {e}")

        print("Waiting 5s before next upload...")
        await asyncio.sleep(5)
        
    session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bilibili Uploader (v2 API)")
    # ... (args same)
    parser.add_argument("--login", action="store_true", help="Login via QR code")
    parser.add_argument("--upload", help="Path to video file")
    parser.add_argument("--title", help="Video Title")
    parser.add_argument("--desc", default="", help="Video Description")
    parser.add_argument("--tags", default="Karaoke", help="Comma separated tags")
    parser.add_argument("--tid", type=int, default=181, help="Bilibili partition TID (default 181 - Knowledge)")
    parser.add_argument("--cover", help="Path to cover image (required for single upload)")
    parser.add_argument("--batch", help="Path to tasks.json for batch upload")
    parser.add_argument("--cleanup", action="store_true", help="Delete source and generated files after successful upload")

    args = parser.parse_args()

    # Use asyncio.run for modern python
    if args.login:
        asyncio.run(login())
    elif args.batch:
        asyncio.run(batch_upload(args.batch, cleanup=args.cleanup))
    elif args.upload:
        if not args.title:
            print("Error: --title is required for upload.")
        elif not args.cover:
             print("Error: --cover is required for single upload (Bilibili restriction).")
        else:
            asyncio.run(upload(
                args.upload, 
                args.title, 
                args.desc, 
                args.tags,
                cover_path=args.cover,
                tid=args.tid
            ))
    else:
        parser.print_help()
