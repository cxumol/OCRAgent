<img alt="OCRAgent logo rmbg640" style="float: right;right: 0px" src="docs/assets/readme-logo-rmbg-640.png" width="96" div align=right>

# OCRAgent

[English](README.md) | [简体中文](README_zh-Hans.md)

[![Publish to PyPI](https://github.com/cxumol/OCRAgent/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/cxumol/OCRAgent/actions/workflows/publish-pypi.yml)
[![PyPI version](https://badge.fury.io/py/ocragent.svg)](https://badge.fury.io/py/ocragent)
<!-- [![PyPI Downloads](https://img.shields.io/pepy/dt/ocragent)](https://pepy.tech/projects/ocragent) -->
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/ocragent)](https://pypi.org/project/ocragent/)

![Brand banner](docs/assets/readme-brand-banner.jpg)

> OCR-first, agent-guided.

Document parsing should be tiered, routed, and reviewed. Use cheap local extraction when it is enough. Escalate only when the AI agent finds the page needs it.

- Tesseract OCR cannot handle every decorative typeface or rare character, while a top multimodal model is wasteful for ordinary printed pages. OCRAgent gives easy pages a cheap first pass.
- Different multimodal models have different strengths: handwriting, formulas, tables, scans, and layout recovery ask for different tools. OCRAgent routes work through the tool that fits the page.
- The agent loop adds review. Even a non-vision reviewer can catch rough failures such as broken flow, displaced layout, and drifting tables.
- If you have several OCR models or document APIs and a mixed archive to process, OCRAgent gives them one command-line workflow.

## Why OCRAgent

![Core value comparison](docs/assets/readme-core-value-comparison.jpg)

Instead of "yet another doc parser", OCRAgent is an Agentic Workflow that orchestrates multiple parsing tools for graded document parsing and judgment-based resource allocation.

A cheap parser gets the first try when the document looks easy. Costlier OCR, VLMs, and cloud APIs enter when the content needs them.

OCRAgent gives its agent enough context to assign work by page character instead of treating every model as interchangeable.

## First Run

Install OCRAgent from PyPI with the common document backends:

```shell
python -m pip install "ocragent[full]"
ocragent --help
```

<details>
<summary>Prefer uv?</summary>

```shell
uv tool install "ocragent[full]"
ocragent --help
```

</details>

For LLM-backed commands, configure an OpenAI-compatible chat-completions endpoint:

```shell
export OCRAGENT_CHAT_BASE=http://localhost:8080/v1
export OCRAGENT_CHAT_MODEL=your-model
export OCRAGENT_CHAT_AUTHKEY=your-key
```

`OPENAI_API_KEY` is also accepted as the auth key. The same values can live in `~/.ocragent/ocragent.settings.toml`, `./ocragent.settings.toml`, or `.env`. Use [src/ocragent/ocragent.settings.default.toml](src/ocragent/ocragent.settings.default.toml) as the configuration reference.

List builtin tools:

```shell
ocragent tool --list
```

If you want OCRAgent to call your own OCR, VLM, shell command, or API, describe it in plain text first:

```text
$HOME/ocragent.toolbox_user.txt
```

The toolbox description format can follow [src/ocragent/ocragent.toolbox_user.example.txt](src/ocragent/ocragent.toolbox_user.example.txt). Tool descriptions can be copied from the vendor's official docs, trimmed to name, scope, cost, flags, limits, and call shape. Put secrets such as API keys in environment variables, then name those variables in the toolbox prose.

Then generate the tool runtime:

```shell
ocragent init tools
```

OCRAgent writes executable Python to `$HOME/.ocragent/user_toolbox.py`. Review that file before using it with real credentials.

Then parse a folder:

```shell
cd /path/to/documents
ocragent init docs
ocragent run --out-dir ocragent_results
```

## CLI Example

```text
$ ocragent tool --list --scope=parser
pdf2txt	scope: parser cost: low	Extract PDF text with PyMuPDF.
	--path /path/to/file.pdf

pdf_pages_to_images	scope: parser cost: medium	Render each PDF page to a PNG image with PyMuPDF.
	--path /path/to/file.pdf
	--out-dir /path/to/page-images

pandoc2txt	scope: parser cost: low	Convert office documents to plain text with Pandoc.
	--path /path/to/file

$ cd ~/cases/mixed_docs
$ ocragent init tools --from ./ocragent.toolbox_user.txt
{
  "ok": true,
  "usertools_valid": [
    "siliconflow_deepseekocr"
  ],
  "usertools_failed": [],
  "agent_turns": 1,
  "result_file": "/home/me/.ocragent/user_toolbox.py"
}

$ ocragent init docs
{
  "ok": true,
  "result_file": "/home/me/cases/mixed_docs/.ocragent_memory.txt",
  "groups": [
    {
      "name": "pdf_text",
      "...": "..."
    }
  ],
  "file_count": 18,
  "unmatched_count": 0
}

$ ocragent run invoice.pdf scans/ --out-dir ocragent_results
{
  "ok": true,
  "out_dir": "/home/me/cases/mixed_docs/ocragent_results",
  "parsed_count": 18,
  "failed_count": 0,
  "skipped_count": 0,
  "results": [
    {
      "source": "invoice.pdf",
      "output_file": "/home/me/cases/mixed_docs/ocragent_results/invoice.pdf.txt",
      "...": "..."
    }
  ],
  "failures": [],
  "skipped": [],
  "output_stats": {
    "file_count": 18,
    "...": "..."
  }
}
```

The JSON examples above keep the real field names and shorten long arrays with `"..."`.

## What You Get

OCRAgent preserves relative paths in the output directory:

```text
docs/report.pdf -> ocragent_results/docs/report.pdf.txt
scans/page-01.jpg -> ocragent_results/scans/page-01.jpg.md
```

It also maintains a folder memory file:

```text
.ocragent_memory.txt
```

That memory is plain prose. It helps later parser runs choose a sensible starting cost without forcing the project into a rigid database schema.

## Architecture

```text
CLI  (ocragent init / run / tool)
 |
AI Agents  (init_tools / parser / reviewer)
 |
Tool chain  (builtin tools + user_toolbox.py)
```

![Architecture diagram](docs/assets/readme-architecture.jpg)

OCRAgent has three working planes:

| Plane | Owns | Examples |
| --- | --- | --- |
| CLI and commands | Stable behavior | config, paths, logging, stdout and stderr contracts |
| Tool plane | Extraction capability | PDF text, image thumbnails, Pandoc, user OCR, VLM APIs |
| Agent plane | Judgment under uncertainty | grouping files, choosing tools, reviewing extracted text |

The parser never calls vendors directly. It asks the tool registry what is available, runs a parser through the same boundary as the CLI, and sends candidate text to review before writing output. When the review fails, the agent can retry with another tool or a higher-cost route, guided by folder memory and the last failure.

## Configuration

Configuration priority:

1. Environment variables.
2. `./ocragent.settings.toml`.
3. `~/.ocragent/ocragent.settings.toml`.
4. Package defaults.

Common settings:

```toml
[aigc.api.chatcomp]
base = "http://localhost:8080/v1"
authkey = ""
model = ""
model_hasVision = true

[output]
dir = "ocragent_results"
ext = "auto"
parser_summary_batch = 5

[reviewer]
max_length = 1000
```

The complete default shape is in [src/ocragent/ocragent.settings.default.toml](src/ocragent/ocragent.settings.default.toml).

## Contributing

OCRAgent is beta, which makes it a good time to shape the core. Useful contributions are small and concrete:

- Add or improve builtin parser tools.
- Add demo assets that represent real document pain.
- Improve reviewer prompts and failure cases.
- Strengthen tests around CLI behavior, tool discovery, and generated user tools.
- Write adapters for common OCR, VLM, and document conversion backends.
- Improve docs for a workflow you actually tried.

Start with:

```shell
uv run python -m unittest discover -s tests
uv run --extra pdf python -m unittest discover -s tests
```

Useful code paths:

- `src/ocragent/cli.py`: command boundary.
- `src/ocragent/cmd/`: command implementations.
- `src/ocragent/cmd/tool.py`: builtin and user tool contract.
- `src/ocragent/agent/`: model-facing loops.
- `src/ocragent/config.py`: layered settings.
- `tests/`: current test suite and CLI flow checks.

## Documentation

- [User Guide](docs/user-guide.md)
- [Architecture](docs/architecture.md)
- [Agent Loop](docs/agent-loop.md)
- [Tool Mechanism](docs/tool-mechanism.md)
- [Developer Guide](docs/developer-guide.md)

## Status

OCRAgent is beta. The command shape is usable, and breaking changes are still possible. The project is looking for contributors who care about document extraction, local-first tooling, and agent workflows with clear boundaries.
