import re
import unicodedata

_INJECTION = re.compile(r'(\[\s*(system|inst|assistant)\s*\]|<<\s*sys\s*>>|ignore\s+(all|previous|the)\s+instructions?|\b(select|insert|update|delete)\s+.+\s+from\b|<script)', re.I)

def sanitize_text(value: str, max_length: int = 120) -> str:
    value = unicodedata.normalize('NFKC', ''.join(ch for ch in value if ch.isprintable())).strip()
    if _INJECTION.search(value): return '[Teks disaring]'
    return value[:max_length]
