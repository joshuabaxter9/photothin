from services.file_scanner import scan_folder

def main():
    folder = input("Enter folder path: ")
    scan_folder(folder)

if __name__ == "__main__":
    main()