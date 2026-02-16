from PIL import Image, ImageDraw, ImageFont
import os
import textwrap

class ImageGenerator:
    def __init__(self, background_base="background_base.png", cover_base="cover_base.png", font_path=None):
        self.background_base = background_base
        self.cover_base = cover_base
        
        # Try to find a nice font
        if font_path and os.path.exists(font_path):
            self.font_path = font_path
        else:
            # Common macOS fonts
            fallbacks = [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "/System/Library/Fonts/Helvetica.ttc"
            ]
            self.font_path = next((f for f in fallbacks if os.path.exists(f)), None)

    def generate(self, title, output_path, is_cover=False):
        base_path = self.cover_base if is_cover else self.background_base
        
        if not os.path.exists(base_path):
            print(f"Error: Base image {base_path} not found.")
            return False
            
        img = Image.open(base_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        w, h = img.size
        
        # Font settings
        font_size = 80 if is_cover else 90
        
        # Try to find a bold font for better match
        bold_fallbacks = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica-Bold.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc"
        ]
        actual_font_path = next((f for f in bold_fallbacks if os.path.exists(f)), self.font_path)

        if actual_font_path:
            font = ImageFont.truetype(actual_font_path, font_size)
        else:
            font = ImageFont.load_default()
            
        # Wrap text - We want it on the right half
        # Logic: x_start = w * 0.45 (approx center-right)
        container_w = w * 0.5 
        avg_char_width = font_size * 0.45
        chars_per_line = int(container_w / avg_char_width)
        lines = textwrap.wrap(title, width=chars_per_line)
        
        # Calculate vertical positioning
        # line_spacing = 1.2
        line_heights = [draw.textbbox((0,0), line, font=font)[3] - draw.textbbox((0,0), line, font=font)[1] for line in lines]
        spacing = 15
        total_text_height = sum(line_heights) + (len(lines) - 1) * spacing
        
        if is_cover:
            # Covers are usually 1080x1080 or similar, center vertically in the right area
            current_y = (h - total_text_height) // 2
        else:
            # Backgrounds have a white band in middle. 
            # Reference shows it in the TOP half (above the band).
            # Band is approx at y=560, height=240? No, let's target y=0 to y=512 area.
            safe_area_h = 560 
            current_y = (safe_area_h - total_text_height) // 2 + 20 # Slight offset
            
        # Placement
        x_start = int(w * 0.45)
        text_color = (30, 30, 30) # Darker grey
        
        for line in lines:
            # Left aligned within the right section
            draw.text((x_start, current_y), line, font=font, fill=text_color)
            
            bbox = draw.textbbox((0, 0), line, font=font)
            current_y += (bbox[3] - bbox[1]) + spacing
            
        img.save(output_path, "JPEG", quality=95)
        print(f"Generated {'Cover' if is_cover else 'Background'}: {output_path}")
        return True

if __name__ == "__main__":
    # Test
    gen = ImageGenerator()
    gen.generate("Testing Automation Ep. 100", "test_out.jpeg")
