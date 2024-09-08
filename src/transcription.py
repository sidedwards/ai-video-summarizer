import requests
import time
from utils import execute_shell_command

def transcribe_audio(video_file, config):
    s3_upload_command = f"{config['aws_cli_path']} s3 cp {video_file} s3://{config['s3_bucket']}/public/{video_file}"
    execute_shell_command(s3_upload_command)

    s3_presign_command = f"{config['aws_cli_path']} s3 presign s3://{config['s3_bucket']}/public/{video_file}"
    presigned_url = execute_shell_command(s3_presign_command)

    headers = {
        "Authorization": f"Bearer {config['replicate_api_key']}",
        "Content-Type": "application/json"
    }
    data = {
        "version": config['replicate_model_version'],
        "input": {
            "debug": False,
            "language": "en",
            "vad_onset": 0.5,
            "audio_file": presigned_url,
            "batch_size": 64,
            "vad_offset": 0.363,
            "diarization": False,
            "temperature": 0,
            "align_output": False,
            "huggingface_access_token": config['huggingface_token'],
            "language_detection_min_prob": 0,
            "language_detection_max_tries": 5
        }
    }

    response = requests.post(config['replicate_api_url'], headers=headers, json=data)
    prediction = response.json()

    prediction_url = prediction['urls']['get']
    while True:
        response = requests.get(prediction_url, headers=headers)
        status = response.json()['status']

        if status == "succeeded":
            segments = response.json()['output']['segments']
            break
        elif status == "failed":
            raise Exception("Transcription process failed.")
        else:
            time.sleep(5)

    transcript = " ".join(segment['text'] for segment in segments)
    return transcript

