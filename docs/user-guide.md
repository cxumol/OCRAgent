# User Guide

OCRAgent turns a mixed document folder into UTF-8 text. It works best when you initialize the folder once, let it learn cheap signals about the files, then parse through a stable tool set.

The workflow has four steps: grade, route, parse, and review. Embedded PDF text, clean scans, decorative type, handwriting, formulas, and tables do not deserve the same parser or the same bill.

| Step | What happens |
| --- | --- |
| Grade | Estimate parsing difficulty from filenames, metadata, previews, and samples. |
| Route | Pick a parser from builtin tools and user tools by scope, cost, and folder memory. |
| Parse | Run the selected tool and write UTF-8 text under the output directory. |
| Review | Check whether extraction is usable; retry with another route when needed. |

## Install And Configure

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

Configure a chat-completions API through environment variables:

```shell
export OCRAGENT_CHAT_BASE=http://localhost:8080/v1
export OCRAGENT_CHAT_MODEL=your-model
export OCRAGENT_CHAT_AUTHKEY=your-key
```

`OPENAI_API_KEY` is also accepted as the auth key. A vision-capable model is strongly recommended, because OCRAgent uses model judgment during grading and review. You can put the same values in `~/.ocragent/ocragent.settings.toml`, `./ocragent.settings.toml`, or `.env`. Use [../src/ocragent/ocragent.settings.default.toml](../src/ocragent/ocragent.settings.default.toml) as the configuration reference.

<details>
<summary>Text-only LLM vs multimodal VLM</summary>

| Stage | Text-only LLM | Multimodal VLM |
| --- | --- | --- |
| Grade | Uses filenames, metadata, text-layer probes, and OCR samples. It cannot inspect page images directly. | Uses thumbnails or rendered pages to judge scan quality, handwriting, diagrams, tables, layout density, and OCR risk. |
| Review | Checks text coherence, obvious OCR artifacts, repeated noise, and table damage in text form. | Can compare text against visual evidence when page images are available, which helps with missing regions, layout loss, handwriting, formulas, and image-heavy pages. |

</details>

The `full` extra includes the common local document backends. Minimal installs are possible, but most users should start with `ocragent[full]`.

## Run Guided Flow

Run `ocragent` inside the folder that contains the documents:

```shell
cd /path/to/documents
ocragent --dry-run
ocragent
```

`ocragent --dry-run` prints the planned stages without modifying files. `ocragent` starts from the latest safe stage, creates missing safe runtime files when possible, initializes folder memory when needed, and then parses documents.

Parse selected files or directories:

```shell
ocragent invoice.pdf scans/ --out-dir ocragent_results
```

Autonomous Mode reuses existing generated assets. If `${HOME}/.ocragent/user_toolbox.py` is missing and `${HOME}/ocragent.toolbox_user.txt` exists, it runs `init tools` first. If `.ocragent_memory.txt` is missing, it runs `init docs` before parsing. With no toolbox TXT, it creates a builtin-only runtime and continues when the remaining state is sufficient. Use `--yes` to accept non-destructive review prompts and `--force` to regenerate initialization assets.

Each successful source writes one UTF-8 text file under the output directory. The source-relative path is preserved:

```text
docs/report.pdf -> ocragent_results/docs/report.pdf.txt
```

During a run, OCRAgent appends short batch notes and a final output summary to `.ocragent_memory.txt`. The notes help future runs and do not need hand editing.

## Use External Tools

Create a toolbox description at `${HOME}/ocragent.toolbox_user.txt`, or pass another file with `--from`. Follow the shape in [../src/ocragent/ocragent.toolbox_user.example.txt](../src/ocragent/ocragent.toolbox_user.example.txt).

Describe each external parser or API in plain technical prose: name, scope, cost, flags, strengths, limits, and how to call it. Vendor tool descriptions can be copied from official docs and trimmed to the facts OCRAgent needs. Keep secrets in environment variables, then name those variables in the toolbox prose.

On the next `ocragent` run, OCRAgent can generate `${HOME}/.ocragent/user_toolbox.py`. Review that file before running generated tools with credentials.

Generate or regenerate the runtime manually:

```shell
ocragent init tools
ocragent init tools --from ./ocragent.toolbox_user.txt --force
```

## Manual Workflow

Use the explicit stages when you want direct control over initialization and parsing:

```shell
cd /path/to/documents
ocragent init docs
ocragent run --out-dir ocragent_results
```

`ocragent init docs` writes `./.ocragent_memory.txt`. It is prose used as guidance. It records file groups, rough parsing difficulty, and cheap preview observations so later runs can start with better tool choices.

Files and folders listed under `[init.ignore]` in `ocragent.settings.toml` are excluded when `init docs` scans the folder and when `run` walks directories.

The full initialization command runs both init stages:

```shell
ocragent init --from /path/to/ocragent.toolbox_user.txt --force
```

Its JSON output uses `result_file` for generated paths. `init docs` returns `groups` as a list of group records, plus `file_count` and `unmatched_count`.

Manual parsing also accepts selected files or directories:

```shell
ocragent run invoice.pdf scans/ --out-dir ocragent_results
```

`ocragent run` requires both `${HOME}/.ocragent/user_toolbox.py` and `./.ocragent_memory.txt`. Its JSON summary reports `parsed_count`, `failed_count`, `skipped_count`, detailed `results`, `failures`, `skipped`, and `output_stats`.

## Inspect Tools

```shell
ocragent tool --list
ocragent tool --list --scope=parser
ocragent tool pdf2txt --help
ocragent tool pdf2txt --path report.pdf
```

Parser tool list output includes each available tool and its flags, for example `pdf2txt`, `pdf_pages_to_images`, and `pandoc2txt` when their optional backends are installed.

Unavailable tools are skipped from normal list output and logged with their reason. Common causes are missing optional Python packages or missing secret environment variables.

## Configuration

Configuration priority, from strongest to weakest:

1. Environment variables.
2. `./ocragent.settings.toml`.
3. `~/.ocragent/ocragent.settings.toml`.
4. Package defaults.

Useful settings:

```toml
[aigc.api.chatcomp]
base = "http://localhost:8080/v1"
authkey = ""
model = ""

[output]
dir = "ocragent_results"
ext = "auto"

[reviewer]
max_length = 1000
```

The full default settings file is [../src/ocragent/ocragent.settings.default.toml](../src/ocragent/ocragent.settings.default.toml).

## FAQ

**Do I need a chat model for every command?**

No. Tool listing and many local parsing paths can run without one. `init tools` and `init docs` need a configured model because they ask an agent to synthesize tools or read the shape of a folder. A vision-capable model gives better grading and review signals for scanned, handwritten, formula-heavy, or layout-heavy files.

**Why did a PDF become page images?**

The parser tried text extraction first. If review rejected it and the PDF image backend was available, OCRAgent rendered pages, parsed each image, merged the page text, and reviewed the merged result.

**Why is `.ocragent_memory.txt` prose?**

Because it is guidance for ranking and summarization. Filesystem discovery, tool validation, and output writing remain deterministic.

**Where should errors be read?**

The CLI prints command results to `stdout`, concise errors to `stderr`, and detailed logs to `ocragent.log` in the working directory.
