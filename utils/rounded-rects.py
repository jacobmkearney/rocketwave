from PIL import Image, ImageDraw

def make_card(filename, size=256, radius=40):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))  # Transparent background
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [(0, 0), (size, size)], radius=radius, fill=(255, 255, 255, 255)
    )
    img.save(filename, "PNG")

# Card version (small radius)
make_card("card.png", size=256, radius=30)

# Pill version (large radius)
make_card("pill.png", size=256, radius=128)
