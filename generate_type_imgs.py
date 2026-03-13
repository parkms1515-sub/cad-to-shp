from PIL import Image, ImageDraw, ImageFont
import math

def create_image(filename, title, draw_shape_func):
    w, h = 400, 200
    img = Image.new('RGB', (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Background and border
    draw.rounded_rectangle([10, 10, w-10, h-10], radius=10, fill="#f8f9fa", outline="#e9ecef", width=2)
    
    # Title
    try:
        font = ImageFont.truetype("malgun.ttf", 18)
    except:
        font = ImageFont.load_default()
    
    draw.text((20, 20), title, fill="#333", font=font)
    
    # Draw specific shape
    draw_shape_func(draw, w, h)
    
    img.save(f"c:\\testpy\\{filename}")
    print(f"Created {filename}")

def draw_a(draw, w, h):
    # ⓐ 영역을 폴리곤으로 변환 (Closed polyline to solid polygon)
    cx, cy = w//2, h//2 + 10
    pts = [(cx-60, cy-40), (cx+60, cy-50), (cx+80, cy+40), (cx-40, cy+60)]
    # Outline only (Left) -> Solid (Right)
    
    # Let's draw before and after
    # Before (left)
    draw.polygon([(x-100, y) for x,y in pts], fill=None, outline="#1976D2", width=3)
    
    # Arrow
    draw.text((cx-10, cy-15), "▶", fill="#9e9e9e", font=ImageFont.truetype("malgun.ttf", 30) if True else None)
    
    # After (right)
    draw.polygon([(x+100, y) for x,y in pts], fill="#bbdefb", outline="#1976D2", width=3)

def draw_b(draw, w, h):
    # ⓑ 라인을 버퍼 적용 (Line to thick buffered polygon)
    cx, cy = w//2, h//2 + 10
    pts = [(cx-50, cy-30), (cx, cy+30), (cx+50, cy-10)]
    
    # Before
    draw.line([(x-100, y) for x,y in pts], fill="#388E3C", width=4)
    
    # Arrow
    draw.text((cx-10, cy-15), "▶", fill="#9e9e9e", font=ImageFont.truetype("malgun.ttf", 30) if True else None)
    
    # After
    # Draw thick line as buffer
    draw.line([(x+100, y) for x,y in pts], fill="#c8e6c9", width=24)
    draw.line([(x+100, y) for x,y in pts], fill="#388E3C", width=2) # Center line

def draw_c(draw, w, h):
    # ⓒ 포인트-라인-폴리곤 (Points to connected lines to filled polygon)
    cx, cy = w//2, h//2 + 10
    pts = [(cx-50, cy-40), (cx+30, cy-50), (cx+50, cy+30), (cx-40, cy+50)]
    
    # Before
    for x, y in pts:
        draw.ellipse([x-100-5, y-5, x-100+5, y+5], fill="#E65100")
        
    # Arrow
    draw.text((cx-10, cy-15), "▶", fill="#9e9e9e", font=ImageFont.truetype("malgun.ttf", 30) if True else None)
    
    # After
    draw.polygon([(x+100, y) for x,y in pts], fill="#ffe0b2", outline="#E65100", width=3)
    for x, y in pts:
        draw.ellipse([x+100-5, y-5, x+100+5, y+5], fill="#E65100")

def draw_d(draw, w, h):
    # ⓓ 포인트를 폴리곤으로 (Point with 8-point octagonal buffer)
    cx, cy = w//2, h//2 + 10
    
    # Before: Single point
    draw.ellipse([cx-100-6, cy-6, cx-100+6, cy+6], fill="#D32F2F")
    
    # Arrow
    draw.text((cx-10, cy-15), "▶", fill="#9e9e9e", font=ImageFont.truetype("malgun.ttf", 30) if True else None)
    
    # After: Octagonal buffer
    radius = 50
    pts = []
    for i in range(8):
        angle = math.radians(i * 45) # 45 degree steps for octagon
        x = cx + 100 + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        pts.append((x, y))
    
    draw.polygon(pts, fill="#ffcdd2", outline="#D32F2F", width=2)
    draw.ellipse([cx+100-4, cy-4, cx+100+4, cy+4], fill="#D32F2F") # Center point reference

if __name__ == "__main__":
    create_image("type_a.png", "ⓐ 영역 → 폴리곤 변환 (닫힌 선을 면으로)", draw_a)
    create_image("type_b.png", "ⓑ 라인 → 버퍼 적용 (선에 두께를 주어 면으로)", draw_b)
    create_image("type_c.png", "ⓒ 포인트 → 라인 → 폴리곤 (점들을 이어 면으로)", draw_c)
    create_image("type_d.png", "ⓓ 포인트 → 폴리곤 (점들을 꼭짓점으로 면 생성)", draw_d)
