import os
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
print(OPENROUTER_API_KEY)
if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY is not set in your environment.")

URL = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",

    # Optional but recommended by OpenRouter
    # "HTTP-Referer": "http://localhost",
    # "X-Title": "My Local Test App",
}

messages = [
    {
        "role": "user",
        "content": "How many r's are in the word 'strawberry'?"
    }
]

payload = {
    "model": "deepseek/deepseek-v4-flash",
    "messages": messages,
    "reasoning": {"enabled": True},
}

res = requests.post(URL, headers=headers, json=payload, timeout=60)
res.raise_for_status()

data = res.json()
assistant_msg = data["choices"][0]["message"]

print("Answer:")
print(assistant_msg.get("content"))

print("\nReasoning details exists:")
print(assistant_msg.get("reasoning_details") is not None)

# Preserve reasoning_details unmodified for continuation
messages.append({
    "role": "assistant",
    "content": assistant_msg.get("content"),
    "reasoning_details": assistant_msg.get("reasoning_details"),
})

messages.append({
    "role": "user",
    "content": "Are you sure? Think carefully."
})

payload2 = {
    "model": "deepseek/deepseek-v4-flash",
    "messages": messages,
    "reasoning": {"enabled": True},
}

res2 = requests.post(URL, headers=headers, json=payload2, timeout=60)
res2.raise_for_status()

data2 = res2.json()
print("\nFollow-up answer:")
print(data2["choices"][0]["message"].get("content"))