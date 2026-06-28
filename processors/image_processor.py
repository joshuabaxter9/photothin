from PIL import Image

def process_image(image_path):
    print(f"Processing Image: {image_path}")
    try:
        with Image.open(image_path) as image:
            image = image.convert("RGB")

            print(f"Image Processed: {image_path}")
            print(f"Size: {image.size}")
            print(f"Mode: {image.mode}\n")

        return image
    
    except Exception as error:
        print(f"Could not process image: {image_path}")
        print(f"Error: {error}\n")

    return None