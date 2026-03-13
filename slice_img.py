import sys
from PIL import Image

def modify_image(image_path):
    img = Image.open(image_path)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    width, height = img.size
    
    # 하단 15% 정도(주의 문구)를 잘라냅니다.
    # 경고창의 대략적 크기를 고려해 18% 정도를 잘라봅니다.
    bottom_crop = int(height * 0.18)
    img = img.crop((0, 0, width, height - bottom_crop))
    width, height = img.size
    
    # 1/3, 2/3 지점에서 분할
    w3 = width // 3
    part1 = img.crop((0, 0, w3, height))
    part2 = img.crop((w3, 0, w3*2, height))
    part3 = img.crop((w3*2, 0, width, height))
    
    # 3cm 정도(약 100px)의 공백 
    space = 80
    new_width = width + space * 2
    new_img = Image.new('RGB', (new_width, height), (255, 255, 255))
    
    new_img.paste(part1, (0, 0))
    new_img.paste(part2, (w3 + space, 0))
    new_img.paste(part3, (w3*2 + space*2, 0))
    
    new_img.save(image_path)
    print("Image modified successfully")

if __name__ == "__main__":
    modify_image("c:\\testpy\\coordinate_guide.png")
