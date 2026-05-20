<img alt="OCRAgent logo rmbg640" style="float: right;right: 0px" src="docs/assets/readme-logo-rmbg-640.png" width="96" div align=right>

# OCRAgent

[English](README.md) | [简体中文](README_zh-Hans.md)

[![Publish to PyPI](https://github.com/cxumol/OCRAgent/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/cxumol/OCRAgent/actions/workflows/publish-pypi.yml)
[![PyPI version](https://badge.fury.io/py/ocragent.svg)](https://badge.fury.io/py/ocragent)
<!-- [![PyPI Downloads](https://img.shields.io/pepy/dt/ocragent)](https://pepy.tech/projects/ocragent) -->
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/ocragent)](https://pypi.org/project/ocragent/)

![品牌横幅](docs/assets/readme-brand-banner.jpg)

> 丝帛简牍数码书，千金半厘辨分殊。  
> 何须一模破万卷，自能调度在慧枢。

> OCR 优先，Agent 调度。

文档解析应该分级、调度、审阅。简单页面先用便宜的本地抽取；只有当 Agent 判断页面确实需要更多能力时，才升级到更贵的 OCR、VLM 或云端 API。

- Tesseract OCR 难以覆盖艺术字形和生僻字符，顶级多模态模型拿来解析普通印刷页又浪费算力。OCRAgent 让容易的页面先走低成本路线。
- 同样是多模态模型，有的擅长手写，有的擅长公式，有的更适合表格、扫描件和版面还原。OCRAgent 按页面特征分派工具。
- Agentic Loop 用于文档识别，优势在于有审阅。即使审阅模型不带视觉能力，也能从文字是否通顺、版面是否错位、表格是否漂移等方面发现粗糙失败。
- 如果你有多种 OCR 模型、文档 API 或命令行工具，又要处理一批混合档案，OCRAgent 给它们一个统一的命令行工作流。

## 为什么是 OCRAgent

![核心价值对比图](docs/assets/readme-core-value-comparison.jpg)

OCRAgent 不是另一个单体文档解析器，而是统筹多种解析工具的 Agentic Workflow。它把杂乱的文档目录整理成干净的纯文本，并让算力花在真正需要的页面上。

容易的页，先请便宜工具去读；读不动了，再升级到更强的 OCR、VLM 或云端 API。

Agent 会参考目录记忆、文件特征和上次失败原因来选工具，而不是把所有模型当成可以互换的黑箱。

## 快速开始

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

需要 LLM 支持的命令时，配置兼容 OpenAI chat-completions 的端点：

```shell
export OCRAGENT_CHAT_BASE=http://localhost:8080/v1
export OCRAGENT_CHAT_MODEL=your-model
export OCRAGENT_CHAT_AUTHKEY=your-key
```

也可以使用 `OPENAI_API_KEY`。同样的配置可以写入 `~/.ocragent/ocragent.settings.toml`、`./ocragent.settings.toml` 或 `.env`。配置格式可参考 [src/ocragent/ocragent.settings.default.toml](src/ocragent/ocragent.settings.default.toml)。

查看内建工具：

```shell
ocragent tool --list
```

如果要让 OCRAgent 调用你自己的 OCR、VLM、命令行工具或 API，先用普通文本描述它：

```text
$HOME/ocragent.toolbox_user.txt
```

用户工具箱的写法可参考 [src/ocragent/ocragent.toolbox_user.example.txt](src/ocragent/ocragent.toolbox_user.example.txt)。各工具说明可以从对应官方文档摘取，再保留工具名、用途范围、成本、参数、限制和调用方式。API key 等机要内容放进环境变量，在工具箱说明中写环境变量名即可。

然后生成工具运行时：

```shell
ocragent init tools
```

OCRAgent 会启用 AI Agent，把 `ocragent.toolbox_user.txt` 转换成可执行脚本，并写入 `$HOME/.ocragent/user_toolbox.py`。真实使用前，请先审阅这份文件。

然后解析一个目录：

```shell
cd /path/to/documents
ocragent init docs
ocragent run --out-dir ocragent_results
```

## CLI 运行示例

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
{
  "ok": true,
  "usertools_valid": [
    "siliconflow_deepseekocr"
  ],
  "usertools_failed": [],
  "agent_turns": 1,
  "result_file": "/home/me/.ocragent/user_toolbox.py"
}

$ ocragent init docs
{
  "ok": true,
  "result_file": "/home/me/cases/mixed_docs/.ocragent_memory.txt",
  "groups": [
    {
      "name": "pdf_text",
      "...": "..."
    }
  ],
  "file_count": 18,
  "unmatched_count": 0
}

$ ocragent run invoice.pdf scans/ --out-dir ocragent_results
{
  "ok": true,
  "out_dir": "/home/me/cases/mixed_docs/ocragent_results",
  "parsed_count": 18,
  "failed_count": 0,
  "skipped_count": 0,
  "results": [
    {
      "source": "invoice.pdf",
      "output_file": "/home/me/cases/mixed_docs/ocragent_results/invoice.pdf.txt",
      "...": "..."
    }
  ],
  "failures": [],
  "skipped": [],
  "output_stats": {
    "file_count": 18,
    "...": "..."
  }
}
```

上面的 JSON 保留真实字段名，较长的数组用 `"..."` 缩短展示。

## 产出结果

OCRAgent 会在输出目录中保留相对路径：

```text
docs/report.pdf -> ocragent_results/docs/report.pdf.txt
scans/page-01.jpg -> ocragent_results/scans/page-01.jpg.md
```

它还会维护一份目录记忆：

```text
.ocragent_memory.txt
```

这份记忆是普通自然语言文本。后续解析会参考它选择合适的起始成本，但项目不会因此被锁进僵硬的数据表结构。

## 三层架构概览

```text
命令行  (ocragent init / run / tool)
 |
AI Agents  (init_tools / parser / reviewer)
 |
工具链  (builtin tools + user_toolbox.py)
```

![架构图](docs/assets/readme-architecture.jpg)

| 层次 | 负责 | 例子 |
| --- | --- | --- |
| CLI 与命令 | 稳定行为 | 配置、路径、日志、stdout 和 stderr 边界 |
| 工具层 | 解析能力 | PDF 文本、图像缩略图、Pandoc、用户 OCR、VLM API |
| Agent 层 | 不确定场景下的判断 | 文件分组、工具选择、抽取结果审阅 |

解析 Agent 不直接调用厂商接口。它先询问工具注册表有哪些可用能力，再通过和 CLI 相同的边界执行工具。候选文本经审阅后才写入输出目录；审阅不通过时，Agent 会参考目录记忆和失败原因，换用其他工具或更高成本路线。

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

## 参与贡献

OCRAgent 处于 beta 阶段，现在很适合参与塑造。适合下手的贡献包括：

- 增加或改进内建解析工具。
- 增加能代表真实文档难题的 demo assets。
- 改进 reviewer prompt 和失败案例。
- 加强 CLI 行为、工具发现、用户工具生成相关测试。
- 为常见 OCR、VLM、文档转换后端编写适配器。
- 把你实际跑通过的流程写进文档。

开始前可先运行：

```shell
uv run python -m unittest discover -s tests
uv run --extra pdf python -m unittest discover -s tests
```

常用代码入口：

- `src/ocragent/cli.py`：命令行入口。
- `src/ocragent/cmd/`：命令实现。
- `src/ocragent/cmd/tool.py`：内建和用户工具接口约定。
- `src/ocragent/agent/`：面向模型的循环。
- `src/ocragent/config.py`：分层配置。
- `tests/`：当前测试套件和 CLI 流程检查。

## 文档

- [用户指南](docs/user-guide.zh-hans.md)
- [架构说明](docs/architecture.md)
- [Agent 循环](docs/agent-loop.md)
- [工具机制](docs/tool-mechanism.md)
- [开发者指南](docs/developer-guide.md)

## 项目状态

OCRAgent 处于 beta 阶段。命令形态已经可用，后续仍可能有破坏性变更。项目欢迎关心文档解析、本地优先工具、边界清楚的 Agentic 工作流的贡献者。
