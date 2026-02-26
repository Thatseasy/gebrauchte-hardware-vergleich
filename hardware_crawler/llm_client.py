"""
Client for interacting with various LLM providers.
"""
import os
import json
import logging
from typing import Any, Dict
from dotenv import load_dotenv

# Load env immediately
load_dotenv()

logger = logging.getLogger(__name__)

class LLMClient:
    """
    Client for interacting with various LLM providers (Gemini, OpenAI, Ollama).
    """
    def __init__(self, api_key: str = None):
        self.provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.api_key = api_key
        self._setup_provider()

    def _setup_provider(self):
        if self.provider == "gemini":
            try:
                import google.generativeai as genai
                if not self.api_key:
                    self.api_key = os.getenv("GEMINI_API_KEY")
                if not self.api_key:
                    logger.warning("GEMINI_API_KEY not found. LLM features will fail.")
                    return
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-2.0-flash')
            except Exception as e:
                logger.error(f"Gemini Init Error: {e}")
                self.api_key = None
            
        elif self.provider == "openai":
            from openai import OpenAI
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                logger.warning("OPENAI_API_KEY not found.")
                return
            self.client = OpenAI(api_key=self.api_key)
            self.model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        elif self.provider == "anthropic":
            # Placeholder
            pass
            
        elif self.provider == "ollama":
            # Placeholder for Requests calls
            self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            self.model_name = os.getenv("OLLAMA_MODEL", "llama3")

    def generate_json(
        self, prompt: str, 
        system_prompt: str = "You are a helpful assistant."
    ) -> Dict[str, Any]:
        """
        Generates a JSON response from the LLM.
        """
        import time
        if not self.api_key and self.provider != "ollama":
            logger.error("LLM Provider not configured properly.")
            return {}

        full_prompt = f"{system_prompt}\n\nTask: {prompt}\n\nResponse (JSON):"

        max_retries = 4
        for attempt in range(max_retries):
            try:
                if self.provider == "gemini":
                    # Gemini JSON mode
                    response = self.model.generate_content(
                        full_prompt,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    return json.loads(response.text)

                elif self.provider == "openai":
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"}
                    )
                    return json.loads(response.choices[0].message.content)
                
                elif self.provider == "ollama":
                    import requests
                    payload = {
                        "model": self.model_name,
                        "prompt": full_prompt,
                        "stream": False,
                        "format": "json"
                    }
                    res = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=30)
                    if res.status_code == 200:
                        return json.loads(res.json()['response'])
            
            except Exception as e:
                error_str = str(e)
                if ("429" in error_str or "Resource exhausted" in error_str) and attempt < max_retries - 1:
                    delay = 2 ** attempt
                    logger.warning(f"Rate limit hit (429). Retrying in {delay}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                    continue
                    
                logger.error("LLM Generation Error (%s): %s", self.provider, e)
                return {}
        
        return {}

    def generate_text(self, prompt: str) -> str:
        """
        Simple text generation.
        """
        if self.provider == "gemini":
            response = self.model.generate_content(prompt)
            return response.text
        # Add others as needed
        return "LLM Not configured or implemented for text."
