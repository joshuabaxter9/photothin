from services.file_scanner import scan_folder

def main():
    # if you want to manually enter folderpath
    #folder = input("Enter folder path: ")

    # hardcoded folder path
    folder = "test_folders/photos"
    scan_folder(folder)

if __name__ == "__main__":
    main()