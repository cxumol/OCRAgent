<img alt="OCRAgent logo" style="float: right;right: 0px" src="docs/assets/readme-logo-rmbg-640.png" width="96" div align=right>

# OCRAgent

[English](README.md) | [简体中文](README_zh-Hans.md)

[![Publish to PyPI](https://github.com/cxumol/OCRAgent/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/cxumol/OCRAgent/actions/workflows/publish-pypi.yml)
[![PyPI version](https://badge.fury.io/py/ocragent.svg)](https://badge.fury.io/py/ocragent)
<!-- [![PyPI Downloads](https://img.shields.io/pepy/dt/ocragent)](https://pepy.tech/projects/ocragent) -->
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/ocragent)](https://pypi.org/project/ocragent/)

![品牌横幅](docs/assets/readme-brand-banner.jpg)

> 何须一模破万卷，自能调度在慧枢。

OCRAgent 是一个命令行文档解析工作流。它使用 Agent 选择 OCR、VLM、PDF、Office 文档或用户自定义工具，并在写入结果前审阅解析文本。

它解决的是工具调度问题：简单文件使用便宜抽取，复杂文件再投入模型或 API 成本。

![核心价值对比图](docs/assets/readme-core-value-comparison.jpg)

## 分级、分配、解析、复查

OCRAgent 适合处理混合文档目录，例如带文字层的 PDF、扫描 PDF、图片、Office 文件、手写页、表格和表单。这些文件通常不适合全部交给同一个解析器。

| 步骤 | OCRAgent 做什么 | 主要产物 |
| --- | --- | --- |
| 分级 | 根据文件名、元数据、预览信号和抽样页估计解析难度。 | `.ocragent_memory.txt` |
| 分配 | 根据成本、scope 和目录记忆，从内建工具和用户工具中选择解析器。 | tool call |
| 解析 | 执行选中的工具，输出 UTF-8 文本，并保留源文件相对路径。 | `ocragent_results/` |
| 复查 | 判断解析文本是否可用；不通过时换工具或路线重试。 | 通过的输出或重试 |

四个步骤对应四个关注点：

- 分级：先判断难度，再决定是否投入模型或 API 成本。
- 分配：所有工具通过同一个工具注册表选择。
- 解析：通过明确的命令边界执行工具。
- 复查：结果可用后再写入最终输出。

## 运行流程

```text
documents
  -> init docs
  -> folder memory
  -> parser agent
  -> parser tool
  -> reviewer agent
  -> output text
```

## 安装

安装 OCRAgent，并带上常用文档后端：

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

建议通过环境变量配置 chat-completions API：

```shell
export OCRAGENT_CHAT_BASE=http://localhost:8080/v1
export OCRAGENT_CHAT_MODEL=your-model
export OCRAGENT_CHAT_AUTHKEY=your-key
```

也可以使用 `OPENAI_API_KEY` 作为 auth key。强烈建议配置具备视觉模态的模型，因为 OCRAgent 会在分级和复查阶段使用模型判断。同样的配置可以写入 `~/.ocragent/ocragent.settings.toml`、`./ocragent.settings.toml` 或 `.env`。配置格式参考 [src/ocragent/ocragent.settings.default.toml](src/ocragent/ocragent.settings.default.toml)。

<details>
<summary>纯文字 LLM 与多模态 VLM 的区别</summary>

| 阶段 | 纯文字 LLM | 多模态 VLM |
| --- | --- | --- |
| 分级 | 依赖文件名、元数据、文字层探测和 OCR 抽样结果。可以从已抽取文本估计可读性，但不能直接查看页面图像。 | 可根据缩略图或页面渲染图判断扫描质量、手写、图表、表格、版面密度，以及普通 OCR 是否容易失败。 |
| 复查 | 检查文本是否通顺、表格转文本后是否损坏、是否出现明显 OCR 噪声。 | 在有页面图像时，可对照视觉证据检查漏识别区域、版面丢失、手写、公式和图片密集页面。 |

</details>

## 快速开始

查看可用工具：

```shell
ocragent tool --list
ocragent tool --list --scope=parser
```

如果要让 OCRAgent 调用自己的 OCR、VLM、命令行工具或 API，先用普通文本描述工具：

```text
$HOME/ocragent.toolbox_user.txt
```

格式可参考 [src/ocragent/ocragent.toolbox_user.example.txt](src/ocragent/ocragent.toolbox_user.example.txt)。说明中写清工具名、scope、成本、参数、限制、调用方式和所需环境变量。

生成工具运行时：

```shell
ocragent init tools
```

OCRAgent 会把可执行 Python 写入 `$HOME/.ocragent/user_toolbox.py`。使用真实凭据前，应先审阅该文件。

初始化并解析文档目录：

```shell
cd /path/to/documents
ocragent init docs
ocragent run --out-dir ocragent_results
```

## CLI 示例

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
# 写入 /home/me/.ocragent/user_toolbox.py
# 返回可用和失败的用户工具

$ ocragent init docs
# 写入 .ocragent_memory.txt
# 返回识别出的分组、file_count 和 unmatched_count

$ ocragent run invoice.pdf scans/ --out-dir ocragent_results
# 将解析结果写入 ocragent_results/
# 返回 parsed_count、failed_count、skipped_count 和 output_stats
```

实际运行时命令会返回 JSON。上面的示例保留流程和关键字段，避免展开过长结果。

## 输出

OCRAgent 保留源文件相对路径：

```text
docs/report.pdf -> ocragent_results/docs/report.pdf.txt
scans/page-01.jpg -> ocragent_results/scans/page-01.jpg.md
```

它还会写入目录记忆文件：

```text
.ocragent_memory.txt
```

记忆文件是自然语言文本，记录文件分组、难度估计、工具选择和运行摘要。后续解析会把它作为上下文。

## 架构

```text
CLI  (ocragent init / run / tool)
 |
AI Agents  (init_tools / parser / reviewer)
 |
Tool chain  (builtin tools + user_toolbox.py)
```

![架构图](docs/assets/readme-architecture.jpg)

| 层次 | 职责 | 例子 |
| --- | --- | --- |
| CLI 与命令 | 稳定的命令行为 | 配置、路径、日志、stdout、stderr |
| 工具注册表 | 解析能力边界 | PDF 文本、图像缩略图、Pandoc、用户 OCR、VLM API |
| Agent 循环 | 运行期决策 | 文件分组、工具选择、审阅、重试 |

parser agent 不直接调用厂商 API。它读取可用解析工具，选择工具，通过工具边界执行，并把抽取文本交给 reviewer。审阅失败时，parser 可以换用其他工具或更高成本路线重试。

## 配置

配置优先级从高到低：

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
model_hasVision = true

[output]
dir = "ocragent_results"
ext = "auto"
parser_summary_batch = 5

[reviewer]
max_length = 1000
```

完整默认配置见 [src/ocragent/ocragent.settings.default.toml](src/ocragent/ocragent.settings.default.toml)。

## 文档

- [用户指南](docs/user-guide.zh-hans.md)
- [架构说明](docs/architecture.md)
- [Agent 循环](docs/agent-loop.md)
- [工具机制](docs/tool-mechanism.md)
- [开发者指南](docs/developer-guide.md)

## 参与贡献

OCRAgent 处于 beta 阶段，后续仍可能有破坏性变更。

适合贡献的方向：

- 增加或改进内建解析工具。
- 增加覆盖真实文档场景的 demo assets。
- 改进 reviewer prompt 和失败案例。
- 加强 CLI 行为、工具发现、用户工具生成相关测试。
- 为常见 OCR、VLM、文档转换后端编写适配器。
- 补充已经实际验证过的流程文档。

运行测试：

```shell
uv run python -m unittest discover -s tests
uv run --extra pdf python -m unittest discover -s tests
```

重要路径：

- `src/ocragent/cli.py`：命令行边界。
- `src/ocragent/cmd/`：命令实现。
- `src/ocragent/cmd/tool.py`：内建和用户工具接口约定。
- `src/ocragent/agent/`：面向模型的循环。
- `src/ocragent/config.py`：分层配置。
- `tests/`：测试套件和 CLI 流程检查。
