# key/templatetags/vite.py
import json
from pathlib import Path
from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()
_manifest_cache = None

def _load_manifest():
    global _manifest_cache
    if _manifest_cache is not None:
        return _manifest_cache
    manifest_path = Path(settings.VITE_ASSETS_DIR) / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Vite manifest not found: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as f:
        _manifest_cache = json.load(f)
    return _manifest_cache

@register.simple_tag
def vite_asset(entry):
    try:
        manifest = _load_manifest()
    except Exception as e:
        return mark_safe(f"<!-- Vite manifest error: {e} -->")
    if entry not in manifest:
        return mark_safe(f"<!-- Vite manifest has no entry {entry} -->")
    data = manifest[entry]
    tags = []
    for css in data.get("css", []):
        href = f"{settings.STATIC_URL.rstrip('/')}/{css.lstrip('/')}"
        tags.append(f'<link rel="stylesheet" href="{href}">')
    js = data.get("file")
    if js:
        src = f"{settings.STATIC_URL.rstrip('/')}/{js.lstrip('/')}"
        tags.append(f'<script type="module" src="{src}"></script>')
    return mark_safe("\n".join(tags))
