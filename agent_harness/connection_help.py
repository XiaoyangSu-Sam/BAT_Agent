"""Safe, actionable observations from the actual HTTP request, never ICMP guesses."""
import socket
import ssl
import httpx
from .errors import HarnessError

def network_error(exc):
    causes, item = [], exc
    while item is not None and len(causes) < 12:
        causes.append(item)
        item = item.__cause__ or item.__context__
    codes = {getattr(e, "errno", None) for e in causes}
    if any(isinstance(e, ssl.SSLError) for e in causes) or "CERTIFICATE_VERIFY_FAILED" in str(exc):
        return HarnessError("tls_error", "The server certificate could not be verified.", "tls",
            suggestions=["Check your computer clock and the endpoint hostname.",
                         "Ask IT for the corporate CA certificate and configure SSL_CERT_FILE. TLS verification remains enabled."])
    if any(isinstance(e, socket.gaierror) for e in causes):
        return HarnessError("dns_error", "The server name could not be resolved.", "network",
            suggestions=["Check the endpoint spelling.", "For an internal server, connect to the required VPN and retry."])
    if isinstance(exc, httpx.ProxyError):
        return HarnessError("proxy_error", "The configured proxy could not complete the connection.", "network",
            suggestions=["Check your organization’s proxy settings.", "Ask IT whether this internal address should be included in NO_PROXY."])
    if codes & {61, 111, 10061}:
        return HarnessError("connection_refused", "The network connection was refused.", "network",
            suggestions=["Check the port and ask whether the model server is running.",
                         "A firewall may also reject a connection. This result alone does not identify which side refused it."])
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        stage = "network" if isinstance(exc, httpx.ConnectTimeout) else "response"
        return HarnessError("model_timeout", "The request timed out before a complete response arrived.", stage, True,
            suggestions=["Check VPN and network access if connecting never completed.",
                         "If the request was sent, the server may be busy or the model may be loading. Retry later."])
    return HarnessError("network_error", "A network connection could not be completed.", "network", True,
        suggestions=["Check the endpoint, VPN and proxy settings.", "Ask IT to check routing, firewall and IP allowlist access."])

def status_error(response):
    status = response.status_code
    code, message, actions = {
        400: ("request_rejected", "The server rejected the request format or model settings.",
              ["Check the model name and whether this service supports Chat Completions."]),
        401: ("authentication_failed", "The server requires a valid API key.",
              ["Enter the correct key, or check that the configured key has not expired."]),
        403: ("access_denied", "The server or gateway denied access.",
              ["Check the required VPN and ask IT about IP allowlists and model permissions.",
               "HTTP 403 does not prove that your IP was blocked or that VPN is disconnected."]),
        404: ("endpoint_not_found", "The endpoint route or requested model was not found.",
              ["Compare the endpoint and model name with a working request.",
               "For a custom request path, select Exact request URL so no path is appended. Model discovery is optional."]),
        407: ("proxy_authentication_required", "The proxy requires authentication.",
              ["Ask IT to check your proxy authentication settings."]),
        429: ("rate_limited", "The service is limiting requests or has no available quota.",
              ["Wait and retry, or ask the service owner to check your quota."]),
    }.get(status, ("server_error" if status >= 500 else "request_rejected",
                 "The model service or gateway returned an error.",
                 ["Ask the service owner to check availability and server logs."]))
    if 300 <= status < 400:
        code, message, actions = "endpoint_redirect", "The endpoint redirected the request.", [
            "Use the final Chat Completions URL. Redirects are not followed with your credentials."]
    return HarnessError(code, message, "http", status in (408, 429, 500, 502, 503, 504),
        http_status=status, suggestions=actions,
        request_id=response.headers.get("x-request-id", "")[:120])

def trace_observation(name):
    # HTTPX trace info can contain headers; only these event names are retained.
    for suffix, phase, label in [
        ("connect_tcp.started", "connecting", "Opening a network connection"),
        ("connect_tcp.complete", "connected", "Network connection established"),
        ("start_tls.complete", "secured", "TLS handshake completed"),
        ("send_request_headers.started", "sending", "Sending the request"),
        ("send_request_body.complete", "processing", "Request sent; waiting for the server"),
        ("receive_response_headers.complete", "receiving", "Response headers received"),
        ("receive_response_body.complete", "received", "Response body received"),
    ]:
        if name.endswith(suffix):
            return {"phase": phase, "message": label}
    return None
