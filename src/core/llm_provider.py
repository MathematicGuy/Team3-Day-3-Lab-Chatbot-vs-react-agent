import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Generator

class LLMProvider(ABC):
    """
    Abstract Base Class for LLM Providers.
    Supports OpenAI, Gemini, and Local models.
    """

    def __init__(self, model_name: str, api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, stop: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Produce a non-streaming completion.
        Returns:
            Dict containing:
            - content: The response text
            - usage: { 'prompt_tokens', 'completion_tokens' }
            - latency_ms: Response time
        """
        pass

    @abstractmethod
    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        """Produce a streaming completion."""
        pass


class FallbackLLMProvider(LLMProvider):
    """
    LLM Provider that implements a Fallback Plan: OpenAI -> Gemini -> Local.
    It attempts to generate content with OpenAI. If it fails, it falls back to Gemini.
    If Gemini fails, it falls back to the Local model.
    """
    def __init__(self, providers: List[LLMProvider]):
        super().__init__(model_name="fallback-chain")
        self.providers = providers

    def generate(self, prompt: str, system_prompt: Optional[str] = None, stop: Optional[List[str]] = None) -> Dict[str, Any]:
        last_error = None
        for provider in self.providers:
            try:
                print(f"[*] [FallbackChain] Attempting generate() with provider: {provider.__class__.__name__}")
                return provider.generate(prompt, system_prompt, stop=stop)
            except Exception as e:
                print(f"[!] [FallbackChain] Provider {provider.__class__.__name__} failed: {e}")
                last_error = e
        raise RuntimeError(f"All fallback providers failed. Last error: {last_error}")

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        last_error = None
        for provider in self.providers:
            try:
                print(f"[*] [FallbackChain] Attempting stream() with provider: {provider.__class__.__name__}")
                # Try to yield from stream
                for chunk in provider.stream(prompt, system_prompt):
                    yield chunk
                return
            except Exception as e:
                print(f"[!] [FallbackChain] Provider {provider.__class__.__name__} stream failed: {e}")
                last_error = e
        raise RuntimeError(f"All fallback streaming providers failed. Last error: {last_error}")


def get_fallback_provider(
    openai_model: str = "gpt-4o",
    gemini_model: str = "deepseek/deepseek-v4-flash",
    local_model_path: Optional[str] = None
) -> LLMProvider:
    """
    Factory function to build a FallbackLLMProvider chain.
    Attempts to initialize in order:
    1. OpenAIProvider (using environment OPENAI_API_KEY)
    2. GeminiProvider (using environment GEMINI_API_KEY)
    3. LocalProvider (using local_model_path or environment LOCAL_MODEL_PATH)
    """
    from src.core.openai_provider import OpenAIProvider
    from src.core.gemini_provider import GeminiProvider

    providers = []
    
    # 1. Try OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and openai_key != "your_openai_api_key_here":
        try:
            providers.append(OpenAIProvider(model_name=openai_model, api_key=openai_key))
            print("[*] [FallbackChain] OpenAIProvider registered.")
        except Exception as e:
            print(f"[!] [FallbackChain] Failed to register OpenAIProvider: {e}")
            
    # 2. Try Gemini
    gemini_key = os.getenv("OPENAI_ROUTER") or os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_gemini_api_key_here":
        try:
            # If using OpenRouter, default to google/gemini-2.5-flash unless specified
            gemini_model_name = gemini_model
            if os.getenv("OPENAI_ROUTER") and gemini_model == "gemini-1.5-flash":
                gemini_model_name = "google/gemini-2.5-flash"
            
            providers.append(GeminiProvider(model_name=gemini_model_name, api_key=gemini_key))
            print("[*] [FallbackChain] GeminiProvider (via OpenRouter/Google) registered.")
        except Exception as e:
            print(f"[!] [FallbackChain] Failed to register GeminiProvider: {e}")
            
    # 3. Try Local
    model_path = local_model_path or os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
    if model_path and os.path.exists(model_path):
        try:
            from src.core.local_provider import LocalProvider, HAS_LLAMA_CPP
            if HAS_LLAMA_CPP:
                providers.append(LocalProvider(model_path=model_path))
                print("[*] [FallbackChain] LocalProvider registered.")
            else:
                print("[!] [FallbackChain] LocalProvider skipped because llama-cpp-python is not installed.")
        except Exception as e:
            print(f"[!] [FallbackChain] Failed to register LocalProvider: {e}")
            
    if not providers:
        raise RuntimeError("No LLM providers could be initialized. Please configure API keys or download a local model.")
        
    return FallbackLLMProvider(providers)

