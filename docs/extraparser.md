# Extraparser Endpoints

`POST /extraparser/pdf2txt`

- Send raw PDF bytes in the request body.
- Accepts `Content-Type: application/pdf` or `application/octet-stream`.
- Returns extracted plain text.

`POST /extraparser/pdfmetadata`

- Send raw PDF bytes in the request body.
- Accepts `Content-Type: application/pdf` or `application/octet-stream`.
- Returns JSON with `pageCount`, `wordCount`, and `TOC`.

`POST /extraparser/pandoc2txt`

- Send raw document bytes in the request body.
- Set query parameter `fmt` to the pandoc input format, for example `docx`, `odt`, `rtf`, `html`, `markdown`, `epub`.
- If `fmt` is omitted, the server tries to infer it from `Content-Type`.
- Returns pandoc's plain-text output.
