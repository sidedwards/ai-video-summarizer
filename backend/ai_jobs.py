import json
import time
import os
import re
import subprocess

import requests

from log import logger
from transcription_goal import TranscriptionGoal
from transcription_models import get_transcription_model
from summarization_models import get_summarization_model
from clip_generation_models import get_clip_generation_model


def start_transcription(url, config):
    transcription_model = get_transcription_model(config)
    return transcription_model.start_transcription(url, config)


def get_transcription_result(prediction_url, config):
    transcription_model = get_transcription_model(config)
    return transcription_model.get_transcription_result(prediction_url, config)


def generate_content(transcript, goal, config):
    summarization_model = get_summarization_model(config)
    return summarization_model.generate_summary(transcript, goal, config)


def create_media_clips(transcript, content, source_file, dest_folder, goal, config):
    clip_model = get_clip_generation_model(config)
    
    # Extract topics from content
    topics = clip_model.extract_topics(content, goal, config)
    
    # Generate clip timestamps
    clips = clip_model.generate_clips(transcript, topics, config)
    
    # Create the actual media clips
    return clip_model.create_clips(clips, source_file, dest_folder)