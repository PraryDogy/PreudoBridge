import subprocess

def get_folder_size(path: str) -> int | None:
    applescript_file = "scripts/get_folder_size.scpt"
    script_command = ['osascript', applescript_file, path]
    try:
        result = subprocess.check_output(script_command).decode().strip()
        return float(result)
    except subprocess.CalledProcessError as e:
        print(f"Error executing AppleScript: {e.output.decode().strip()}")
        return 0

# Пример использования
folder_path = "/Users/Morkowik/Desktop"
size = get_folder_size(folder_path)