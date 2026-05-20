# Toolbox And Configuration

## Install And Entry Points

Prefer a virtual environment on user machines:

```shell
python -m venv .venv
. .venv/bin/activate
python -m pip install "ocragent[full]"
```

If the `ocragent` console script is not on `PATH`, use the module entry:

```shell
python -m ocragent --help
```

If optional backends fail to install, use the base package and inspect available tools:

```shell
python -m pip install ocragent
ocragent tool --list
```

## Chat Endpoint

LLM-backed commands need an OpenAI-compatible chat-completions endpoint:

```shell
export OCRAGENT_CHAT_BASE=http://localhost:8080/v1
export OCRAGENT_CHAT_MODEL=your-model
export OCRAGENT_CHAT_AUTHKEY=your-key
```

`OPENAI_API_KEY` is also accepted as the auth key. The same values can live in `./ocragent.settings.toml`, `~/.ocragent/ocragent.settings.toml`, or `.env`.

## User Toolbox

A toolbox description is plain prose. Include only facts the generator needs:

- tool name
- scope, usually `parser` or `previewer`
- cost, one of `very low`, `low`, `medium`, `high`, `very high`
- supported file types
- required flags
- required secret environment variables
- request shape or shell command
- output shape
- known limits

Example:

```text
my_ocr_api

Scope: parser
Cost: medium
Input: image files through --path /path/to/image.png
Secrets: MY_OCR_API_KEY
Call: POST https://example.test/v1/ocr with multipart file upload and Bearer auth.
Output: return only recognized Markdown text.
Limits: max 10 MB per file.
```

Generate the runtime:

```shell
ocragent init tools --from ./ocragent.toolbox_user.txt
```

OCRAgent writes `${HOME}/.ocragent/user_toolbox.py`. Treat it as executable generated code and review it before using real credentials.

## Sandboxed HOME

If the runtime cannot read or write the real home directory, use a writable workspace directory:

```shell
HOME=/path/to/workspace-home ocragent init tools --from ./ocragent.toolbox_user.txt
HOME=/path/to/workspace-home ocragent init docs
HOME=/path/to/workspace-home ocragent run --out-dir ocragent_results
```

Keep the same `HOME` across `init tools`, `init docs`, and `run`, otherwise OCRAgent will look for a different `user_toolbox.py`.

## Generated Files

- `${HOME}/.ocragent/user_toolbox.py`: generated Python tool runtime.
- `./.ocragent_memory.txt`: folder-local parsing memory, created by `init docs`.
- `./ocragent.log`: command log in the current working directory.
- `./ocragent_results/`: default output directory unless configured or overridden.

## Useful Commands

```shell
ocragent tool --list
ocragent tool --list --scope=previewer
ocragent tool --list --scope=parser
ocragent tool <toolname> --help
ocragent tool <toolname> --path /path/to/file
```
