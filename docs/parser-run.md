# Parser Run

`pennyparse run` is the document parsing entrypoint.

## Usage

```shell
pennyparse run
pennyparse run --out-dir pennyparse_results
pennyparse run invoice.pdf scans/
```

When `./.pennyparse_memory.txt` exists, its file list and group cost baselines guide the run. Without memory, PennyParse walks the current directory.

## Parser Selection

The parser agent uses available `scope=parser` tools that accept `--path` and return text or JSON.

- PDF files prefer `pdf2txt`.
- Office-style documents prefer `pandoc2txt`.
- User parser tools can handle images and higher-cost parsing backends.
- Group `cost_baseline` from `.pennyparse_memory.txt` is used as a soft ranking signal.

## Reviewer

The reviewer marks empty extraction as `major_revision`.

When no chat model is configured, non-empty local extraction is accepted. When a chat model is configured, the reviewer asks it for `pass`, `minor_revision`, or `major_revision` JSON and writes the revised text for minor revisions.

Reviewer prompt input is truncated by `[output].max_length`.

## Output

Each successful source writes one UTF-8 text file under the output directory. The source relative path is preserved, and the original filename is kept in the output name:

```text
docs/report.pdf -> pennyparse_results/docs/report.pdf.txt
```
