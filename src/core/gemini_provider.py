import os
import time
from typing import Dict, Any, List, Optional, Generator
from openai import OpenAI
from src.core.llm_provider import LLMProvider

class GeminiProvider(LLMProvider):
    """
    OpenRouter Provider utilizing OpenRouter to call models (e.g. deepseek/deepseek-v4-flash).
    Uses the OPENAI_ROUTER or GEMINI_API_KEY environment variable.
    """
    def __init__(self, model_name: str = "deepseek/deepseek-v4-flash", api_key: Optional[str] = None):
        if not api_key:
            api_key = os.getenv("OPENAI_ROUTER") or os.getenv("GEMINI_API_KEY")
        
        # Translate standard gemini-1.5-flash to OpenRouter's deepseek/deepseek-v4-flash or similar
        if model_name == "gemini-1.5-flash":
            model_name = "deepseek/deepseek-v4-flash"
        elif model_name and not model_name.startswith("deepseek/") and "/" not in model_name:
            model_name = f"deepseek/{model_name}"

        # Validate/suggest model options from metrics.py
        from src.telemetry.metrics import tracker
        supported = tracker.get_supported_models()
        clean_model = model_name.split("/")[-1]
        if clean_model not in supported and model_name not in supported:
            print(f"[*] [GeminiProvider] Note: model '{model_name}' is not listed in metrics.py pricing tables.")
            print(f"    Available options in metrics.py: {supported}")

        super().__init__(model_name, api_key)
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key
        )

    def generate(self, prompt: str, system_prompt: Optional[str] = None, stop: Optional[List[str]] = None) -> Dict[str, Any]:
        start_time = time.time()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stop=stop
        )

        end_time = time.time()
        latency_ms = int((end_time - start_time) * 1000)

        # Extraction from OpenRouter/OpenAI response
        content = response.choices[0].message.content
        prompt_tokens = getattr(response.usage, "prompt_tokens", 0) if response.usage else 0
        completion_tokens = getattr(response.usage, "completion_tokens", 0) if response.usage else 0
        total_tokens = getattr(response.usage, "total_tokens", 0) if response.usage else 0
        
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens
        }

        # Track Request telemetry metrics
        from src.telemetry.metrics import tracker
        tracker.track_request(
            provider="deepseek-openrouter",
            model=self.model_name,
            usage=usage,
            latency_ms=latency_ms
        )

        return {
            "content": content,
            "usage": usage,
            "latency_ms": latency_ms,
            "provider": "deepseek-openrouter"
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


if __name__ == "__main__":
    # Test script for checking if OpenRouter key works for Gemini
    print("=" * 60)
    print("         OPENROUTER DEEPSEEK KEY VALIDATION RUNNER")
    print("=" * 60)

    # Let's retrieve the OPENAI_ROUTER from environment
    api_key = os.getenv("OPENAI_ROUTER")

    if not api_key:
        print("[ERROR] No OPENAI_ROUTER environment variable is currently set.")
        print("[*] Please set the OPENAI_ROUTER environment variable and try again.")
        print("=" * 60)
    else:
        print(f"[*] API Key Source : Environment Variable (OPENAI_ROUTER)")
        print(f"[*] API Key Prefix : {api_key[:12]}...")
        print(f"[*] API Key Suffix : ...{api_key[-12:]}")
        print(f"[*] Initializing DeepSeek via OpenRouter (deepseek/deepseek-v4-flash)")
        print("-" * 60)

        try:
            provider = GeminiProvider(model_name="deepseek/deepseek-v4-flash", api_key=api_key)
            prompt = "Hello! Tell me in 1 sentence what DeepSeek model you are running on."
            print(f"[*] Prompt: '{prompt}'")
            print("[*] Generating response...")
            
            result = provider.generate(
                prompt=prompt,
                system_prompt="You are a helpful travel assistant running via OpenRouter."
            )
            
            print("-" * 60)
            print("[SUCCESS] OpenRouter DeepSeek connection verified! Key is VALID.")
            print(f"[SUCCESS] Response Content: {result['content']}")
            print(f"[SUCCESS] Usage: {result['usage']}")
            print(f"[SUCCESS] Latency: {result['latency_ms']} ms")
            print("=" * 60)
        except Exception as e:
            print("-" * 60)
            print("[ERROR] OpenRouter DeepSeek API verification FAILED.")
            print(f"[ERROR] Exception Details: {e}")
            print("=" * 60)
