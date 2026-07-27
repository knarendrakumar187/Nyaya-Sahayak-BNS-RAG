"""Inspect .env key hygiene without printing the secret."""

from pathlib import Path

from dotenv import dotenv_values

env_path = Path(__file__).resolve().parent.parent / ".env"
vals = dotenv_values(env_path)
raw = vals.get("GOOGLE_API_KEY") or ""

print("env_file:", env_path)
print("raw_len:", len(raw))
print("stripped_len:", len(raw.strip()))
print("has_spaces:", " " in raw.strip())
print("has_quotes:", raw.strip()[:1] in {'"', "'"} or raw.strip()[-1:] in {'"', "'"})
print("starts_with_AIza:", raw.strip().startswith("AIza"))
print("starts_with_sk:", raw.strip().startswith("sk-"))
print("contains_newline:", "\n" in raw or "\r" in raw)
if not raw.strip().startswith("AIza"):
    print(
        "HINT: Gemini keys from https://aistudio.google.com/apikey usually start with 'AIza'."
    )
