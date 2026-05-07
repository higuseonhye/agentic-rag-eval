from __future__ import annotations

from chromadb import HttpClient

from app.core.config import settings


def get_chroma_client() -> HttpClient:
    # chroma_http_url like http://localhost:8001
    base = settings.chroma_http_url.replace("http://", "").replace("https://", "")
    if ":" in base:
        host, port_str = base.split(":", 1)
        port = int(port_str)
    else:
        host, port = base, 80
    return HttpClient(host=host, port=port)


def get_default_collection_name() -> str:
    return "adw_chunks_v1"

