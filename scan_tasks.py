import os
import json
import argparse
from pathlib import Path

def scan_directory(base_dir):
    tasks = []
    base_path = Path(base_dir).resolve()
    
    if not base_path.exists():
        print(f"Error: Directory {base_path} not found.")
        return []

    print(f"Scanning directory: {base_path}")
    
    # Supported extensions
    audio_exts = {'.mp3', '.wav', '.m4a', '.flac'}
    image_exts = {'.jpg', '.jpeg', '.png', '.webp'}
    
    # Find all audio files
    audio_files = []
    for ext in audio_exts:
        audio_files.extend(base_path.rglob(f"*{ext}"))
    
    audio_files.sort()
    
    # Helper to extract numbers from string
    import re
    def extract_episode_num(filename):
        # Matches "Ep. 30", "Ep30", "30" etc.
        # We look for the last significant number or specific "Ep" patterns
        # 1. Look for Ep/Episode followed by digits
        match = re.search(r'(?:ep|episode)[._\s]*(\d+)', filename, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # 2. Fallback: return the last distinct number found in filename (risky if dates are present)
        # But commonly "Title 01.mp3" -> 1
        nums = re.findall(r'\d+', filename)
        if nums:
            # Heuristic: usually the episode number is towards the end or is the only number
            return int(nums[-1])
        return None

    # Pre-scan images in the directory to avoid repeated IO
    all_images = []
    for ext in image_exts:
        all_images.extend(base_path.rglob(f"*{ext}"))

    for audio_file in audio_files:
        task = {
            "audio_path": str(audio_file),
            "image_path": None
        }
        
        found_img = False
        audio_num = extract_episode_num(audio_file.name)

        # Strategy 1: Exact name match (Audio.mp3 -> Audio.jpg)
        for ext in image_exts:
            img_candidate = audio_file.with_suffix(ext)
            if img_candidate.exists():
                task["image_path"] = str(img_candidate)
                found_img = True
                break
        
        # Strategy 2: Smart Number Match (if in same directory)
        if not found_img:
            if audio_num is not None:
                # Look for images in the SAME directory with the same number
                parent_dir = audio_file.parent
                candidates = [img for img in all_images if img.parent == parent_dir]
                
                for img in candidates:
                    img_num = extract_episode_num(img.name)
                    if img_num == audio_num:
                        task["image_path"] = str(img)
                        found_img = True
                        break

        # Strategy 3: Fallback to 'cover' image
        if not found_img:
            parent_dir = audio_file.parent
            for ext in image_exts:
                cover_candidate = parent_dir / f"cover{ext}"
                if cover_candidate.exists():
                    task["image_path"] = str(cover_candidate)
                    found_img = True
                    break
        
        # Extraction Logic for Titles (Always run this first)
        import re
        filename_stem = audio_file.stem
        # Regex: Optional [Channel], Optional Number (e.g., 42. or 42 ), then Core Title
        match = re.match(r'^(\[.*?\])?\s*(\d+\s*[\.\s]\s*)?(.*)$', filename_stem)
        
        channel_part = ""
        actual_title = filename_stem # Fallback
        
        if match:
            channel_part = (match.group(1) or "").strip()
            # Also strip trailing "Ep. XX" if present in the rest of the title
            raw_actual = (match.group(3) or "").strip()
            actual_title = re.sub(r'\s*\|\s*Ep\.\s*\d+$', '', raw_actual) # remove " | Ep. 41"
            actual_title = re.sub(r'\s+Ep\.\s*\d+$', '', actual_title)    # remove " Ep. 41"
            actual_title = actual_title.strip()
        
        image_title = actual_title
        if audio_num is not None:
            image_title = f"{actual_title} | Ep. {audio_num}"
            
        bili_title_full = (f"{channel_part} {actual_title}").strip()
        
        # Ensure image_path is set even if not found
        if not task["image_path"]:
            # Default to original filename with .jpg extension in the same directory
            task["image_path"] = str(audio_file.with_suffix(".jpg"))

        # Differentiate between render background and Bilibili cover
        # Logic: look for "cover_" + episode_num
        bili_cover_path = None
        if audio_num is not None:
            parent_dir = audio_file.parent
            candidates = [img for img in all_images if img.parent == parent_dir]
            for img in candidates:
                if img.name.lower().startswith("cover_"):
                    img_num = extract_episode_num(img.name)
                    if img_num == audio_num:
                        bili_cover_path = str(img)
                        break
        
        # Automation: If images missing, generate them!
        from generate_images import ImageGenerator
        gen = ImageGenerator()
        
        if not os.path.exists(task["image_path"]):
            print(f"Background missing for {audio_file.name}, generating -> {Path(task['image_path']).name}")
            gen.generate(image_title, task["image_path"], is_cover=False)
            
        if not bili_cover_path:
            # We expect cover_EpXX.jpeg
            cover_name = f"cover_Ep{audio_num}.jpeg" if audio_num else f"cover_{audio_file.stem}.jpeg"
            bili_cover_path = str(base_path / cover_name)
            
        if not os.path.exists(bili_cover_path):
            print(f"Cover missing for {audio_file.name}, generating -> {Path(bili_cover_path).name}")
            gen.generate(image_title, bili_cover_path, is_cover=True)
        
        # Add metadata for Bilibili upload (Always present in JSON)
        if len(bili_title_full) > 80:
            bili_title_full = bili_title_full[:80]
            
        task["title"] = bili_title_full
        task["desc"] = ""
        task["tags"] = "英语听力,英语学习,PodCast,English"
        task["tid"] = 181 # Knowledge default (知识区)
        task["copyright"] = 2 # 1=Original,2=Cover
        task["source"] = ""   
        task["bili_cover_path"] = bili_cover_path
        
        tasks.append(task)
        print(f"[OK] Processed: {audio_file.name} (Title: {task['title']})")

    return tasks

def main():
    parser = argparse.ArgumentParser(description="Scan directory for audio tasks")
    parser.add_argument("directory", nargs="?", default="../PodCast", help="Directory to scan")
    parser.add_argument("--output", "-o", default="tasks.json", help="Output JSON file")
    
    args = parser.parse_args()
    
    tasks = scan_directory(args.directory)
    
    if tasks:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, indent=4, ensure_ascii=False)
        print(f"\nSuccessfully generated {len(tasks)} tasks in '{args.output}'")
    else:
        print("\nNo tasks found.")

if __name__ == "__main__":
    main()
