<img alt="OCRAgent logo" style="float: right;right: 0px" src="docs/assets/readme-logo-rmbg-640.png" width="96" div align=right>

# OCRAgent

[English](README.md) | [简体中文](README_zh-Hans.md)

[![Publish to PyPI](https://github.com/cxumol/OCRAgent/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/cxumol/OCRAgent/actions/workflows/publish-pypi.yml)
[![PyPI version](https://badge.fury.io/py/ocragent.svg)](https://badge.fury.io/py/ocragent)
<!-- [![PyPI Downloads](https://img.shields.io/pepy/dt/ocragent)](https://pepy.tech/projects/ocragent) -->
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/ocragent)](https://pypi.org/project/ocragent/)

![Brand banner](docs/assets/readme-brand-banner.jpg)

> OCR-first, agent-guided.

OCRAgent is a command-line document parsing workflow. It uses an agent to select OCR, VLM, PDF, office-document, or user-defined tools, then reviews the extracted text before writing output.

The goal is practical routing: use inexpensive extraction when it is enough, and spend model/API cost only on files that need it.

![Core value comparison](docs/assets/readme-core-value-comparison.jpg)

## Grade, Route, Parse, Review

OCRAgent works best for mixed folders: PDFs with text layers, scanned PDFs, images, office files, handwritten pages, tables, forms, and other files that should not all use the same parser.

| Step | What OCRAgent does | Main artifact |
| --- | --- | --- |
| Grade | Inspects file names, metadata, preview signals, and sample pages to estimate parsing difficulty. | `.ocragent_memory.txt` |
| Route | Chooses a parser from builtin tools and user-defined tools according to cost, scope, and prior folder notes. | tool call |
| Parse | Runs the selected tool and writes UTF-8 text while preserving source-relative paths. | `ocragent_results/` |
| Review | Checks whether extracted text is usable; retries with another tool or route when review fails. | accepted output or retry |

The four steps keep the system understandable:

- Grade before spending model/API cost.
- Route through one tool registry.
- Parse through deterministic command boundaries.
- Review before writing final output.

## Runtime Flow

```text
documents
  -> init docs
  -> folder memory
  -> parser agent
  -> parser tool
  -> reviewer agent
  -> output text
```

## Install

Install with common document backends:

```shell
python -m pip install "ocragent[full]"
ocragent --help
```

<details>
<summary>uv</summary>

```shell
uv tool install "ocragent[full]"
ocragent --help
```

</details>

Configure a chat-completions API through environment variables:

```shell
export OCRAGENT_CHAT_BASE=http://localhost:8080/v1
export OCRAGENT_CHAT_MODEL=your-model
export OCRAGENT_CHAT_AUTHKEY=your-key
```

`OPENAI_API_KEY` is also accepted as the auth key. A vision-capable model is strongly recommended, because OCRAgent uses model judgment during grading and review. The same values can be configured in `~/.ocragent/ocragent.settings.toml`, `./ocragent.settings.toml`, or `.env`. Use [src/ocragent/ocragent.settings.default.toml](src/ocragent/ocragent.settings.default.toml) as the reference.

<details>
<summary>Text-only LLM vs multimodal VLM</summary>

| Stage | Text-only LLM | Multimodal VLM |
| --- | --- | --- |
| Grade | Uses file names, metadata, text-layer probes, and OCR samples. It can estimate readability from extracted text, but cannot inspect page images directly. | Uses thumbnails or rendered pages to judge scan quality, handwriting, diagrams, tables, layout density, and whether OCR is likely to fail. |
| Review | Checks whether extracted text reads coherently, whether tables look damaged in text form, and whether obvious OCR artifacts appear. | Can compare extracted text against visual page evidence when available, which is better for missing regions, layout loss, handwriting, formulas, and image-heavy pages. |

</details>

## Quick Start

Run the guided default flow inside a document folder:

```shell
cd /path/to/documents
ocragent --dry-run
ocragent
```

`ocragent --dry-run` prints the stages OCRAgent will run. `ocragent` then starts from the latest safe stage: it reuses existing generated files, creates missing safe runtime files when possible, initializes folder memory when needed, and parses documents into `ocragent_results`.

Parse selected files or folders:

```shell
ocragent invoice.pdf scans/ --out-dir ocragent_results
```

List available tools when you want to inspect the runtime:

```shell
ocragent tool --list
ocragent tool --list --scope=parser
```

If you want OCRAgent to call your own OCR, VLM, shell command, or API, describe those tools in plain text:

```text
$HOME/ocragent.toolbox_user.txt
```

The format can follow [src/ocragent/ocragent.toolbox_user.example.txt](src/ocragent/ocragent.toolbox_user.example.txt). Include tool name, scope, cost, flags, limits, call shape, and required environment variables. On the next `ocragent` run, OCRAgent can generate `$HOME/.ocragent/user_toolbox.py`; review that file before running generated tools with credentials.

For manual control or troubleshooting, run the same stages explicitly:

```shell
ocragent init tools
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
$ ocragent --dry-run
# prints prepare, init tools, init docs, and run decisions

$ ocragent invoice.pdf scans/ --out-dir ocragent_results
# writes parsed files under ocragent_results/
# reports stages_run, parsed_count, failed_count, skipped_count, and failures
```

The commands return JSON in normal use. The example above keeps the flow compact and notes the important fields.

## Output

OCRAgent preserves relative paths:

```text
docs/report.pdf -> ocragent_results/docs/report.pdf.txt
scans/page-01.jpg -> ocragent_results/scans/page-01.jpg.md
```

It also writes a folder memory file:

```text
.ocragent_memory.txt
```

The memory file is prose. It records file groups, difficulty estimates, tool choices, and run summaries. Later parser runs use it as context.

## Architecture

```text
CLI  (ocragent init / run / tool)
 |
AI Agents  (init_tools / parser / reviewer)
 |
Tool chain  (builtin tools + user_toolbox.py)
```

![Architecture diagram](docs/assets/readme-architecture.jpg)

| Plane | Responsibility | Examples |
| --- | --- | --- |
| CLI and commands | Stable command behavior | config, paths, logging, stdout, stderr |
| Tool registry | Parser capability boundary | PDF text, image thumbnails, Pandoc, user OCR, VLM APIs |
| Agent loops | Runtime decisions | file grouping, tool selection, review, retry |

The parser agent does not call vendor APIs directly. It reads the available parser tools, chooses one, runs it through the tool boundary, and sends extracted text to the reviewer. If review fails, the parser can retry with another tool or a higher-cost route.

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

The complete default file is [src/ocragent/ocragent.settings.default.toml](src/ocragent/ocragent.settings.default.toml).

## Documentation

- [User Guide](docs/user-guide.md)
- [Architecture](docs/architecture.md)
- [Agent Loop](docs/agent-loop.md)
- [Tool Mechanism](docs/tool-mechanism.md)
- [Developer Guide](docs/developer-guide.md)

## Contributing

OCRAgent is beta. Breaking changes are still possible.

Useful contributions:

- Add or improve builtin parser tools.
- Add demo assets for real document cases.
- Improve reviewer prompts and failure cases.
- Strengthen tests around CLI behavior, tool discovery, and generated user tools.
- Write adapters for common OCR, VLM, and document conversion backends.
- Improve documentation for tested workflows.

Run tests:

```shell
uv run python -m unittest discover -s tests
uv run --extra pdf python -m unittest discover -s tests
```

Important paths:

- `src/ocragent/cli.py`: command boundary.
- `src/ocragent/cmd/`: command implementations.
- `src/ocragent/cmd/tool.py`: builtin and user tool contract.
- `src/ocragent/agent/`: model-facing loops.
- `src/ocragent/config.py`: layered settings.
- `tests/`: test suite and CLI flow checks.
