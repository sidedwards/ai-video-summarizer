import os
import yaml
import subprocess

def prompt_for_file(file_extension):
    while True:
        file_path = input(f"Please enter the full path to the {file_extension} file: ").strip()
        if not file_path:
            print("No file path entered. Exiting.")
            return None
        if os.path.isfile(file_path) and file_path.lower().endswith(file_extension):
            return file_path
        else:
            print(f"Invalid file path or not a {file_extension} file. Please try again.")

def execute_shell_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = process.communicate()
    return stdout.decode('utf-8').strip()

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

