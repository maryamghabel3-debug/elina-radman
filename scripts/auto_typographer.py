import sys
import os
import textwrap
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

def create_persian_text_slide(bg_color_img_path, output_path, text_content):
    try:
        base_img = Image.open(bg_color_img_path).convert("RGB")
        bg_color = base_img.getpixel((10, 10))
        
        img_w, img_h = 1080, 1350
        slide = Image.new("RGB", (img_w, img_h), bg_color)
        draw = ImageDraw.Draw(slide)
        
        font_path = "/home/user/assets/fonts/Vazirmatn-Regular.ttf"
        font_size = 55
        font = ImageFont.truetype(font_path, font_size)
        
        # FIX RTL ISSUES:
        # 1. We must apply bidi (RTL conversion) ONLY AFTER wrapping the text lines.
        # Otherwise, the bidi algorithm reverses the entire paragraph block before it gets cut into lines,
        # which scrambles the reading order.
        
        lines = text_content.strip().split('\n')
        final_display_lines = []
        
        for line in lines:
            if line.strip() == "":
                final_display_lines.append("") 
                continue
            
            # Wrap the raw string FIRST
            wrapped_segments = textwrap.wrap(line, width=40)
            
            # Then apply Arabic Reshaper and Bidi to EACH individual segment independently
            for segment in wrapped_segments:
                reshaped_text = arabic_reshaper.reshape(segment)
                bidi_text = get_display(reshaped_text)
                final_display_lines.append(bidi_text)
                
        line_height = font_size * 2.0 
        total_text_height = len(final_display_lines) * line_height
        
        y_text = (img_h - total_text_height) // 2
        
        for line in final_display_lines:
            if line == "":
                y_text += line_height
                continue
                
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x_text = (img_w - text_w) // 2
            
            shadow_offset = 3
            draw.text((x_text + shadow_offset, y_text + shadow_offset), line, font=font, fill=(0, 0, 0, 100))
            draw.text((x_text, y_text), line, font=font, fill=(255, 255, 255, 255))
            
            y_text += line_height
            
        slide.save(output_path, quality=100)
        print(f"✅ Slide generated successfully: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error generating slide: {e}")
        return False

if __name__ == "__main__":
    slide_text = """ما نسلی هستیم که استادِ پنهان کردنیم.

یاد گرفتیم چطور با قلبی که تند می‌زنه،
کاملاً خونسرد قهوه بخوریم."""
    
    os.makedirs("/home/user/images/auto_slides", exist_ok=True)
    create_persian_text_slide("/home/user/images/elina_profile_cropped_v2.jpg", 
                            "/home/user/images/auto_slides/Auto_Slide_2_Fixed.jpg", 
                            slide_text)
