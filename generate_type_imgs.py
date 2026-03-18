from PIL import Image, ImageDraw, ImageFont
import math
import os

def create_image(filename, title, draw_shape_func):
    """더 현대적이고 세련된 스타일의 다이어그램 생성 (설명 포함)"""
    w, h = 500, 300 # 텍스트 공간을 위해 높이 약간 조정
    img = Image.new('RGB', (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # 세련된 배경 카드 스타일
    draw.rounded_rectangle([2, 2, w-2, h-2], radius=16, fill="#F1F5F9", outline="#E2E8F0", width=1)
    draw.rounded_rectangle([10, 10, w-10, h-10], radius=12, fill="#FFFFFF", outline=None)
    
    # 폰트 설정 (한글 지원)
    try:
        font_title = ImageFont.truetype("malgun.ttf", 20)
    except:
        font_title = ImageFont.load_default()
    
    # 제목 추가
    draw.text((30, 25), title, fill="#1E293B", font=font_title)
    
    # 다이어그램 그리기
    draw_shape_func(draw, w, h)
    
    output_path = os.path.join("c:\\testpy", filename)
    img.save(output_path)
    print(f"Created {filename}")

def draw_arrow(draw, x, y, size=30):
    """더 세련된 화살표 그리기"""
    color = "#94A3B8"
    draw.polygon([(x-size/2, y-size/3), (x+size/2, y), (x-size/2, y+size/3)], fill=color)

def draw_a(draw, w, h):
    # ⓐ 영역 -> 폴리곤
    cx, cy = w//2, h//2 + 20
    pts = [(cx-150, cy-50), (cx-50, cy-60), (cx-30, cy+50), (cx-130, cy+70)]
    draw.polygon(pts, fill=None, outline="#3B82F6", width=4)
    for px, py in pts:
        draw.ellipse([px-5, py-5, px+5, py+5], fill="#FFFFFF", outline="#3B82F6", width=2)
    draw_arrow(draw, cx, cy, 30)
    pts_after = [(x+180, y) for x, y in pts]
    draw.polygon(pts_after, fill="#DBEAFE", outline="#2563EB", width=4)
    for px, py in pts_after:
        draw.ellipse([px-5, py-5, px+5, py+5], fill="#FFFFFF", outline="#2563EB", width=2)

def draw_b(draw, w, h):
    # ⓑ 라인 -> 버퍼
    cx, cy = w//2, h//2 + 20
    pts = [(cx-150, cy-40), (cx-100, cy+40), (cx-50, cy-20)]
    draw.line(pts, fill="#10B981", width=6, joint="round")
    draw_arrow(draw, cx, cy, 30)
    pts_after = [(x+180, y) for x, y in pts]
    draw.line(pts_after, fill="#D1FAE5", width=36, joint="round")
    draw.line(pts_after, fill="#10B981", width=4, joint="round")

def draw_c(draw, w, h):
    # ⓒ 포인트 -> 라인 -> 폴리곤
    cx, cy = w//2, h//2 + 20
    pts = [(cx-150, cy-50), (cx-70, cy-60), (cx-50, cy+40), (cx-130, cy+60)]
    for px, py in pts:
        draw.ellipse([px-7, py-7, px+7, py+7], fill="#F59E0B")
    draw_arrow(draw, cx, cy, 30)
    pts_after = [(x+180, y) for x,y in pts]
    draw.polygon(pts_after, fill="#FEF3C7", outline="#D97706", width=4)
    for px, py in pts_after:
        draw.ellipse([px-7, py-7, px+7, py+7], fill="#F59E0B")

def draw_d(draw, w, h):
    # ⓓ 포인트 -> 폴리곤
    cx, cy = w//2, h//2 + 20
    px, py = cx-90, cy
    draw.ellipse([px-10, py-10, px+10, py+10], fill="#EF4444")
    draw_arrow(draw, cx, cy, 30)
    target_cx, target_cy = cx+90, cy
    radius = 70
    poly_pts = []
    for i in range(8):
        angle = math.radians(i * 45)
        poly_pts.append((target_cx + radius * math.cos(angle), target_cy + radius * math.sin(angle)))
    draw.polygon(poly_pts, fill="#FEE2E2", outline="#DC2626", width=4)
    draw.ellipse([target_cx-6, target_cy-6, target_cx+6, target_cy+6], fill="#EF4444")

if __name__ == "__main__":
    create_image("type_a.png", "ⓐ 영역 → 폴리곤 변환 (닫힌 선을 면으로)", draw_a)
    create_image("type_b.png", "ⓑ 라인 → 버퍼 적용 (선에 두께를 주어 면으로)", draw_b)
    create_image("type_c.png", "ⓒ 포인트 → 라인 → 폴리곤 (점들을 이어 면으로)", draw_c)
    create_image("type_d.png", "ⓓ 포인트 → 폴리곤 (점들을 꼭짓점으로 면 생성)", draw_d)
