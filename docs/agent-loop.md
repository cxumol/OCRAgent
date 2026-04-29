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

The parser and reviewer modules expose the target `tool_calls` mode while keeping a deterministic local fallback path. Parser tools are selected from available `scope = "parser"` tools, and reviewer output is normalized to `pass`, `minor_revision`, or `major_revision`.
