import os
import yaml
import subprocess
from transcription_goal import TranscriptionGoal

def prompt_for_media_file():
    supported_extensions = ('.mp4', '.m4a', '.mp3', '.wav', '.avi', '.mov')
    while True:
        file_path = input(f"Please enter the full path to the audio or video file {supported_extensions}: ").strip()
        if not file_path:
            print("No file path entered. Exiting.")
            return None
        if os.path.isfile(file_path) and file_path.lower().endswith(supported_extensions):
            return file_path
        else:
            print(f"Invalid file path or unsupported file type. Please try again.")

def prompt_for_goal():
    print("Select a transcription goal:")
    for i, goal in enumerate(TranscriptionGoal, 1):
        print(f"{i}. {goal.value.replace('_', ' ').title()}")
    
    while True:
        try:
            choice = int(input("Enter the number of your choice: "))
            if 1 <= choice <= len(TranscriptionGoal):
                return list(TranscriptionGoal)[choice - 1]
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a number.")

def execute_shell_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = process.communicate()
    return stdout.decode('utf-8').strip()

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)
