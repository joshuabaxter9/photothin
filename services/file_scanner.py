from pathlib import Path

def scan_folder(folder_path):
    path = Path(folder_path)

    for file in path.iterdir():
        print(file.name)