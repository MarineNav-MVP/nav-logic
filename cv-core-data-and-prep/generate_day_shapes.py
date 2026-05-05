"""
Synthetic Day Shapes Generator
------------------------------
Generates marine scenes with day shapes (ball, diamond, etc.)
aligned with COLREG-72 configurations.
"""

import os
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path
from tqdm import tqdm
from typing import List, Tuple, Dict


class DayShapesGenerator:
    def __init__(self, output_dir: str, num_images: int = 2000, img_size: int = 1024):
        self.output_dir = Path(output_dir)
        self.num_images = num_images
        self.img_size = img_size
        self.classes = ["ball", "diamond", "cylinder", "cone_up", "cone_down"]
        self.train_ratio = 0.8
        
        # COLREG-72 Vessel Configurations
        self.configs = [
            {"name": "NUC", "main": ["ball", "ball"], "sides": []},
            {"name": "RAM", "main": ["ball", "diamond", "ball"], "sides": []},
            {"name": "CBD", "main": ["cylinder"], "sides": []},
            {"name": "Fishing", "main": ["cone_up", "cone_down"], "sides": []},
            {"name": "Fishing_150m", "main": ["cone_up", "cone_down"], "sides": [("right", ["cone_up"])]},
            {"name": "Dredging", "main": ["ball", "diamond", "ball"], "sides": [("left", ["ball", "ball"]), ("right", ["diamond", "diamond"])]},
            {"name": "Minesweeper", "main": ["ball"], "sides": [("left", ["ball"]), ("right", ["ball"])]},
            {"name": "Anchor", "main": ["ball"], "sides": []},
            {"name": "Sailing_Power", "main": ["cone_down"], "sides": []},
        ]

    def _create_folders(self):
        for split in ['train', 'val']:
            (self.output_dir / split / 'images').mkdir(parents=True, exist_ok=True)
            (self.output_dir / split / 'labels').mkdir(parents=True, exist_ok=True)

    def _get_background(self) -> Image.Image:
        """Generates a procedural sky/sea background."""
        base = Image.new('RGB', (self.img_size, self.img_size))
        draw = ImageDraw.Draw(base)
        horizon = random.randint(int(self.img_size * 0.45), int(self.img_size * 0.65))
        
        # Sky with gradient
        sky_top = (random.randint(50, 150), random.randint(100, 200), 255)
        sky_bottom = (200, 230, 255)
        for y in range(horizon):
            ratio = y / horizon
            color = tuple(int(sky_top[i] + (sky_bottom[i] - sky_top[i]) * ratio) for i in range(3))
            draw.line([(0, y), (self.img_size, y)], fill=color)
            
        # Sea
        sea_color = (random.randint(10, 40), random.randint(40, 80), random.randint(80, 130))
        draw.rectangle([0, horizon, self.img_size, self.img_size], fill=sea_color)
        return base

    def _draw_shape(self, draw: ImageDraw.Draw, shape_type: str, center: Tuple[int, int], size: Tuple[int, int]):
        """Draws a professional day shape with slight lighting effects."""
        cx, cy = center
        w, h = size
        x1, y1, x2, y2 = cx - w//2, cy - h//2, cx + w//2, cy + h//2
        
        color_base = random.randint(10, 35)
        fill = (color_base, color_base, color_base)
        outline = (color_base + 15, color_base + 15, color_base + 15)

        if shape_type == "ball":
            draw.ellipse([x1, y1, x2, y2], fill=fill, outline=outline)
        elif shape_type == "diamond":
            draw.polygon([(cx, y1), (x2, cy), (cx, y2), (x1, cy)], fill=fill, outline=outline)
        elif shape_type == "cylinder":
            draw.rectangle([x1, y1, x2, y2], fill=fill, outline=outline)
        elif shape_type == "cone_up":
            draw.polygon([(cx, y1), (x2, y2), (x1, y2)], fill=fill, outline=outline)
        elif shape_type == "cone_down":
            draw.polygon([(x1, y1), (x2, y1), (cx, y2)], fill=fill, outline=outline)

    def _generate_scene(self) -> Tuple[Image.Image, List[str]]:
        img = self._get_background()
        draw = ImageDraw.Draw(img)
        config = random.choice(self.configs)
        
        obj_w = random.randint(25, 55)
        gap = random.randint(8, 15)
        side_dist = random.randint(60, 100)
        
        center_x = random.randint(int(self.img_size * 0.2), int(self.img_size * 0.8))
        base_y = random.randint(int(self.img_size * 0.1), int(self.img_size * 0.3))
        
        yolo_labels = []
        
        # Main Mast
        curr_y = base_y
        for s_name in config['main']:
            draw_shape_pro = self._draw_shape(draw, s_name, (center_x, curr_y + obj_w//2), (obj_w, obj_w))
            cid = self.classes.index(s_name)
            yolo_labels.append(f"{cid} {center_x/self.img_size} {(curr_y + obj_w//2)/self.img_size} {obj_w/self.img_size} {obj_w/self.img_size}")
            curr_y += obj_w + gap
            
        # Side Masts
        for side_type, side_shapes in config['sides']:
            sx = center_x - side_dist if side_type == "left" else center_x + side_dist
            sy = base_y + random.randint(0, 40)
            curr_sy = sy
            for s_name in side_shapes:
                self._draw_shape(draw, s_name, (sx, curr_sy + obj_w//2), (obj_w, obj_w))
                cid = self.classes.index(s_name)
                yolo_labels.append(f"{cid} {sx/self.img_size} {(curr_sy + obj_w//2)/self.img_size} {obj_w/self.img_size} {obj_w/self.img_size}")
                curr_sy += obj_w + gap
            draw.line([(center_x, base_y), (sx, base_y+20)], fill=(40, 40, 40), width=1)
            
        return img, yolo_labels

    def run(self):
        self._create_folders()
        print(f"🎨 Generating {self.num_images} synthetic images...")
        
        for i in tqdm(range(self.num_images)):
            split = 'train' if i < self.num_images * self.train_ratio else 'val'
            img, labels = self._generate_scene()
            
            img_filename = f"img_{i:04d}.jpg"
            img.save(self.output_dir / split / 'images' / img_filename, quality=95)
            with open(self.output_dir / split / 'labels' / f"img_{i:04d}.txt", 'w') as f:
                f.write("\n".join(labels))
                
        # Generate data.yaml
        yaml_content = f"path: /content/{self.output_dir.name}\ntrain: train/images\nval: val/images\nnames:\n"
        for idx, name in enumerate(self.classes):
            yaml_content += f"  {idx}: {name}\n"
            
        with open(self.output_dir / "data.yaml", 'w') as f:
            f.write(yaml_content)
        
        print(f"✨ Successfully generated dataset in: {self.output_dir}")


if __name__ == "__main__":
    generator = DayShapesGenerator(output_dir="marine_day_shapes", num_images=1000)
    # generator.run()
