from typing import Dict, List
import json
import re
import requests
from log import logger
from transcription_goal import TranscriptionGoal
from ai_base_models import AnthropicBaseModel
from ai_base_models import OpenAIBaseModel

class SummarizationModel:
    """Base class for summarization models."""
    
    def generate_summary(self, transcript: List[Dict], goal: TranscriptionGoal, config: Dict) -> str:
        """Generate and return a summary based on the transcript and goal."""
        raise NotImplementedError


class AnthropicSummarizationModel(SummarizationModel, AnthropicBaseModel):
    """Implementation of Anthropic's summarization model."""

    def _get_prompt_for_goal(self, goal: TranscriptionGoal) -> str:
        prompts = {
            TranscriptionGoal.MEETING_MINUTES: "Create very detailed meeting minutes based on the following transcription.",
            TranscriptionGoal.PODCAST_SUMMARY: "Summarize this podcast episode, highlighting key points and interesting discussions.",
            TranscriptionGoal.LECTURE_NOTES: "Create comprehensive lecture notes from this transcription, organizing key concepts and examples.",
            TranscriptionGoal.INTERVIEW_HIGHLIGHTS: "Extract the main insights and notable quotes from this interview transcription.",
            TranscriptionGoal.GENERAL_TRANSCRIPTION: "Provide a clear and concise summary of the main points discussed in this transcription.",
        }
        return prompts.get(goal, prompts[TranscriptionGoal.GENERAL_TRANSCRIPTION])

    def generate_summary(self, transcript: List[Dict], goal: TranscriptionGoal, config: Dict) -> str:
        logger.debug(f"Generating content for goal: {goal.value}")
        
        base_prompt = self._get_prompt_for_goal(goal)
        message = f"""Return a JSON object with a single key "content" containing the following:
        {base_prompt}
        
        Transcription:
        {json.dumps(transcript)}
        
        Format your response EXACTLY like this:
        {{
            "content": "Your summary here..."
        }}
        """
        
        response_text = self._make_anthropic_request(message, config, max_tokens=4000)
        parsed_response = self._parse_json_response(response_text)
        logger.debug(f"Parsed Anthropic response: {parsed_response}")
        
        # Try to extract content using various possible keys
        for key in ["content", "text", "summary"]:
            if isinstance(parsed_response, dict) and key in parsed_response:
                logger.debug(f"Found content in key: {key}")
                return parsed_response[key]
        
        # If parsed_response is a string, return it directly
        if isinstance(parsed_response, str):
            logger.warning("Response was parsed as plain text, using as content")
            return parsed_response
            
        logger.error(f"Could not find content in response: {parsed_response}")
        raise Exception("Failed to extract summary from AI response")

class OpenAISummarizationModel(SummarizationModel, OpenAIBaseModel):
    """Implementation of OpenAI's summarization model."""

    def _get_prompt_for_goal(self, goal: TranscriptionGoal) -> str:
        prompts = {
            TranscriptionGoal.MEETING_MINUTES: "Create very detailed meeting minutes based on the following transcription.",
            TranscriptionGoal.PODCAST_SUMMARY: "Summarize this podcast episode, highlighting key points and interesting discussions.",
            TranscriptionGoal.LECTURE_NOTES: "Create comprehensive lecture notes from this transcription, organizing key concepts and examples.",
            TranscriptionGoal.INTERVIEW_HIGHLIGHTS: "Extract the main insights and notable quotes from this interview transcription.",
            TranscriptionGoal.GENERAL_TRANSCRIPTION: "Provide a clear and concise summary of the main points discussed in this transcription.",
        }
        return prompts.get(goal, prompts[TranscriptionGoal.GENERAL_TRANSCRIPTION])

    def generate_summary(self, transcript: List[Dict], goal: TranscriptionGoal, config: Dict) -> str:
        """
        Generates a summary using OpenAI's ChatCompletion API.
        
        Parameters:
          - transcript: List of transcription segments.
          - goal: The transcription goal (defines tone/purpose).
          - config: Configuration dictionary containing API keys, endpoints, etc.
        
        Returns:
          - A string containing the summary.
        """
        logger.debug(f"Generating content for goal: {goal.value}")
        
        base_prompt = self._get_prompt_for_goal(goal)
        messages = [
            {"role": "system", "content": "You must output valid JSON only with a single key 'content' containing your response."},
            {"role": "user", "content": f"""Return a JSON object with a single key "content" containing the following:
            {base_prompt}
            
            Transcription:
            {json.dumps(transcript)}
            
            Format your response EXACTLY like this:
            {{
                "content": "Your summary here..."
            }}
            """}
        ]
        
        response_text = self._make_openai_request(messages, config, max_tokens=4000)
        parsed_response = self._parse_json_response(response_text)
        logger.debug(f"Parsed OpenAI response: {parsed_response}")
        
        # Try to extract content using various possible keys
        for key in ["content", "text", "summary"]:
            if isinstance(parsed_response, dict) and key in parsed_response:
                logger.debug(f"Found content in key: {key}")
                return parsed_response[key]
        
        # If parsed_response is a string, return it directly
        if isinstance(parsed_response, str):
            logger.warning("Response was parsed as plain text, using as content")
            return parsed_response
            
        logger.error(f"Could not find content in response: {parsed_response}")
        raise Exception("Failed to extract summary from AI response")


def get_summarization_model(config: Dict) -> SummarizationModel:
    """Factory function to get the appropriate summarization model."""
    model_type = config.get("summarization_model", "anthropic")
    if model_type == "anthropic":
        return AnthropicSummarizationModel()
    elif model_type == "openai":
        return OpenAISummarizationModel()
    else:
        raise ValueError(f"Unknown summarization model: {model_type}") 