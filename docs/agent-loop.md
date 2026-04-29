# Agent Loop

PennyParse agents declare their intended implementation mode with `_AGENT_IMPL_MODE`.

- `agent/init_tools.py`: `pesudo_XML`
- `agent/parser.py`: `tool_calls`
- `agent/reviewer.py`: `tool_calls`

## Init Tools

The user-tool generator accepts the pseudo-XML shape:

````text
<full_file_code>
```python
...
```
</full_file_code>
````

Repair turns feed validation failures back to the model. The extractor also accepts a bare fenced Python block for older responses.

## Parser And Reviewer

The reusable `tool_calls` loop lives in `utils_aigc.run_tool_calls_loop`.

Loop behavior:

- Calls the chat model with `tools`.
- Executes every returned tool call through a name-to-handler mapping.
- Appends tool results to the same chat session.
- Returns the first assistant message without tool calls.
- Stops at `[aigc.agent].max_iter`.

Errors are layered:

- Chat completion failures are retried with exponential backoff up to `[aigc.agent].max_retry`.
- Tool handler exceptions are captured as JSON tool results so the model can react.
- Malformed tool-call arguments and unknown tool names are also returned as tool results.

The parser and reviewer modules expose the target `tool_calls` mode while keeping a deterministic local fallback path. Parser tools are selected from available `scope = "parser"` tools, and reviewer output is normalized to `pass`, `minor_revision`, or `major_revision`.

## Reviewer Regex Repair

The reviewer has one tool-call repair tool: `myregexpatch`.

`myregexpatch` accepts `before_len`, `after_len`, and a chain of `re.sub` patch objects. The program applies the chain to the initial parser text received by the reviewer and returns only an audit result: status, summary, patch count, replacement count, and text lengths. It does not return the revised full text to the model.

A later repair turn is evaluated against the same initial text, not against the previous revised text. This keeps generated regex patches reproducible and avoids compounding accidental edits. The final reviewer decision still uses the normalized `pass`, `minor_revision`, or `major_revision` status.
