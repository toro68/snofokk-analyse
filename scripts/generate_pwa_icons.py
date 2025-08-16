#!/usr/bin/env python3
"""
Generate PWA icons for the Snøfokk Varsling app
Creates icons in different sizes with a weather-themed design
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_weather_icon(size: int, output_path: str):
    """Create a weather-themed icon for the PWA"""
    
    # Create base image with gradient background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background gradient (blue to lighter blue)
    for i in range(size):
        alpha = i / size
        color = (
            int(102 + (135-102) * alpha),  # 667eea to lighter blue
            int(126 + (160-126) * alpha),
            int(234 + (255-234) * alpha),
            255
        )
        draw.line([(0, i), (size, i)], fill=color)
    
    # Calculate sizes based on icon size
    margin = size // 10
    center_x, center_y = size // 2, size // 2
    
    # Draw snowflake symbol
    snowflake_size = size // 3
    
    # Main snowflake lines
    line_width = max(2, size // 50)
    
    # Vertical line
    draw.line([
        (center_x, center_y - snowflake_size),
        (center_x, center_y + snowflake_size)
    ], fill='white', width=line_width)
    
    # Horizontal line
    draw.line([
        (center_x - snowflake_size, center_y),
        (center_x + snowflake_size, center_y)
    ], fill='white', width=line_width)
    
    # Diagonal lines
    diag_offset = int(snowflake_size * 0.7)
    draw.line([
        (center_x - diag_offset, center_y - diag_offset),
        (center_x + diag_offset, center_y + diag_offset)
    ], fill='white', width=line_width)
    
    draw.line([
        (center_x - diag_offset, center_y + diag_offset),
        (center_x + diag_offset, center_y - diag_offset)
    ], fill='white', width=line_width)
    
    # Add small decorative elements at snowflake tips
    tip_size = max(2, size // 30)
    for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
        import math
        x = center_x + int(snowflake_size * 0.8 * math.cos(math.radians(angle)))
        y = center_y + int(snowflake_size * 0.8 * math.sin(math.radians(angle)))
        
        draw.ellipse([
            (x - tip_size, y - tip_size),
            (x + tip_size, y + tip_size)
        ], fill='white')
    
    # Add wind effect (curved lines)
    wind_offset = size // 4
    wind_length = size // 6
    wind_thickness = max(1, size // 80)
    
    # Right side wind lines
    for i in range(3):
        y_pos = center_y + (i - 1) * wind_offset // 2
        x_start = center_x + snowflake_size + margin
        if x_start < size - margin:
            draw.arc([
                (x_start, y_pos - wind_length // 2),
                (x_start + wind_length, y_pos + wind_length // 2)
            ], start=0, end=180, fill='white', width=wind_thickness)
    
    # Save the icon
    img.save(output_path, 'PNG')
    print(f"✅ Created icon: {output_path} ({size}x{size})")

def create_favicon():
    """Create a simple favicon.ico"""
    # Create a 32x32 version for favicon
    img = Image.new('RGBA', (32, 32), (102, 126, 234, 255))
    draw = ImageDraw.Draw(img)
    
    # Simple snowflake
    center = 16
    draw.line([(16, 4), (16, 28)], fill='white', width=2)
    draw.line([(4, 16), (28, 16)], fill='white', width=2)
    draw.line([(8, 8), (24, 24)], fill='white', width=2)
    draw.line([(8, 24), (24, 8)], fill='white', width=2)
    
    return img

def main():
    """Generate all required PWA icons"""
    
    # Ensure static directory exists
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    os.makedirs(static_dir, exist_ok=True)
    
    print("🎨 Generating PWA icons for Snøfokk Varsling...")
    
    # Standard PWA icon sizes
    icon_sizes = [192, 512]
    
    for size in icon_sizes:
        output_path = os.path.join(static_dir, f'icon-{size}.png')
        create_weather_icon(size, output_path)
    
    # Additional useful sizes
    additional_sizes = [72, 96, 128, 144, 152, 180, 384]
    
    for size in additional_sizes:
        output_path = os.path.join(static_dir, f'icon-{size}.png')
        create_weather_icon(size, output_path)
    
    # Create favicon
    favicon_path = os.path.join(static_dir, 'favicon.ico')
    favicon_img = create_favicon()
    favicon_img.save(favicon_path, 'ICO')
    print(f"✅ Created favicon: {favicon_path}")
    
    # Create apple touch icon (180x180 is the standard size)
    apple_icon_path = os.path.join(static_dir, 'apple-touch-icon.png')
    create_weather_icon(180, apple_icon_path)
    
    print("🎉 All PWA icons generated successfully!")
    print("\nGenerated files:")
    for file in os.listdir(static_dir):
        if file.startswith('icon-') or file in ['favicon.ico', 'apple-touch-icon.png']:
            print(f"  - {file}")

if __name__ == "__main__":
    main()
