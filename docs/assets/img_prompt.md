# OCRAgent Image Regeneration Prompts

These prompts describe the desired visual direction for refreshed README and docs assets. Use the existing images in `docs/assets/` only as style references, not as strict edit targets. Preserve the colored-pencil handmade brand language while updating the product story to match the current docs: `OCRAgent` is a command-line document parsing workflow with Autonomous Mode, deterministic command boundaries, a shared tool registry, and agent loops for grading, routing, parsing, and review.

## Shared Visual Language

Colored-pencil illustration on lightly textured warm paper. Refined but handmade. Clear information hierarchy, readable labels, generous whitespace, no photorealistic stock-image look, no dark blur, no glassmorphism, no decorative gradients. Use brass gold for the balance scale, ink blue for command/system structure, muted green for tools, amber for agent judgment, gray for local state, purple for local compute, soft orange for AI/API compute, and red only for failure or retry marks.

Text must be sparse and verbatim. Spell `OCRAgent` exactly. Avoid tiny labels, filler copy, vendor logos, watermarks, and invented slogans. The refreshed diagrams must not reduce the product to a generic router. They should show a practical workflow: grade cheaply, route through tools, parse through deterministic boundaries, review before writing output.

## Brand Banner

A wide GitHub README hero banner. On the left, a brass balance scale drawn in colored pencil: one pan holds a parchment scroll, bamboo slips, ordinary documents, and a USB drive; the other pan holds gold, silver, and copper coins. On the right, a clean title block with exact text:

```text
OCRAgent
OCR-first, agent-guided.
何须一模破万卷，智能调度在慧枢。
```

The image should feel warm, literate, and technical without becoming ornate. Keep the title large and readable at README width. Use the current logo idea as inspiration, but do not copy any accidental text artifacts from the old banner.

## Core Value Comparison

A two-panel infographic. Left panel: `One parser for all`. A single bulky OCR machine receives mixed inputs such as a text PDF, scanned PDF, sticky-note handwriting, table/chart page, and photo document. Some pages come out rejected, some text is garbled, and coins are wasted.

Right panel: `OCRAgent`. Mixed files enter a four-step flow labeled exactly:

```text
Grade
Route
Parse
Review
```

The flow chooses tools by difficulty, cost, availability, and quality. Show tool choices as small stations labeled:

```text
PDF text
OCR
VLM
Pandoc
User tool
```

Outputs should be labeled `UTF-8 text`, not only Markdown. The picture should communicate that OCRAgent spends cheap tools first, escalates when needed, and accepts output only after review.

## README Architecture Diagram

A compact system diagram for the README. Use four horizontal bands:

1. `CLI` and `Autonomous Mode`, including bare `ocragent`.
2. Deterministic command layer: `prepare`, `init tools`, `init docs`, `run`, `summarize`.
3. Agent and tool layer: `Agents` with `init_tools`, `parser`, `reviewer`; `Tool Registry` with `builtin tools`, `user_toolbox.py`, and scopes `previewer`, `parser`, `reviewer`.
4. Local state and outputs: `.ocragent_memory.txt`, `ocragent.log`, `ocragent_results`.

Arrows should show that agents choose and review through the tool boundary, while command code owns paths, config, logging, validation, and output writes. Include the phrase `review before write`. Do not put `OCRAgent Router` as the sole central object.

## Detailed Developer Architecture Poster

A larger developer-guide diagram. Preserve the old diagram's intent of multi-dimensional encoding, but update the content. Include a legend for:

- interaction channel
- capability type
- logic pattern
- compute nature

The default user flow should begin with bare `ocragent`, then show optional explicit commands for manual control. Include:

```text
Autonomous Mode
prepare
init tools
init docs
run
summarize
```

Configuration hierarchy must include:

```text
Environment variables
.env
CWD settings
Home settings
Package defaults
```

Show the tool registry with builtin tools and generated user tools, including `previewer`, `parser`, `reviewer`, `cost`, `secrets`, `flags`, and availability. Show agentic loop modes `tool_calls` and `pseudo-XML`. Show parser review loop and reviewer regex repair loop with deterministic validators around model output. Include local state and resources:

```text
.ocragent_memory.txt
user_toolbox.py
ocragent.log
ocragent_results
```

The result should be a readable technical poster, not a dense wall of tiny boxes.
