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

Configure a chat-completions API through environment variables:

```shell
export OCRAGENT_CHAT_BASE=http://localhost:8080/v1
export OCRAGENT_CHAT_MODEL=your-model
export OCRAGENT_CHAT_AUTHKEY=your-key
```

`OPENAI_API_KEY` is also accepted as the auth key. A vision-capable model is strongly recommended, because OCRAgent uses model judgment during grading and review. The same values can live in `./ocragent.settings.toml`, `~/.ocragent/ocragent.settings.toml`, or `.env`.

<details>
<summary>Text-only LLM vs multimodal VLM</summary>

| Stage | Text-only LLM | Multimodal VLM |
| --- | --- | --- |
| Grade | Uses filenames, metadata, text-layer probes, and OCR samples. It cannot inspect page images directly. | Uses thumbnails or rendered pages to judge scan quality, handwriting, diagrams, tables, layout density, and OCR risk. |
| Review | Checks text coherence, obvious OCR artifacts, repeated noise, and table damage in text form. | Can compare text against visual evidence when page images are available, which helps with missing regions, layout loss, handwriting, formulas, and image-heavy pages. |

</details>

## Grade, Route, Parse, Review

| Step | What happens | Common artifact |
| --- | --- | --- |
| Grade | Estimate parsing difficulty from filenames, metadata, previews, and samples. | `.ocragent_memory.txt` |
| Route | Pick a parser from builtin tools and user tools by scope, cost, and folder memory. | tool call |
| Parse | Run the selected parser and write UTF-8 text or Markdown. | `ocragent_results/` |
| Review | Check whether extraction is usable; retry with another route when needed. | accepted output or retry |

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
