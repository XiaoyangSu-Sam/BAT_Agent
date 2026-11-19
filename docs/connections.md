# Model connections

## Endpoint and model

BAT Agent supports an OpenAI-compatible **Chat Completions** service. Endpoint may be a complete /v1/chat/completions URL, a /v1 base URL, or a host URL. A host URL receives /v1/chat/completions. Custom proxy prefixes are preserved.

The model name must match the deployment’s accepted identifier. Find models requests the sibling /models route (for example /v1/models) and presents up to 300 entries in a dropdown. Not every service provides this route. Failure to list models does not prove that chat is unavailable; type the known model name and test it.

Supported discovery capacity fields are integer context_length and max_model_len. Other formats remain unknown. Confirm deployment capacity with the service owner if necessary.

Saved connections automatically fill their settings. Choose New connection to add another. The workbench dropdown switches between usable connections without retyping endpoints or credentials. An existing connection can be edited and tested again before saving. This release does not include a Delete connection button; see the configuration guide for removing a saved entry.

## API key is optional

- Blank key and blank environment-variable field: no Authorization header.
- Entered key: Bearer authentication; retained only in server memory until shutdown.
- Environment variable in Advanced settings: resolved on the server, never displayed in the page.
- An available in-memory key can be reused when editing that saved connection. Changing the endpoint clears this reuse choice.

Saved YAML contains a reference such as $LLM_API_KEY, not a newly entered key. After restart, either supply that variable or re-enter the key. If several saved services use different keys, give their environment variables distinct names. Legacy literal keys in existing YAML are accepted but are not shown to the browser.

The page is a model connection screen, not a multi-user login system.

## What Test connection proves

The test makes one actual chat request, with retries disabled and a maximum total request time of 30 seconds. It does not save a failed draft. Changing a field invalidates the previous test. Open workspace is enabled only after a valid text reply to the current draft.

The result lists observations from that request, including network establishment, TLS where applicable, sending and receiving. It does not use ICMP ping: a server can block ping while its model API works. Network establishment may refer to a configured proxy, not a direct connection to the final host.

A chat test proves that the selected endpoint/model can answer chat. It does not prove tool calling works. In the workbench, Test model and tools sends a synthetic echo function and returns its result to the model. It never runs files or commands.

## Troubleshooting

| Result | What is known | What to do |
| --- | --- | --- |
| DNS error | Server name could not be resolved | Check spelling and internal DNS/VPN access. |
| Connection refused | The connection was rejected | Check host, port and server process; a firewall can also reject a connection. |
| Timeout before connection | No connection completed in time | Check VPN, routing, firewall and proxy access. |
| Timeout after sending | No complete reply arrived | Server may be overloaded, queueing or loading a model; ask its owner or retry. |
| TLS error | Certificate validation failed | Check clock/hostname and install the correct corporate CA via SSL_CERT_FILE. |
| Proxy error / HTTP 407 | Proxy access failed or needs authentication | Check proxy authentication and NO_PROXY with IT. |
| HTTP 401 | Credentials were not accepted | Check key, expiration and required authentication scheme. |
| HTTP 403 | Server or gateway denied access | Check VPN, IP allowlist, account/model permissions and gateway policy. It does not identify which one caused the denial. |
| HTTP 404 | Route or model was not found | Check full endpoint path and deployed model name. |
| HTTP 429 | Rate/quota restriction | Wait, reduce requests, or ask about quota. |
| HTTP 5xx | Service or gateway error | Ask the service owner to inspect availability/logs. |
| Redirect | Endpoint returned a redirect | Use the final API URL. Credentials are not forwarded through automatic redirects. |
| Invalid JSON/reply | Response was not compatible Chat Completions | Check whether the address points to a web login page or another API format. |
| Tools not observed | Chat worked but the expected tool exchange did not | Check the server’s tool parser/model; explicitly try JSON mode. |

VPN/IP rejection is only confirmed by infrastructure or service logs. The app does not claim to know VPN state from an HTTP status.

HTTP(S)_PROXY, ALL_PROXY, NO_PROXY and certificate environment settings are honored by default. TLS validation remains enabled. Set trust_env: false in YAML only when deliberately bypassing environment proxy configuration. Never publish a real API key in a screenshot or issue.

## Tool compatibility

Native mode uses Chat Completions function tools. JSON mode is an explicit fallback for deployments without native tools. Chat only disables tools. The agent never executes an arbitrary code block from an answer.

A model may chat correctly yet fail to use tools reliably. Complete the small coding and Skill tasks in company-validation.md before adopting the app for company work.
