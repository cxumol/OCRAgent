# Parser Run

`pennyparse run` is the document parsing entrypoint.

## Usage

```shell
pennyparse run
pennyparse run --out-dir pennyparse_results
pennyparse run invoice.pdf scans/
```

When explicit paths are omitted, PennyParse walks the current directory. If `./.pennyparse_memory.txt` exists, the parser reads its natural-language notes as soft context for tool ordering.

The command requires the normal initialization files:

- `~/.pennyparse/user_toolbox.py`
- `./.pennyparse_memory.txt`

## Parser Selection

The parser agent uses available `scope=parser` tools that accept `--path` and return text or JSON.

- PDF files prefer `pdf2txt`.
- If PDF text extraction fails review, the parser calls `pdf_pages_to_images` and parses each rendered page image recursively.
- Office-style documents prefer `pandoc2txt`.
- User parser tools can handle images and higher-cost parsing backends.
- Natural-language cost hints from `.pennyparse_memory.txt` are used as a soft ranking signal.

PDF page recursion is bounded to one fallback layer: original PDF -> page PNG files. The page images are written under:

```text
pennyparse_results/.pennyparse_pages/<source-relative-pdf-path>/page-0001.png
```

The final PDF output remains one file for the original PDF. Page parser results are merged in page order with stable headings:

```text
## Page 1

...

## Page 2

...
```

`pdf_pages_to_images` depends on PyMuPDF. When PyMuPDF is not importable, the tool stays unavailable and PDF fallback is skipped.

## Reviewer

The reviewer marks empty extraction as `major_revision`.

When no chat model is configured, non-empty local extraction is accepted. When a chat model is configured, the reviewer asks it for `pass`, `minor_revision`, or `major_revision` JSON.

Reviewer prompt input is truncated by `[reviewer].max_length`. This truncation is only for audit context. A `pass` result writes the parser tool's complete original text, and a `minor_revision` result writes the complete original text after applying reviewer-provided regex patches.

## Output

Each successful source writes one UTF-8 text file under the output directory. The source relative path is preserved, and the original filename is kept in the output name:

```text
docs/report.pdf -> pennyparse_results/docs/report.pdf.txt
```

## Memory Updates

Runtime memory is append-only. Normal `pennyparse run` opens `./.pennyparse_memory.txt` only for reading and appending.

After each `[output].parser_summary_batch` parsed files, the command appends one compact batch line of at most 20 non-whitespace characters. The line summarizes the batch's source filename signal and parser tools.

At the end of the run, the command appends an output summary with parsed count, failure count, output file count, byte count, and output suffix counts.
