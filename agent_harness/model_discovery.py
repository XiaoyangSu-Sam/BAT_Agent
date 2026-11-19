import asyncio
from urllib.parse import urlsplit, urlunsplit
import httpx
from .errors import HarnessError
from .connection_help import network_error, status_error

async def discover_models(config, transport=None):
    p = urlsplit(config.url())
    url = urlunsplit((p.scheme, p.netloc, p.path.removesuffix("/chat/completions") + "/models", "", ""))
    secret = config.secret()
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=config.trust_env, transport=transport,
                                     follow_redirects=False) as client:
            async with asyncio.timeout(15):
                response = await client.get(url, headers={"Authorization":"Bearer "+secret} if secret else {})
        if response.status_code >= 300:
            raise status_error(response)
        data = response.json()
        if not isinstance(data.get("data"), list):
            raise ValueError()
        models = []
        for item in data["data"][:300]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            size = item.get("context_length") or item.get("max_model_len")
            models.append({"id": item["id"][:200],
                "context_window": size if type(size) is int and 1024 <= size <= 10000000 else None})
        return {"models": models, "endpoint": url}
    except (httpx.RequestError, TimeoutError) as exc:
        raise network_error(exc) from exc
    except (ValueError, TypeError):
        raise HarnessError("model_list_unavailable", "This service did not return a model list.", "response",
            suggestions=["You can still enter the model name provided by your service owner and test the connection."])
