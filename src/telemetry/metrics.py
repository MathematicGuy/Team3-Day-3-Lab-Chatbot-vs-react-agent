import time
from typing import Dict, Any, List
from src.telemetry.logger import logger

class PerformanceTracker:
    """
    Tracking industry-standard metrics for LLMs.
    """
    # Per-1K-token pricing table (prompt + completion averaged)
    # Sources (approximate, as of mid-2025):
    #   GPT-4o          : $0.005 / 1K tokens (blended)
    #   GPT-4o-mini     : $0.00015 / 1K tokens
    #   GPT-3.5-turbo   : $0.0005 / 1K tokens
    #   gemini-1.5-flash: $0.000075 / 1K tokens
    #   gemini-1.5-pro  : $0.00175 / 1K tokens
    #   gemini-2.0-flash: $0.0001 / 1K tokens (estimated)
    PRICING: Dict[str, float] = {
        "gpt-4o":               0.005,
        "gpt-4o-mini":          0.00015,
        "gpt-3.5-turbo":        0.0005,
        "gemini-1.5-flash":     0.000075,
        "gemini-1.5-pro":       0.00175,
        "gemini-2.0-flash":     0.0001,
        "gemini-2.0-flash-exp": 0.0001,
        "gemini-2.5-flash":     0.000075,
        "gemini-3.1-flash-lite":0.000075,
        "deepseek-v4-flash":    0.00014745,
    }

    def __init__(self):
        self.session_metrics = []

    def get_supported_models(self) -> List[str]:
        """
        Returns a list of supported model keys from the metrics configuration.
        """
        return list(self.PRICING.keys())

    def track_request(self, provider: str, model: str, usage: Dict[str, int], latency_ms: int):
        """
        Logs a single request metric to our telemetry.
        """
        metric = {
            "provider": provider,
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "latency_ms": latency_ms,
            "cost_estimate": self._calculate_cost(model, usage) # Mock cost calculation
        }
        self.session_metrics.append(metric)
        logger.log_event("LLM_METRIC", metric)

    def _calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """
        Estimate API cost based on real-world per-token pricing.
        Prices are per 1 000 tokens (input + output combined for simplicity).
        """
        # Match model name (case-insensitive, partial prefix match)
        model_lower = model.lower()
        price_per_1k = 0.001  # default fallback
        for key, price in self.PRICING.items():
            if model_lower.startswith(key) or key in model_lower:
                price_per_1k = price
                break

        total_tokens = usage.get("total_tokens", 0)
        return round((total_tokens / 1000) * price_per_1k, 7)

# Global tracker instance
tracker = PerformanceTracker()
