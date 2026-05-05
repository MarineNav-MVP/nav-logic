"""
Dataset Preparation Script
--------------------------
Converts YOLO-formatted ship datasets into a binary classification dataset
by cropping objects and balancing classes.
"""

import os
import cv2
import yaml
import random
import shutil
from pathlib import Path
from tqdm import tqdm
from typing import List, Dict


class DatasetPreparer:
    def __init__(self, source_dir: str, output_dir: str):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.data_yaml = self.source_dir / "data.yaml"
        self.proportions = {'train': 0.7, 'valid': 0.2, 'test': 0.1}
        self.limit_not_sail = 160  # Max samples per non-sailboat category
        
        self.temp_crops = Path("temp_crops_storage")
        self.class_names = self._load_class_names()

    def _load_class_names(self) -> List[str]:
        if not self.data_yaml.exists():
            raise FileNotFoundError(f"Config file not found: {self.data_yaml}")
        with open(self.data_yaml, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)['names']

    def _extract_crops(self) -> None:
        """Iterates through YOLO dataset and saves individual object crops."""
        if self.temp_crops.exists():
            shutil.rmtree(self.temp_crops)
        
        for name in self.class_names:
            (self.temp_crops / name).mkdir(parents=True, exist_ok=True)

        print("✂️  Extracting crops from source YOLO dataset...")
        for split in ["train", "valid", "test"]:
            img_dir = self.source_dir / split / "images"
            lbl_dir = self.source_dir / split / "labels"
            
            if not img_dir.exists():
                continue
            
            images = list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png")) + list(img_dir.glob("*.jpeg"))
            for img_path in tqdm(images, desc=f"Processing {split}"):
                lbl_path = lbl_dir / (img_path.stem + ".txt")
                if not lbl_path.exists():
                    continue
                
                img = cv2.imread(str(img_path))
                if img is None:
                    continue
                
                height, width, _ = img.shape
                with open(lbl_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip().split()
                    # Parse YOLO labels (class, x_center, y_center, width, height)
                    for i in range(0, len(content), 5):
                        group = content[i:i+5]
                        if len(group) < 5:
                            continue
                        
                        try:
                            cls_idx, xc, yc, bw, bh = map(float, group)
                            # Convert YOLO format to pixel coordinates
                            x1 = int((xc - bw/2) * width)
                            y1 = int((yc - bh/2) * height)
                            x2 = int((xc + bw/2) * width)
                            y2 = int((yc + bh/2) * height)
                            
                            # Clamp coordinates to image boundaries
                            x1, y1 = max(0, x1), max(0, y1)
                            x2, y2 = min(width, x2), min(height, y2)
                            
                            if x2 <= x1 or y2 <= y1:
                                continue
                            
                            crop = img[y1:y2, x1:x2]
                            if crop.size > 0:
                                class_name = self.class_names[int(cls_idx)]
                                crop_name = f"{img_path.stem}_obj{i//5}.jpg"
                                output_path = self.temp_crops / class_name / crop_name
                                cv2.imwrite(str(output_path), crop)
                        except (ValueError, IndexError):
                            continue

    def _distribute_files(self, files: List[Path], class_name: str) -> None:
        """Splits files into train/valid/test folders based on proportions."""
        random.shuffle(files)
        n = len(files)
        
        train_end = int(n * self.proportions['train'])
        valid_end = int(n * (self.proportions['train'] + self.proportions['valid']))
        
        splits = {
            'train': files[:train_end],
            'valid': files[train_end:valid_end],
            'test': files[valid_end:]
        }
        
        for split_name, split_files in splits.items():
            target_path = self.output_dir / split_name / class_name
            target_path.mkdir(parents=True, exist_ok=True)
            for file_path in split_files:
                shutil.copy(file_path, target_path / file_path.name)

    def run(self) -> None:
        """Executes the full dataset preparation pipeline."""
        self._extract_crops()
        
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        
        print("📂 Organizing binary classes and balancing data...")
        
        # 1. Collect all sailboat images
        sail_dir = self.temp_crops / "Sailboat"
        sail_files = list(sail_dir.glob("*.jpg")) if sail_dir.exists() else []
        
        # 2. Collect and balance non-sailboat images
        not_sail_files = []
        for class_dir in self.temp_crops.iterdir():
            if class_dir.is_dir() and class_dir.name != "Sailboat":
                imgs = list(class_dir.glob("*.jpg"))
                # Sample up to limit_not_sail images to prevent extreme imbalance
                sampled = random.sample(imgs, min(len(imgs), self.limit_not_sail))
                not_sail_files.extend(sampled)

        # 3. Distribute files into train/valid/test splits
        self._distribute_files(sail_files, "sailboat")
        self._distribute_files(not_sail_files, "not_sailboat")

        # Cleanup temporary storage
        if self.temp_crops.exists():
            shutil.rmtree(self.temp_crops)
            
        print(f"✨ Successfully created binary dataset at: {self.output_dir}")


if __name__ == "__main__":
    preparer = DatasetPreparer(source_dir="source_dataset", output_dir="binary_dataset")
    # preparer.run()
