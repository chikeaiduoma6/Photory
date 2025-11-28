from PIL import Image, ExifTags
from pillow_heif import register_heif_opener
import os

# 让 Pillow 认识 HEIC/HEIF
register_heif_opener()

print("cwd =", os.getcwd())

img = Image.open("IMG_5197.HEIC")  # 文件名按你本地的来
exif = img.getexif()

print("exif object type:", type(exif))
print("exif length:", len(exif))

for k, v in exif.items():
    print(ExifTags.TAGS.get(k, k), ":", v)
