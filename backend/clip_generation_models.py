from typing import Dict, List, Tuple
import json
import re
import requests
import os
import subprocess
from log import logger
from transcription_goal import TranscriptionGoal
from ai_base_models import AnthropicBaseModel
from ai_base_models import OpenAIBaseModel

class ClipGenerationModel:
    """Base class for clip generation models."""
    
    def extract_topics(self, content: str, goal: TranscriptionGoal, config: Dict) -> List[Dict]:
        """Extract topics from content."""
        raise NotImplementedError
        
    def generate_clips(self, transcript: List[Dict], topics: List[Dict], config: Dict) -> List[Dict]:
        """Generate clip timestamps for each topic."""
        raise NotImplementedError
        
    def create_clips(self, clips: List[Dict], source_file: str, dest_folder: str) -> Tuple[str, List[Dict], List[Dict]]:
        """Create actual media clips from timestamps."""
        raise NotImplementedError


class AnthropicClipGenerationModel(ClipGenerationModel, AnthropicBaseModel):
    """Implementation of Anthropic's clip generation model."""
    
    def extract_topics(self, content: str, goal: TranscriptionGoal, config: Dict) -> List[Dict]:
        message = f"""Return a JSON array of objects describing the main topics discussed.
        
        Content to analyze:
        {content}
        
        Each object in the array MUST have these exact keys:
        - "title": A short, descriptive title (max 5 words)
        - "keywords": An array of related keywords (max 5 keywords)
        
        Format your response EXACTLY like this:
        [
            {{
                "title": "Example Topic",
                "keywords": ["keyword1", "keyword2", "keyword3"]
            }},
            ...
        ]
        """
        
        response_text = self._make_anthropic_request(message, config, max_tokens=1000)
        parsed_response = self._parse_json_response(
            response_text,
            fallback_pattern=r'\{\s*"title":\s*"([^"]+)",\s*"keywords":\s*\[((?:[^]]+))\]\s*\}'
        )
        
        logger.debug(f"Parsed topics response: {parsed_response}")
        
        # Handle different response formats
        if isinstance(parsed_response, list):
            if all(isinstance(item, dict) for item in parsed_response):
                return parsed_response
            elif all(isinstance(item, tuple) for item in parsed_response):
                # Handle regex fallback results
                return [{"title": title, "keywords": [k.strip(' "') for k in keywords.split(',')]} 
                        for title, keywords in parsed_response]
                
        raise ValueError("Failed to extract valid topics from the AI response")

    def generate_clips(self, transcript: List[Dict], topics: List[Dict], config: Dict) -> List[Dict]:
        message = f"""Return a JSON array of objects defining video clips for each topic.
        
        Topics:
        {json.dumps(topics)}
        
        Transcript:
        {json.dumps(transcript)}
        
        Each object in the array MUST have these exact keys:
        - "title": The topic title
        - "start": Start time in seconds (number)
        - "end": End time in seconds (number)
        
        Rules:
        1. Aim for 2-5 minutes duration
        2. Include complete discussions even if over 5 minutes
        3. Never cut off mid-sentence
        4. Clips can overlap if needed
        
        Format your response EXACTLY like this:
        [
            {{
                "title": "Topic Title",
                "start": 123.45,
                "end": 234.56
            }},
            ...
        ]
        """
        
        response_text = self._make_anthropic_request(message, config, max_tokens=2000)
        parsed_response = self._parse_json_response(
            response_text,
            fallback_pattern=r'\{\s*"title":\s*"([^"]+)",\s*"start":\s*(\d+(?:\.\d+)?),\s*"end":\s*(\d+(?:\.\d+)?)\s*\}'
        )
        
        logger.debug(f"Parsed clips response: {parsed_response}")
        
        # Handle different response formats
        if isinstance(parsed_response, list):
            if all(isinstance(item, dict) for item in parsed_response):
                return parsed_response
            elif all(isinstance(item, tuple) for item in parsed_response):
                # Handle regex fallback results
                return [{"title": title, "start": float(start), "end": float(end)} 
                        for title, start, end in parsed_response]
                
        raise ValueError("Failed to extract valid clips from the AI response")

    def create_clips(self, clips: List[Dict], source_file: str, dest_folder: str) -> Tuple[str, List[Dict], List[Dict]]:
        try:
            ffmpeg_path = subprocess.check_output(['which', 'ffmpeg'], text=True).strip()
        except subprocess.CalledProcessError:
            for path in ['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg']:
                if os.path.exists(path):
                    ffmpeg_path = path
                    break
            else:
                raise Exception("ffmpeg not found. Please install ffmpeg and ensure it's in your PATH")

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
            command = f'"{ffmpeg_path}" -i "{source_file}" -ss {start_time:.2f} -to {end_time:.2f} -y -c copy "{output_file}"'
            ffmpeg_commands.append(command)

        logger.debug(f"Generated FFmpeg commands: {ffmpeg_commands}")
        return ' && '.join(ffmpeg_commands), [], clips

