from PIL import Image, ImageDraw, ImageFont
import urllib.request
import io

def create_grouped_infographic():
    # Load old image to extract icons
    try:
        old_img = Image.open("c:\\testpy\\coordinate_guide_extended.png")
        if old_img.mode != 'RGB':
            old_img = old_img.convert('RGB')
        
        # Old image dimensions are roughly 1100x370.
        # Box width was ~213 for first three boxes.
        icon1 = old_img.crop((70, 70, 70+160, 70+150))
        icon2 = old_img.crop((350, 70, 350+160, 70+150))
        icon3 = old_img.crop((650, 70, 650+160, 70+150))
        icon4 = old_img.crop((920, 70, 920+160, 70+150)) # Map template with red X
    except:
        icon1 = icon2 = icon3 = icon4 = None

    # Dimensions for high-res
    box_w = 280
    box_h = 360 # Increased by ~2cm (70px) from 290
    space = 60
    margin = 50
    
    total_w = margin*2 + box_w*4 + space*3 + 80
    total_h = margin*2 + box_h + 40
    
    img = Image.new('RGB', (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype("malgunbd.ttf", 22)  # Bold for title
        font_body = ImageFont.truetype("malgun.ttf", 18)
        font_arrow = ImageFont.truetype("malgunbd.ttf", 55)
        font_group = ImageFont.truetype("malgunbd.ttf", 20)
    except:
        font_title = font_body = font_arrow = font_group = ImageFont.load_default()
        
    # Group box around 1, 2, 3
    grp_x0 = margin - 20
    grp_y0 = margin - 35
    grp_x1 = margin + box_w*3 + space*2 + 20
    grp_y1 = margin + box_h + 20
    
    draw.rounded_rectangle([grp_x0, grp_y0, grp_x1, grp_y1], radius=20, fill="#F8FAFC", outline="#94A3B8", width=3)
    draw.text((grp_x0 + 20, grp_y0 + 10), "📌 정상적인 작업 흐름", fill="#475569", font=font_group)
    
    boxes = [
        {
            "color": "#1976D2", # Blue
            "title": "Base도면구성\n(수치지형도 or 지적도)",
            "body": "좌표정보가 있는 국가공간정보포털\nor 브이월드에서 다운로드한 도면"
        },
        {
            "color": "#388E3C", # Green
            "title": "CAD 작업",
            "body": "다운로드 도면 위에 측량·설계\n작업 진행 → 다운로드 도면\n좌표계 유지"
        },
        {
            "color": "#F57C00", # Orange
            "title": "DXF 파일 저장",
            "body": "DXF2007 버전 이하로 저장\nCAD좌표값이 그대로 유지된\n상태로 내보내기"
        },
        {
            "color": "#D32F2F", # Red
            "title": "❌ 절대 금지",
            "body": "템플릿 입력과정에서\n스케일, 이동, 회전 등이\n진행되면 변환불가"
        }
    ]
    
    icons = [icon1, icon2, icon3, icon4]
    
    for i, b in enumerate(boxes):
        if i < 3:
            x0 = margin + i * (box_w + space)
            y0 = margin + 10
        else:
            x0 = margin + i * (box_w + space) + 40 # offset for 4th box
            y0 = margin + 10
            
        x1 = x0 + box_w
        y1 = y0 + box_h
        
        # Draw box
        draw.rounded_rectangle([x0, y0, x1, y1], radius=15, fill="#FFFFFF", outline=b["color"], width=4)
        draw.rounded_rectangle([x0, y0, x1, y0 + 90], radius=15, fill=b["color"])
        draw.rectangle([x0, y0 + 70, x1, y0 + 90], fill=b["color"])
        
        # Center title
        lines = b["title"].split('\n')
        ty = y0 + 20
        if len(lines) == 1:
            ty += 15
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_title)
            tw = bbox[2] - bbox[0]
            draw.text((x0 + (box_w - tw)//2, ty), line, fill="white", font=font_title)
            ty += 30
            
        # Paste Icon if present
        if icons[i]:
            ic = icons[i]
            ic_w, ic_h = ic.size
            # Draw placeholder circle if icon fails
            cx = x0 + box_w//2
            cy = y0 + 170
            
            # Simple resize to fit the vertical space nicely
            ratio = 110 / ic_h
            new_ic_w = int(ic_w * ratio)
            new_ic_h = int(ic_h * ratio)
            ic_small = ic.resize((new_ic_w, new_ic_h), Image.Resampling.LANCZOS)
            
            img.paste(ic_small, (cx - new_ic_w//2, cy - new_ic_h//2))
            
        # Draw body text
        lines = b["body"].split('\n')
        by = y0 + 250 # moved down
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_body)
            tw = bbox[2] - bbox[0]
            draw.text((x0 + (box_w - tw)//2, by), line, fill="#333333", font=font_body)
            by += 28
            
        # Draw arrow to the next box (only inside group)
        if i < 2:
            arrow_str = "▶"
            abbox = draw.textbbox((0, 0), arrow_str, font=font_arrow)
            aw = abbox[2] - abbox[0]
            ax = x1 + (space - aw)//2
            draw.text((ax, y0 + box_h//2 - 20), arrow_str, fill="#64748B", font=font_arrow)

    # Save
    img.save("c:\\testpy\\coordinate_guide_final_grouped.png")
    print("Grouped infographic created successfully")

if __name__ == "__main__":
    create_grouped_infographic()
