"""Image generation backend for opencode — GPT Image 2 via OpenAI API.

Usage:
  image-gen.py <prompt> [--size SIZE] [--quality QUALITY] [--output PATH]

Env:
  OPENAI_API_KEY          — required
  OPENAI_PROXY            — optional, http://user:pass@host:port
  OPENAI_IMAGE_MODEL      — default: gpt-image-2
  OPENAI_IMAGE_SIZE       — default: 1024x1024
  OPENAI_IMAGE_QUALITY    — default: standard
"""

import sys
import os
import json
import base64
import argparse
from pathlib import Path

import httpx

API_KEY = os.environ.get("OPENAI_API_KEY", "")
PROXY_URL = os.environ.get("OPENAI_PROXY", "")

# Load from .env as fallback
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if _ENV_FILE.exists():
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip()
                if not os.environ.get(key):
                    os.environ[key] = val
                    if key == "OPENAI_API_KEY":
                        API_KEY = val
                    elif key == "OPENAI_PROXY":
                        PROXY_URL = val

MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2")
DEFAULT_SIZE = os.environ.get("OPENAI_IMAGE_SIZE", "1024x1024")
DEFAULT_QUALITY = os.environ.get("OPENAI_IMAGE_QUALITY", "auto")
OUTPUT_DIR = Path.home() / ".config/opencode/generated"

VALID_SIZES = {"1024x1024", "1792x1024", "1024x1792"}
VALID_QUALITIES = {"low", "medium", "high", "auto"}


def generate(prompt: str, size: str = DEFAULT_SIZE, quality: str = DEFAULT_QUALITY,
             output: str = None) -> str:
    if not API_KEY:
        return "ERROR: OPENAI_API_KEY is not set. Add to .opencode/.env or export it."

    if size not in VALID_SIZES:
        return f"ERROR: invalid size '{size}'. Use: {', '.join(VALID_SIZES)}"
    if quality not in VALID_QUALITIES:
        return f"ERROR: invalid quality '{quality}'. Use: {', '.join(VALID_QUALITIES)}"

    client_kwargs = {"timeout": httpx.Timeout(120)}
    if PROXY_URL:
        client_kwargs["proxy"] = PROXY_URL

    with httpx.Client(**client_kwargs) as client:
        resp = client.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "prompt": prompt,
                "n": 1,
                "size": size,
                "quality": quality,
            },
        )

    if resp.status_code != 200:
        return f"ERROR: API returned {resp.status_code}\n{resp.text[:500]}"

    data = resp.json()
    b64 = data["data"][0]["b64_json"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if output:
        out_path = Path(output)
    else:
        import hashlib
        h = hashlib.md5(prompt.encode()).hexdigest()[:8]
        out_path = OUTPUT_DIR / f"img_{h}.png"

    out_path.write_bytes(base64.b64decode(b64))
    return f"Generated: {out_path.resolve()}\nSize: {size}\nQuality: {quality}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPT Image 2 generator")
    parser.add_argument("prompt", help="Image description")
    parser.add_argument("--size", default=DEFAULT_SIZE, choices=VALID_SIZES)
    parser.add_argument("--quality", default=DEFAULT_QUALITY, choices=VALID_QUALITIES)
    parser.add_argument("--output", help="Output file path")
    args = parser.parse_args()

    print(generate(args.prompt, args.size, args.quality, args.output))
