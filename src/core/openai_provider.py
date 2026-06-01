import os
import time
from typing import Dict, Any, List, Optional, Generator
from openai import OpenAI
from src.core.llm_provider import LLMProvider

class OpenAIProvider(LLMProvider):
    def __init__(self, model_name: str = "gpt-5-nano-2025-08-07", api_key: Optional[str] = None):
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        # Validate/suggest model options from metrics.py
        from src.telemetry.metrics import tracker
        supported = tracker.get_supported_models()
        # Strip vendor prefix if checking
        clean_model = model_name.split("/")[-1]
        if clean_model not in supported and model_name not in supported:
            print(f"[*] [OpenAIProvider] Note: model '{model_name}' is not listed in metrics.py pricing tables.")
            print(f"    Available options in metrics.py: {supported}")
            
        super().__init__(model_name, api_key)
        self.client = OpenAI(api_key=self.api_key)

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

        # Extraction from OpenAI response
        content = response.choices[0].message.content
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }

        # Track Request telemetry metrics
        from src.telemetry.metrics import tracker
        tracker.track_request(
            provider="openai",
            model=self.model_name,
            usage=usage,
            latency_ms=latency_ms
        )

        return {
            "content": content,
            "usage": usage,
            "latency_ms": latency_ms,
            "provider": "openai"
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
    # Test script for checking if OpenAI key is valid
    print("=" * 60)
    print("           OPENAI API KEY VALIDATION RUNNER")
    print("=" * 60)

    # Key provided from env
    env_key = os.getenv("OPENAI_API_KEY")

    if not env_key:
        print("[ERROR] No OPENAI_API_KEY environment variable is currently set.")
        print("[*] Please set the OPENAI_API_KEY environment variable and try again.")
        print("=" * 60)
    else:
        print(f"[*] Testing API key from environment:")
        print(f"    Prefix: {env_key[:12]}...")
        print(f"    Suffix: ...{env_key[-12:]}")

        print("-" * 60)
        print("[*] Initializing OpenAIProvider...")
        try:
            provider = OpenAIProvider(model_name="gpt-5-nano-2025-08-07", api_key=env_key)
            prompt = "Hello! Please give a 1-sentence greeting for a flight assistant traveler tool."
            print(f"[*] Prompt: '{prompt}'")
            print("[*] Generating response...")
            
            result = provider.generate(
                prompt=prompt,
                system_prompt="You are a friendly digital nomad travel assistant."
            )
            
            print("-" * 60)
            print("[SUCCESS] OpenAI connection verified! The key is VALID.")
            print(f"[SUCCESS] Response Content: {result['content']}")
            print(f"[SUCCESS] Usage: {result['usage']}")
            print(f"[SUCCESS] Latency: {result['latency_ms']} ms")
            print("=" * 60)
        except Exception as e:
            print("-" * 60)
            print("[ERROR] OpenAI API verification FAILED.")
            print(f"[ERROR] Exception Details: {e}")
            print("[ERROR] Please check if the key is correct, has expired, is inactive, or has usage/billing limits.")
            print("=" * 60)
