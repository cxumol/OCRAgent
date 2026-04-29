# Init Docs

`pennyparse init` generates the user toolbox and then scans the current directory, enriches file metadata with available previewer tools, groups files, and writes a natural-language `./.pennyparse_memory.txt`.

`pennyparse init docs` runs only the docs step.

The root `pennyparse.log` runtime file is skipped during scanning.

## Prerequisites

- Generate the user toolbox first:
  - `pennyparse init tools`
- Configure the chat model (required):
  - `PENNYPARSE_CHAT_MODEL` (and optionally `PENNYPARSE_CHAT_BASE`, `PENNYPARSE_CHAT_AUTHKEY` / `OPENAI_API_KEY`)
  - or `~/.pennyparse/pennyparse.settings.toml` / `./pennyparse.settings.toml` under `[aigc.api.chatcomp]`

If LLM grouping is unavailable at runtime, the command falls back to extension and preview metadata heuristics.

## Usage

Run inside the directory that contains your documents:

```bash
cd /path/to/my_docs
pennyparse init
```

Run only the docs step:

```bash
pennyparse init docs
```

Pass a non-default toolbox source into the full init sequence:

```bash
pennyparse init --from /path/to/pennyparse.toolbox_user.txt
```

Overwrite existing generated init assets:

```bash
pennyparse init --force
```

The command prints a JSON summary to `stdout` and writes natural-language parser context to `./.pennyparse_memory.txt`.

The memory file includes:

- one sentence for each group, covering filename traits, estimated parsing difficulty, and the suggested starting cost baseline
- short sample observations when a sampled PDF, image, or Office file can be previewed or parsed by an available very low, low, or medium cost `--path` tool
- one overall sentence covering the folder-level difficulty estimate and the suggested overall starting cost baseline

The memory file is intentionally not JSON. Runtime parser selection may read it as soft context, but it must not depend on a machine-readable `files` or `groups` schema.

## Configuration

Use `./pennyparse.settings.toml` (project) or `~/.pennyparse/pennyparse.settings.toml` (user) to customize:

- `[init.ignore]`
  - `ext`: extensions to ignore (without leading dots)
  - `folder`: folder names to skip during directory walk
- `[init.sampling]`
  - `by`: `first`, `random`, or `none`
  - `num`: sampled files per group
  - `pdf_page`: planned pages per sampled PDF
  - `pdf_page_total_max`: total planned pages per group

## Optional previewer dependencies

Some metadata enrichment is skipped unless these Python modules are importable:

- `PIL` (image width/height)
- `pymupdf` (PDF page/word counts)

Generated user tools with `scope = "previewer"` are also discovered. If they accept `--path`, their JSON or text result can contribute to the natural-language group summaries.

For sampled PDFs, images, and Office files, `init docs` also tries available very low, low, or medium cost tools that accept `--path`. Text results are clipped, simple JSON values are summarized, binary previews are ignored, and failures are logged without aborting initialization.
