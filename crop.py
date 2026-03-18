from PIL import Image

def adjust_margins(image_path):
    img = Image.open(image_path)
    width, height = img.size
    
    # 5cm top ~ 150px, 4cm bottom ~ 120px roughly (assuming 72-96 dpi)
    # Let's crop top 150px and bottom 120px
    top_crop = 150
    bottom_crop = 120
    
    # Check if image is tall enough
    if height > top_crop + bottom_crop:
        bbox = (0, top_crop, width, height - bottom_crop)
        img = img.crop(bbox)
        img.save(image_path)
        print(f"Cropped to: {img.size}")
    else:
        print("Image too small to crop that much.")

if __name__ == "__main__":
    adjust_margins("c:\\testpy\\coordinate_guide.png")
