"""Local Ollama transport and model identity checks; no model downloads here."""
import hashlib
import json
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def local_url(value):
    parsed = urlparse(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise ValueError("Ollama must use a local HTTP URL, e.g. http://127.0.0.1:11434")
    return value.rstrip("/")


def fetch(base_url, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(local_url(base_url) + path, data=data,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=15) as stream:
        return json.load(stream)


def identity(manifest):
    base = manifest["base_url"]
    version = fetch(base, "/api/version")["version"]
    models = fetch(base, "/api/tags").get("models", [])
    match = next((m for m in models if m.get("name") == manifest["model"]
                  or m.get("model") == manifest["model"]), None)
    if match is None:
        raise ValueError(f"Local model missing. Run: ollama pull {manifest['model']}")
    details = fetch(base, "/api/show", {"model": manifest["model"]})
    if details.get("remote_host") or details.get("remote_model"):
        raise ValueError("The plan requires local weights, not an Ollama cloud model")
    if not match.get("digest"):
        raise ValueError("Ollama did not report a model digest")
    # Template and model defaults can affect judgments even with the same weights.
    relevant = {k: details.get(k) for k in ["template", "parameters", "model_info", "details", "capabilities"]}
    digest = hashlib.sha256(json.dumps(relevant, sort_keys=True).encode()).hexdigest()
    return {"provider": "ollama", "server_version": version, "model": manifest["model"],
            "model_digest": match["digest"], "model_details_sha256": digest,
            "model_size_bytes": match.get("size"), "details": match.get("details", {})}


def payload(prompt, manifest, schema):
    return {"model": manifest["model"], "messages": [{"role": "user", "content": prompt}],
            "stream": False, "think": manifest["thinking"], "format": schema,
            "keep_alive": "10m", "options": {
                "temperature": manifest["temperature"], "num_predict": manifest["max_output_tokens"],
                "num_ctx": manifest["context_window"], "top_p": manifest["top_p"],
                "top_k": manifest["top_k"], "repeat_penalty": 1.0,
            }}


def parse(response, validate):
    if response.get("done") is not True or response.get("done_reason") != "stop":
        raise ValueError("Missing or incomplete Ollama generation")
    message = response.get("message", {})
    if message.get("role") != "assistant" or message.get("tool_calls"):
        raise ValueError("Expected a final assistant JSON response, not a tool call")
    return validate(json.loads(message.get("content", "")))