class OpenAIClipGenerationModel(ClipGenerationModel, OpenAIBaseModel):
    """Implementation of OpenAI's clip generation model."""
    
    def extract_topics(self, content: str, goal: TranscriptionGoal, config: Dict) -> List[Dict]:
        """
        Uses OpenAI to extract topics from the summary.
        
        Returns a list of topic objects with keys "title" and "keywords".
        """
        messages = [
            {"role": "system", "content": "You must output valid JSON only. No other text or explanation is allowed."},
            {"role": "user", "content": f"""Return a JSON array of objects describing the main topics discussed.
            
            Content to analyze:
            {content}
            
            Each object in the array MUST have these exact keys:
            - "title": A short, descriptive title (max 5 words)
            - "keywords": An array of related keywords (max 5 keywords)
            
            Format your response EXACTLY like this:
            [
                {{
                    "title": "Example Topic",
                    "keywords": ["keyword1", "keyword2", "keyword3"]
                }},
                ...
            ]
            """}
        ]
        
        response_text = self._make_openai_request(messages, config, max_tokens=1000)
        parsed_response = self._parse_json_response(
            response_text,
            fallback_pattern=r'\{\s*"title":\s*"([^"]+)",\s*"keywords":\s*\[((?:[^]]+))\]\s*\}'
        )
        
        logger.debug(f"Parsed topics response: {parsed_response}")
        
        # Handle different response formats
        if isinstance(parsed_response, list):
            if all(isinstance(item, dict) for item in parsed_response):
                return parsed_response
            elif all(isinstance(item, tuple) for item in parsed_response):
                # Handle regex fallback results
                return [{"title": title, "keywords": [k.strip(' "') for k in keywords.split(',')]} 
                        for title, keywords in parsed_response]
                
        raise ValueError("Failed to extract valid topics from the AI response")

    def generate_clips(self, transcript: List[Dict], topics: List[Dict], config: Dict) -> List[Dict]:
        """
        Uses OpenAI to generate clip boundaries from the transcript and topics.
        
        Returns a list of clip objects, each with keys "title", "start", and "end".
        """
        messages = [
            {"role": "system", "content": "You must output valid JSON only. No other text or explanation is allowed."},
            {"role": "user", "content": f"""Return a JSON array of objects defining video clips for each topic.
            
            Topics:
            {json.dumps(topics)}
            
            Transcript:
            {json.dumps(transcript)}
            
            Each object in the array MUST have these exact keys:
            - "title": The topic title
            - "start": Start time in seconds (number)
            - "end": End time in seconds (number)
            
            Rules:
            1. Aim for 2-5 minutes duration
            2. Include complete discussions even if over 5 minutes
            3. Never cut off mid-sentence
            4. Clips can overlap if needed
            
            Format your response EXACTLY like this:
            [
                {{
                    "title": "Topic Title",
                    "start": 123.45,
                    "end": 234.56
                }},
                ...
            ]
            """}
        ]
        
        response_text = self._make_openai_request(messages, config, max_tokens=2000)
        parsed_response = self._parse_json_response(
            response_text,
            fallback_pattern=r'\{\s*"title":\s*"([^"]+)",\s*"start":\s*(\d+(?:\.\d+)?),\s*"end":\s*(\d+(?:\.\d+)?)\s*\}'
        )
        
        logger.debug(f"Parsed clips response: {parsed_response}")
        
        # Handle different response formats
        if isinstance(parsed_response, list):
            if all(isinstance(item, dict) for item in parsed_response):
                return parsed_response
            elif all(isinstance(item, tuple) for item in parsed_response):
                # Handle regex fallback results
                return [{"title": title, "start": float(start), "end": float(end)} 
                        for title, start, end in parsed_response]
                
        raise ValueError("Failed to extract valid clips from the AI response")

    def create_clips(self, clips: List[Dict], source_file: str, dest_folder: str) -> Tuple[str, List[Dict], List[Dict]]:
        """Create actual media clips from timestamps."""
        try:
            ffmpeg_path = subprocess.check_output(['which', 'ffmpeg'], text=True).strip()
        except subprocess.CalledProcessError:
            for path in ['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg']:
                if os.path.exists(path):
                    ffmpeg_path = path
                    break
            else:
                raise Exception("ffmpeg not found. Please install ffmpeg and ensure it's in your PATH")

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
            command = f'"{ffmpeg_path}" -i "{source_file}" -ss {start_time:.2f} -to {end_time:.2f} -y -c copy "{output_file}"'
            ffmpeg_commands.append(command)

        logger.debug(f"Generated FFmpeg commands: {ffmpeg_commands}")
        return ' && '.join(ffmpeg_commands), [], clips


def get_clip_generation_model(config: Dict) -> ClipGenerationModel:
    """Factory function to get the appropriate clip generation model."""
    model_type = config.get("clip_generation_model", "anthropic")
    if model_type == "anthropic":
        return AnthropicClipGenerationModel()
    elif model_type == "openai":
        return OpenAIClipGenerationModel()
    else:
        raise ValueError(f"Unknown clip generation model: {model_type}") 