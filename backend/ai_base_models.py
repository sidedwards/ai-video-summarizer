from typing import Dict, Any, Optional
import json
import re
from log import logger
import requests
from openai import OpenAI

class AnthropicBaseModel:
    """Base class for Anthropic API interactions."""

    def _make_anthropic_request(self, message: str, config: Dict, max_tokens: int = 2000, retries: int = 2) -> str:
        """Make a request to Anthropic API and return the response text."""
        # Add JSON format enforcement to the message
        formatted_message = f"""You MUST respond with valid JSON only. No other text or explanation is allowed.
        If you need to include a message, put it in the JSON structure.
        
        {message}
        
        Remember: Your entire response must be parseable as JSON."""

        headers = {
            "x-api-key": config["anthropic_api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        data = {
            "model": config["anthropic_model"],
            "messages": [{"role": "user", "content": formatted_message}],
            "max_tokens": max_tokens,
            "temperature": 0
        }

        for attempt in range(retries + 1):
            try:
                logger.debug(f"Sending request to Anthropic API (attempt {attempt + 1}): {config['anthropic_api_url']}")
                response = requests.post(config["anthropic_api_url"], headers=headers, json=data)
                response.raise_for_status()
                response_json = response.json()

                if "error" in response_json:
                    error_msg = response_json.get("error", {}).get("message", "Unknown error")
                    logger.error(f"Anthropic API error: {error_msg}")
                    if attempt < retries:
                        logger.info(f"Retrying request (attempt {attempt + 2})")
                        continue
                    raise Exception(f"Anthropic API error: {error_msg}")

                return response_json.get("content", [{}])[0].get("text", "")

            except requests.RequestException as e:
                if attempt < retries:
                    logger.warning(f"Request failed (attempt {attempt + 1}): {str(e)}")
                    continue
                raise Exception(f"Failed to communicate with Anthropic API: {str(e)}")

        raise Exception("All retry attempts failed")

    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """Attempt to extract JSON from a text response."""
        # Try to find JSON-like structure
        json_pattern = r'\{(?:[^{}]|(?R))*\}'
        matches = re.findall(json_pattern, text)

        for potential_json in matches:
            try:
                json.loads(potential_json)
                return potential_json
            except json.JSONDecodeError:
                continue

        return None

    def _parse_json_response(self, response_text: str, fallback_pattern: str = None) -> Any:
        """Parse JSON response with multiple fallback strategies."""
        # Clean control characters
        cleaned_text = "".join(char for char in response_text if ord(char) >= 32 or char == '\n')

        # First attempt: direct JSON parsing
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            logger.debug("Direct JSON parsing failed, trying fallback methods")

        # Second attempt: try to extract JSON from text
        json_text = self._extract_json_from_text(cleaned_text)
        if json_text:
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                logger.debug("Extracted JSON parsing failed, trying pattern matching")

        # Third attempt: pattern matching if provided
        if fallback_pattern:
            matches = re.findall(fallback_pattern, cleaned_text)
            if matches:
                logger.debug("Successfully extracted content using pattern matching")
                return matches

        # Fourth attempt: try to create JSON from plain text
        if not any(char in cleaned_text for char in '{['):
            try:
                # Wrap plain text in a JSON structure
                return {"content": cleaned_text.strip()}
            except Exception:
                logger.debug("Failed to create JSON from plain text")

        logger.error(f"Failed to parse response as JSON: {cleaned_text}")
        raise Exception("Failed to parse AI response")

class OpenAIBaseModel:
    """Base class for OpenAI API interactions."""

    def _make_openai_request(self, messages: list, config: Dict, max_tokens: int = 4000, retries: int = 2) -> str:
        """
        Send a request to OpenAI's ChatCompletion endpoint.
        
        Args:
            messages: List of dicts for the conversation.
            config: Contains openai_api_key and other OpenAI settings.
            max_tokens: Maximum tokens in the response.
            retries: Number of retry attempts.
            
        Returns:
            The response text from the API.
        """
        client = OpenAI(api_key=config["openai_api_key"])

        for attempt in range(retries + 1):
            try:
                logger.debug(f"Sending OpenAI request (attempt {attempt + 1})")
                response = client.chat.completions.create(
                    model=config.get("openai_model", "gpt-3.5-turbo"),
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0
                )
                return response.choices[0].message.content

            except Exception as e:
                if attempt < retries:
                    logger.warning(f"OpenAI request failed (attempt {attempt + 1}): {str(e)}")
                    continue
                raise Exception(f"OpenAI API error: {str(e)}")

        raise Exception("All retry attempts for OpenAI API failed")

    # Reuse the same JSON parsing helpers from AnthropicBaseModel
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """Attempt to extract JSON from a text response."""
        json_pattern = r'\{(?:[^{}]|(?R))*\}'
        matches = re.findall(json_pattern, text)

        for potential_json in matches:
            try:
                json.loads(potential_json)
                return potential_json
            except json.JSONDecodeError:
                continue

        return None

    def _parse_json_response(self, response_text: str, fallback_pattern: str = None) -> Any:
        """Parse JSON response with multiple fallback strategies."""
        # Clean control characters
        cleaned_text = "".join(char for char in response_text if ord(char) >= 32 or char == '\n')

        # First attempt: direct JSON parsing
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            logger.debug("Direct JSON parsing failed, trying fallback methods")

        # Second attempt: try to extract JSON from text
        json_text = self._extract_json_from_text(cleaned_text)
        if json_text:
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                logger.debug("Extracted JSON parsing failed, trying pattern matching")

        # Third attempt: pattern matching if provided
        if fallback_pattern:
            matches = re.findall(fallback_pattern, cleaned_text)
            if matches:
                logger.debug("Successfully extracted content using pattern matching")
                return matches

        # Fourth attempt: try to create JSON from plain text
        if not any(char in cleaned_text for char in '{['):
            try:
                return {"content": cleaned_text.strip()}
            except Exception:
                logger.debug("Failed to create JSON from plain text")

        logger.error(f"Failed to parse response as JSON: {cleaned_text}")
        raise Exception("Failed to parse AI response") 