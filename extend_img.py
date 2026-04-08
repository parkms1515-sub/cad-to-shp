from PIL import Image, ImageDraw, ImageFont

def combine_images():
    base = Image.open("c:\\testpy\\coordinate_guide.png")
    if base.mode != 'RGB': base = base.convert('RGB')
    
    extra = Image.open("C:\\Users\\kfca\\.gemini\\antigravity\\brain\\d46d4237-82b7-4223-a728-f597a8776140\\map_template_wrong_1773365756767.png")
    if extra.mode != 'RGB': extra = extra.convert('RGB')
    
    bw, bh = base.size
    
    # 4th box is red-themed warning section. 
    # Let's resize extra image to match the height or proportional height.
    # The height of base is bh.
    ew, eh = extra.size
    ratio = (bh - 140) / eh
    new_ew = int(ew * ratio)
    new_eh = int(eh * ratio)
    
    extra = extra.resize((new_ew, new_eh), Image.Resampling.LANCZOS)
    
    box_width = new_ew + 40
    space = 80
    
    new_width = bw + space + box_width
    new_img = Image.new('RGB', (new_width, bh), (255, 255, 255))
    new_img.paste(base, (0, 0))
    
    # Draw red box
    draw = ImageDraw.Draw(new_img)
    x0, y0 = bw + space, 0
    x1, y1 = new_width, bh
    
    # Box with shadow/outline
    draw.rounded_rectangle([x0, y0, x1, y1], radius=20, fill="#ffffff", outline="#E53935", width=4)
    # Header
    draw.rounded_rectangle([x0, y0, x1, y0 + 60], radius=20, fill="#E53935")
    draw.rectangle([x0, y0 + 30, x1, y0 + 60], fill="#E53935") # clear bottom curves
    
    try:
        font_title = ImageFont.truetype("malgun.ttf", 24)
        font_body = ImageFont.truetype("malgun.ttf", 18)
    except:
        font_title = font_body = ImageFont.load_default()
        
    draw.text((x0 + 15, y0 + 15), "❌ 템플릿 이동/스케일 변경", fill="white", font=font_title)
    
    # Paste the sample icon map inside
    new_img.paste(extra, (x0 + 20, y0 + 70))
    
    # Add body text below image
    text = "도면 서식(템플릿)으로\n옮기기 위해 스케일 축소/확대\n또는 객체 이동 시 좌표 틀어짐 발생\n→ 절대 금지!"
    draw.text((x0 + 10, y0 + 70 + new_eh + 10), text, fill="#333333", font=font_body, spacing=6)
    
    new_img.save("c:\\testpy\\coordinate_guide_extended.png")
    print(f"Created new image at width {new_width}")

if __name__ == "__main__":
    combine_images()
