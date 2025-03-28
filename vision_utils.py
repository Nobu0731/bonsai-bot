import os
from google.cloud import vision

def analyze_image_from_bytes(image_bytes: bytes) -> list:
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    response = client.label_detection(image=image)
    if response.error.message:
        raise Exception(f"Vision API error: {response.error.message}")
    return [label.description for label in response.label_annotations]
