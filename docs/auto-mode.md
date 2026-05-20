# Autonomous Mode

Autonomous Mode is the default guided workflow for `ocragent`. It checks the current state, starts from the latest safe stage, and runs the document parsing flow with minimal user input.

The mode follows the same four-step model as the rest of OCRAgent:

| Step | Meaning |
| --- | --- |
| Grade | Inspect files and write folder memory. |
| Route | Choose parser tools by scope, cost, availability, and memory. |
| Parse | Run parser tools and write output files. |
| Review | Check extracted text before accepting output. |

## Command Shape

```shell
ocragent [paths...] [--out-dir ocragent_results] [--force] [--yes] [--dry-run]
```

If `paths` is empty, OCRAgent uses the current directory. Paths may be files or directories. Directory traversal follows the same ignore rules as `ocragent init docs` and `ocragent run`.

Common options:

- `--out-dir`: output directory for parsed files.
- `--force`: allow overwriting generated initialization assets.
- `--yes`: allow non-destructive confirmations in interactive flows.
- `--dry-run`: print the planned stages and stop before modifying files.

## State Detection

Autonomous Mode checks these inputs before running:

- chat-completions configuration: `OCRAGENT_CHAT_BASE`, `OCRAGENT_CHAT_MODEL`, `OCRAGENT_CHAT_AUTHKEY`, or compatible settings files;
- user toolbox description: `${HOME}/ocragent.toolbox_user.txt` or a configured path;
- generated user toolbox runtime: `${HOME}/.ocragent/user_toolbox.py`;
- folder memory: `./.ocragent_memory.txt`;
- output directory: `--out-dir` or configured default;
- available builtin and user tools.

A vision-capable chat model is strongly recommended. Without one, grading and review can still use filenames, metadata, text-layer probes, OCR samples, and extracted text, but cannot inspect rendered pages directly.

## Start Point Selection

Autonomous Mode starts from the latest stage that is safe and recoverable.

| Current state | Action |
| --- | --- |
| `user_toolbox.py` exists and `.ocragent_memory.txt` exists | Run parsing. |
| `user_toolbox.py` exists and `.ocragent_memory.txt` is missing | Run `init docs`, then parsing. |
| `user_toolbox.py` is missing, toolbox TXT exists, chat is configured | Run `init tools`, then `init docs`, then parsing. |
| `user_toolbox.py` is missing, toolbox TXT is missing, builtin-only mode is acceptable | Generate or reuse a minimal builtin-only runtime, then continue. |
| `user_toolbox.py` is missing, toolbox TXT is missing, builtin-only mode is not acceptable | Stop and ask for toolbox TXT. |
| Chat config is missing and an agent-backed init stage is required | Stop and report the missing chat configuration. |
| Existing generated files would be overwritten | Reuse them by default; overwrite only with `--force`. |

Builtin-only mode means no external OCR, VLM, shell command, or API tools are added. It is suitable when the user wants to parse with packaged local tools only.

## Stage Plan

The normal stage plan is:

```text
prepare
  -> init tools, if needed
  -> init docs, if needed
  -> run
  -> summarize
```

`prepare` validates configuration and files. `init tools` creates `${HOME}/.ocragent/user_toolbox.py`. `init docs` creates `./.ocragent_memory.txt`. `run` performs routing, parsing, and review. `summarize` reports output counts and failure paths.

## Output And Progress

Autonomous Mode preserves the CLI stream contract:

- final machine-readable summaries go to `stdout`;
- progress, warnings, confirmations, and logs go to `stderr`;
- detailed runtime logs go to `./ocragent.log`.

In an interactive terminal, progress may be displayed as a compact status area:

```text
stage: init docs
files scanned: 42
current: scans/page-12.png
```

In a non-interactive terminal, OCRAgent prints ordinary line-based progress to `stderr`. It must not use dynamic terminal updates that make logs hard to read.

## Interactive And Non-Interactive Behavior

Interactive mode may ask for confirmation when:

- generated tool code was created and should be reviewed before use;
- builtin-only mode is about to be used because no toolbox TXT exists;
- an existing generated file would be overwritten;
- a failed stage can be retried safely.

Non-interactive mode must not wait for input. It should either continue with safe defaults or exit with a structured error that includes the next command to run.

`--yes` answers safe confirmations automatically. It must not imply destructive overwrite; `--force` is still required for overwriting generated initialization assets.

## Overwrite Rules

Autonomous Mode is conservative by default.

- Existing `${HOME}/.ocragent/user_toolbox.py` is reused.
- Existing `./.ocragent_memory.txt` is reused.
- `--force` allows regeneration of init assets.
- Existing output files are not deleted.
- If a target output path already exists, OCRAgent should follow the same policy as `ocragent run`: overwrite, skip, or version according to configured output behavior.

The mode must never remove output directories as part of recovery.

## Generated Tool Safety

`init tools` writes executable Python. If generated user tools include shell commands, local binaries, or remote API calls, Autonomous Mode should require review before continuing in an interactive session.

Safe defaults:

- generated external-tool runtime: pause for review unless `--yes` is set;
- generated builtin-only runtime: continue without review;
- non-interactive generated external-tool runtime without `--yes`: stop with a clear message.

Secrets must remain in environment variables or `.env`. Autonomous Mode must not ask users to pass API keys through argv.

## Failure And Retry

Failures are reported by stage.

| Stage | Common failure | Recovery |
| --- | --- | --- |
| prepare | missing chat config | print required environment variables and stop. |
| init tools | invalid generated runtime | retry through the normal repair loop until max iterations. |
| init docs | missing toolbox runtime or unavailable preview tools | run earlier stage if possible, otherwise stop with next step. |
| run | parser failure for some files | preserve successful outputs and report failed paths. |
| review | rejected extraction | retry with another parser route if available. |

In interactive mode, OCRAgent may ask whether to retry after an unexpected transient failure. In non-interactive mode, it should return a non-zero exit code and print the stage, error summary, and suggested next command.

## Dry Run

`--dry-run` prints the planned actions without modifying files.

Example:

```text
prepare: ok
init tools: skip, user_toolbox.py exists
init docs: run, .ocragent_memory.txt missing
run: run, out-dir ocragent_results
```

Dry runs should still validate obvious configuration and file presence, but should not call model endpoints, generate files, or parse documents.

## Summary

The final JSON summary should include:

- `ok`;
- `stages_run`;
- `out_dir`;
- `parsed_count`;
- `failed_count`;
- `skipped_count`;
- `failures`;
- `skipped`;
- `log_file`;
- `memory_file`;
- `toolbox_file`.

Human-readable status can be printed to `stderr`, but `stdout` should remain suitable for scripts.
