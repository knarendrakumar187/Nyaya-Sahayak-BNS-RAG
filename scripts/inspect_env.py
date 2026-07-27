"""Inspect .env structure without printing secrets."""

from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
text = env_path.read_text(encoding="utf-8-sig")
lines = text.splitlines()

print("path:", env_path)
print("line_count:", len(lines))
print("mtime_ok:", env_path.exists())

for i, line in enumerate(lines, 1):
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        continue
    if "=" not in stripped:
        print(f"L{i}: INVALID_LINE (no =)")
        continue
    name, value = stripped.split("=", 1)
    name = name.strip()
    value = value.strip().strip("\"'")
    preview = ""
    if name.upper().endswith("KEY") or "TOKEN" in name.upper():
        preview = f"len={len(value)} prefix={value[:4]!r}..."
    else:
        preview = f"value={value!r}"
    print(f"L{i}: {name} -> {preview}")
