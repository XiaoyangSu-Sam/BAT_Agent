# NVIDIA Nemotron 3.5 Super VL compatibility

This contract covers the text and native tool use path for `nvidia/nemotron-3.5-super-vl-120b-a12b`. NVIDIA also documents image and video inputs. BAT Agent currently sends text messages.

## Request and response

| Part | BAT Agent behavior |
| --- | --- |
| Endpoint | Sends a JSON POST to `/v1/chat/completions`. Use Exact request URL for an existing custom route. Confirm the served model ID with the deployment operator or `/v1/models`. |
| Authentication | Adds Bearer authentication when the connection has a key. NVIDIA's hosted endpoint requires a key. A private gateway can allow requests with no key. |
| Conversation | Sends the exact model ID and ordered `messages`, with text in `content`. Sets `stream: false` and requests JSON. |
| Text reply | Reads the first `choices[].message.content` as the final answer. Reads `reasoning_content` or `reasoning` separately and uses available `usage` counts. |
| Tool reply | Sends function definitions in `tools` with automatic choice. A structured tool request can have null content. Each call needs a unique ID and JSON-object arguments serialized as a string. BAT Agent validates calls before dispatch and applies the current approval policy. |
| Tool continuation | Returns the assistant call and a `role: tool` message with its matching `tool_call_id`. The named Nemotron model also receives its latest user turn's tool reasoning in `reasoning_content`, as supported by NVIDIA's template. |

The template retains tool reasoning within the latest user turn. BAT Agent omits that reasoning from earlier turns and keeps it out of normal answer text. A gateway that rejects this field can set `preserve_tool_reasoning: false` for that connection. For a deployment that serves this model under a different alias, `preserve_tool_reasoning: true` enables the same behavior after you confirm support. It applies only in native tool mode.

The deployment must parse model output into structured tool calls. NVIDIA's model-specific NIM recipe uses `nemotron_v3` for reasoning and `qwen3_coder` for tools. If text chat succeeds and the diagnostic observes no structured calls, ask the service operator to verify its parser and tool choice settings. The diagnostic sends a result value known only after the synthetic tool response, so merely repeating the original prompt cannot pass.

## Transport and failures

- The saved-model indicator uses a short chat probe. A valid response that exhausts its small output budget can establish reachability. Test connection still requires a complete text reply. Test model and tools checks the separate tool round trip.
- Reasoning uses output tokens in the NVIDIA deployment. If a full request ends with `finish_reason: length`, the task reports the limit and discards the incomplete response before dispatching tools. Adjust **Max output tokens** in Advanced settings to a budget allowed by your deployment.
- HTTP status, timeout, invalid JSON, malformed completion and unexpected SSE have distinct errors. A gateway that streams despite `stream: false` is rejected from its response headers. The HTTP client uses the configured proxy and certificate settings. Redirects are reported without forwarding credentials.
- Model requests use bounded timeouts and retry eligible temporary failures. The transport does not retry local tool side effects. The activity log records observed request phases, latency and an upstream request ID when available. It does not send or display model credentials.
- Model context capacity depends on the actual served profile. Use a verified deployment value or compatible model-list metadata for the context ring. The ring labels the separate local character limit.

## Verify a live deployment

In the approved environment, use the exact working endpoint and model with the connection's current authentication. Run **Test connection**, then **Test model and tools** with Native tool calling selected. Confirm the chat and synthetic tool round trip both pass. Finally, send a two-turn text conversation. Compare the actual reply, elapsed time and any upstream request ID in Activity if a request fails. The supported local tests simulate the NVIDIA contract and exercise real loopback HTTP. The live result depends on the deployed gateway and model configuration.

Official references: [NVIDIA hosted model API](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-super-vl-120b-a12b-infer), [NIM model deployment and reasoning](https://docs.nvidia.com/nim/large-language-models/2.1.6/get-started/advanced/get-started-nemotron-3.5-super-vl.html), [NIM tool calling](https://docs.nvidia.com/nim/large-language-models/2.1.6/advanced-use-cases/tool-calling-and-mcp.html), and [NVIDIA's model chat template](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4/blob/2e5cc3953bb1ea66b2fb7c831fee3aa317427e69/chat_template.jinja).
