# 用户指南

OCRAgent 把一个目录里的杂文档，理成可读、可检索、可再处理的 UTF-8 文本。推荐走法很清楚：先准备工具，再让它看一遍目录，最后开始解析。

工作流分为四步：分级、分配、解析、复查。普通文字层、清爽扫描页、手写稿、公式、表格，各有各的读法。

| 步骤 | 做什么 |
| --- | --- |
| 分级 | 根据文件名、元数据、预览和抽样估计解析难度。 |
| 分配 | 根据 scope、成本和目录记忆，从内建工具和用户工具中选择解析器。 |
| 解析 | 执行选中的工具，并在输出目录写入 UTF-8 文本。 |
| 复查 | 判断抽取结果是否可用；必要时换路线重试。 |

## 安装与配置

从 PyPI 安装 OCRAgent，并带上常用文档后端：

```shell
python -m pip install "ocragent[full]"
ocragent --help
```

<details>
<summary>偏好 uv？</summary>

```shell
uv tool install "ocragent[full]"
ocragent --help
```

</details>

建议通过环境变量配置 chat-completions API：

```shell
export OCRAGENT_CHAT_BASE=http://localhost:8080/v1
export OCRAGENT_CHAT_MODEL=your-model
export OCRAGENT_CHAT_AUTHKEY=your-key
```

也可以使用 `OPENAI_API_KEY` 作为 auth key。强烈建议配置具备视觉模态的模型，因为 OCRAgent 会在分级和复查阶段使用模型判断。同样的配置可以写入 `~/.ocragent/ocragent.settings.toml`、`./ocragent.settings.toml` 或 `.env`。配置格式参考 [../src/ocragent/ocragent.settings.default.toml](../src/ocragent/ocragent.settings.default.toml)。

<details>
<summary>纯文字 LLM 与多模态 VLM 的区别</summary>

| 阶段 | 纯文字 LLM | 多模态 VLM |
| --- | --- | --- |
| 分级 | 依赖文件名、元数据、文字层探测和 OCR 抽样结果，不能直接查看页面图像。 | 可根据缩略图或页面渲染图判断扫描质量、手写、图表、表格、版面密度和 OCR 风险。 |
| 复查 | 检查文本连贯性、明显 OCR 噪声、重复内容和表格文本损坏。 | 有页面图像时，可对照视觉证据检查漏识别区域、版面丢失、手写、公式和图片密集页面。 |

</details>

`full` 会带上常用本地文档后端。若只想装最小依赖，也可以另行选择；多数用户从 `ocragent[full]` 开始最省心。

## 准备用户工具

把外部工具写在 `${HOME}/ocragent.toolbox_user.txt`，也可以用 `--from` 指定别的文件。写法可参考 [../src/ocragent/ocragent.toolbox_user.example.txt](../src/ocragent/ocragent.toolbox_user.example.txt)。

内容用平实的技术说明即可：工具名、用途范围、成本、参数、能力边界、调用方式和注意事项。工具说明可以从对应官方文档摘取，再删到 OCRAgent 需要的事实。API key 等机要内容放进环境变量，在工具箱说明中写环境变量名即可。

生成工具运行时：

```shell
ocragent init tools
ocragent init tools --from ./ocragent.toolbox_user.txt --force
```

生成结果位于 `${HOME}/.ocragent/user_toolbox.py`。它是可执行 Python 代码，带真实凭据使用前，须先看一遍。

## 初始化文档目录

`ocragent init docs` 需要 `${HOME}/.ocragent/user_toolbox.py` 已存在，所以先准备用户工具，再进入文档所在目录：

```shell
cd /path/to/documents
ocragent init docs
```

命令会写入 `./.ocragent_memory.txt`。这个文件是一份自然语言记忆，记下文件分组、解析难度和低成本预览结果。它只是给后续解析看的札记，不要求手工维护结构。

`ocragent.settings.toml` 中 `[init.ignore]` 列出的文件后缀和目录，会同时被 `init docs` 扫描和 `run` 目录遍历排除。

完整初始化会同时生成工具和目录记忆：

```shell
ocragent init --from /path/to/ocragent.toolbox_user.txt --force
```

JSON 输出中，生成文件路径使用 `result_file` 字段。`init docs` 的 `groups` 是分组记录列表，另有 `file_count` 和 `unmatched_count`。

## 解析文档

默认引导流程是在文档目录运行 `ocragent`：

```shell
ocragent
ocragent invoice.pdf scans/ --out-dir ocragent_results
ocragent --dry-run
```

Autonomous Mode 会复用已有生成文件，能安全补齐时自动补齐，然后进入解析。若 `${HOME}/.ocragent/user_toolbox.py` 缺失且 `${HOME}/ocragent.toolbox_user.txt` 存在，它会先运行 `init tools`。若 `.ocragent_memory.txt` 缺失，它会先运行 `init docs`。没有 toolbox TXT 时，它会创建仅含内建工具的运行时，并在其余状态足够时继续。`--yes` 用于接受非破坏性确认，`--force` 用于重新生成初始化文件。

解析当前目录：

```shell
ocragent run
```

解析指定文件或目录：

```shell
ocragent run invoice.pdf scans/ --out-dir ocragent_results
```

`ocragent run` 需要 `${HOME}/.ocragent/user_toolbox.py` 和 `./.ocragent_memory.txt` 都已存在。返回摘要使用 `parsed_count`、`failed_count`、`skipped_count`，并包含详细的 `results`、`failures`、`skipped` 和 `output_stats`。

每个成功解析的源文件会在输出目录下生成一个 UTF-8 文本文件，并保留相对路径：

```text
docs/report.pdf -> ocragent_results/docs/report.pdf.txt
```

运行过程中，OCRAgent 会向 `.ocragent_memory.txt` 追加批次摘要和最终输出摘要。以后再跑，它便能少走一点弯路。

## 查看与运行工具

```shell
ocragent tool --list
ocragent tool --list --scope=parser
ocragent tool pdf2txt --help
ocragent tool pdf2txt --path report.pdf
```

解析工具列表会显示每个可用工具及其参数；可选后端齐备时，常见项包括 `pdf2txt`、`pdf_pages_to_images` 和 `pandoc2txt`。

不可用工具不会出现在普通列表中，原因会写入日志。常见原因是缺少可选依赖，或少了工具声明的环境变量。

## 配置优先级

优先级从高到低：

1. 环境变量。
2. `./ocragent.settings.toml`。
3. `~/.ocragent/ocragent.settings.toml`。
4. 包内默认配置。

常用配置：

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

完整默认配置见 [../src/ocragent/ocragent.settings.default.toml](../src/ocragent/ocragent.settings.default.toml)。

## 常见问题

**每个命令都需要模型吗？**

不需要。查看工具和不少本地解析路径，都可以不用模型。`init tools` 和 `init docs` 需要模型，因为它们要让 Agent 生成工具代码，或判断目录里那些文件大概该怎样分组。具备视觉模态的模型能为扫描件、手写稿、公式和复杂版面提供更好的分级与复查信号。

**为什么 PDF 会被转成逐页图片？**

解析器会先试文本层提取。若评审认为结果不可用，而 PDF 图片后端也在，系统会把页面渲染成图片，再逐页解析并合并。

**为什么 `.ocragent_memory.txt` 不是 JSON？**

它只是给解析器的软提示。文件发现、工具校验和输出写入，仍由确定性代码完成。

**错误信息在哪里看？**

命令结果在 `stdout`，简短错误在 `stderr`，详细日志在当前目录的 `ocragent.log`。
