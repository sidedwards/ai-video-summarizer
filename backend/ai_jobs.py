import json
import time
import os
import re

import requests

from log import logger
from transcription_goal import TranscriptionGoal


def start_transcription(url, config):
    logger.debug(f"Starting transcription for URL: {url}")
    headers = {
        "Authorization": f"Bearer {config['replicate_api_key']}",
        "Content-Type": "application/json",
    }
    data = {
        "version": config["replicate_model_version"],
        "input": {
            "debug": False,
            "language": "en",
            "vad_onset": 0.5,
            "audio_file": url,
            "batch_size": 64,
            "vad_offset": 0.363,
            "diarization": False,
            "temperature": 0,
            "align_output": False,
            "huggingface_access_token": config["huggingface_token"],
            "language_detection_min_prob": 0,
            "language_detection_max_tries": 5,
        },
    }
    logger.debug(f"Sending request to Replicate API: {config['replicate_api_url']}")
    response = requests.post(config["replicate_api_url"], headers=headers, json=data)
    logger.debug(f"Replicate API response: {response.text}")
    return response.json()


def get_transcription_result(prediction_url, config):
    logger.debug(f"Getting transcription result from: {prediction_url}")
    headers = {"Authorization": f"Bearer {config['replicate_api_key']}"}
    while True:
        response = requests.get(prediction_url, headers=headers)
        result = response.json()
        logger.debug(f"Transcription status: {result['status']}")
        if result["status"] == "succeeded":
            logger.info("Transcription completed successfully")
            return result["output"]["segments"]
        elif result["status"] == "failed":
            logger.error("Transcription process failed")
            raise Exception("Transcription process failed.")
        time.sleep(5)


def generate_content(transcript, goal, config):
    logger.debug(f"Generating content for goal: {goal.value}")
    headers = {
        "x-api-key": config["anthropic_api_key"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    prompts = {
        TranscriptionGoal.MEETING_MINUTES: "Create very detailed meeting minutes based on the following transcription:",
        TranscriptionGoal.PODCAST_SUMMARY: "Summarize this podcast episode, highlighting key points and interesting discussions:",
        TranscriptionGoal.LECTURE_NOTES: "Create comprehensive lecture notes from this transcription, organizing key concepts and examples:",
        TranscriptionGoal.INTERVIEW_HIGHLIGHTS: "Extract the main insights and notable quotes from this interview transcription:",
        TranscriptionGoal.GENERAL_TRANSCRIPTION: "Provide a clear and concise summary of the main points discussed in this transcription:",
    }

    prompt = prompts.get(goal, prompts[TranscriptionGoal.GENERAL_TRANSCRIPTION])

    data = {
        "model": config["anthropic_model"],
        "temperature": 0,
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": f"{prompt} {json.dumps(transcript)}"}],
    }
    logger.debug(f"Sending request to Anthropic API: {config['anthropic_api_url']}")
    response = requests.post(config["anthropic_api_url"], headers=headers, json=data)
    print(response)
    logger.debug(f"Anthropic API response: {response.text}")

    # Log the full AI response
    logger.debug(
        f"Full AI response for content generation:\n{response.json()['content'][0]['text']}"
    )

    return response.json()["content"][0]["text"]


def create_media_clips(transcript, content, source_file, dest_folder, goal, config):
    logger.debug(f"Creating media clips for goal: {goal.value}")
    topic_extraction_message = f"""
    Based on the following {goal.value.replace('_', ' ')}:
    {content}

    Extract each of the main topics or segments discussed.

    For each topic/segment, provide:
    1. A short, descriptive title (max 5 words)
    2. A list of related keywords (max 5 keywords)

    Format the response as a JSON array of objects, each containing 'title' and 'keywords' fields.
    """
    headers = {
        "x-api-key": config['anthropic_api_key'],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    topic_extraction_data = {
        "model": config['anthropic_model'],
        "max_tokens": 1000,
        "messages": [
            {"role": "user", "content": topic_extraction_message}
        ]
    }
    topic_response = requests.post(config['anthropic_api_url'], headers=headers, json=topic_extraction_data)
    topic_text = topic_response.json()['content'][0]['text']
    logger.debug(f"Full AI response for topic extraction:\n{topic_text}")

    try:
        topics = json.loads(topic_text)
    except json.JSONDecodeError:
        topic_pattern = r'\{\s*"title":\s*"([^"]+)",\s*"keywords":\s*\[((?:[^]]+))\]\s*\}'  
        matches = re.findall(topic_pattern, topic_text)
        topics = [{"title": title, "keywords": [k.strip(' "') for k in keywords.split(',')]} for title, keywords in matches]

    if not topics:
        raise ValueError("Failed to extract topics from the AI response")

    clip_generation_message = f"""
    For each of the following topics/segments, find the most relevant part in the transcript:
    {json.dumps(topics)}

    Transcript:
    {json.dumps(transcript)}

    For each topic/segment:
    1. Find the part that best represents the topic/segment.
    2. Aim for a clip duration of 2-5 minutes, but prioritize capturing the complete discussion or segment.
    3. If the relevant content exceeds 5 minutes, include it entirely to avoid cutting off important information.
    4. Ensure that the segment captures complete thoughts and ideas. Do not cut off in the middle of a sentence or a speaker's point.
    5. It's better to include slightly more content than to risk cutting off important information.

    Provide the results as a JSON array of objects, each containing:
    - title: The topic/segment title
    - start: Start time of the clip (in seconds)
    - end: End time of the clip (in seconds)

    The clips can overlap if necessary to capture complete discussions or segments.
    """

    clip_generation_data = {
        "model": config['anthropic_model'],
        "max_tokens": 2000,
        "messages": [
            {"role": "user", "content": clip_generation_message}
        ]
    }

    clip_response = requests.post(config['anthropic_api_url'], headers=headers, json=clip_generation_data)
    clip_text = clip_response.json()['content'][0]['text']
    logger.debug(f"Full AI response for clip generation:\n{clip_text}")

    try:
        clips = json.loads(clip_text)
    except json.JSONDecodeError:
        clip_pattern = r'\{\s*"title":\s*"([^"]+)",\s*"start":\s*(\d+(?:\.\d+)?),\s*"end":\s*(\d+(?:\.\d+)?)\s*\}'
        matches = re.findall(clip_pattern, clip_text)
        clips = [{"title": title, "start": float(start), "end": float(end)} for title, start, end in matches]

    if not clips:
        raise ValueError("Failed to extract clip information from the AI response")

    ffmpeg_commands = []
    for clip in clips:
        safe_title = ''.join(c for c in clip['title'] if c.isalnum() or c in (' ', '_')).rstrip()
        safe_title = safe_title.replace(' ', '_')
        output_file = os.path.join(dest_folder, f"{safe_title}{os.path.splitext(source_file)[1]}")
        start_time = clip['start']
        end_time = clip['end']
        buffer = 0.5
        start_time = max(0, start_time - buffer)
        end_time += buffer
        command = f"/opt/homebrew/bin/ffmpeg -i {source_file} -ss {start_time:.2f} -to {end_time:.2f} -y -c copy {output_file}"
        ffmpeg_commands.append(command)

    logger.debug(f"Generated FFmpeg commands: {ffmpeg_commands}")
    return ' && '.join(ffmpeg_commands), topics, clips