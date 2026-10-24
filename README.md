# UI Quality Curator

**面向前端生成的界面数据筛选与分类原型。** 使用 Luna 提取结构化视觉描述，使用 Jev 完成页面功能、业务领域分类和分项评分，再通过透明规则生成唯一的质量总分。

A research prototype for frontend screenshot curation: structured visual captions, page-function/domain classification, and rule-based quality screening with saved evidence.

![项目方法与真实 JSON 字段示例](docs/project-overview.png)

## 解决的问题

网页素材中混有完整界面、孤立组件、作者宣传图和文字难以辨认的页面。搜索来源为 `dashboard` 不代表图片实际就是仪表盘；页面结构完整也不能抵消严重的可读性缺陷。

本项目保留每张图片的描述、问题配置、模型响应、分项分数与决策原因，方便追溯和人工检查。目前是 **100 张样本的原型实验**，没有训练新模型，也没有建立人工金标准或验证下游生成效果。

## 方法

1. **Luna 视觉描述**：逐图查看，按内容、布局、层级、字体配色、展示限制、不确定项及分类证据等字段输出 JSON。本实验在交互式 Codex 会话中完成；仓库保存实际描述和复核记录，不提供独立可调用的 Luna API 服务。
2. **Jev 分类与评分**：`choice` 选择页面功能和业务领域；`score` 按预设的 0–4 级标准输出五项设计评分。第二次请求评估页面结构类别与完整度。真实响应包含模型名、置信度及概率分布。
3. **程序计算质量总分**：分项乘以 25 转成百分制，应用以下规则，输出三档标签并保留待复核原因。小数位与置信度都不等于经过校准的正确率。

### 质量规则

五项加权分：布局与间距 25%、信息层级 20%、可读性 15%、视觉一致性 20%、数据可学习性 20%。页面结构完整度另外限制总分。

```text
质量总分 = min(五项加权分, 页面结构完整度, 结构上限, 严重设计缺陷上限)

结构上限：孤立组件 25；作者宣传或非界面 0；其他 100
严重设计缺陷：布局、层级、可读性、一致性任一 <50 时，总分不能高于该项分数

高质量：总分 >=65
中质量：50 <= 总分 <65
低质量：总分 <50
```

按未舍入分数分档，页面显示一位小数。完整规则见每个实验的 `rule_v5.json`。规则属于本次研究的启发式定义，尚未经人工校准。

## 已完成的实验

从两类各 10,000 张候选素材中分别固定随机抽取 50 张，两个样本集均包含 50 个不同作品。随机种子、抽样方法与原始图片哈希见各自的 `experiment.json` 和 `samples.csv`。

| 来源样本集 | 高质量 | 中质量 | 低质量 | 平均总分 |
|---|---:|---:|---:|---:|
| Landing-page，50 张 | 20 | 13 | 17 | 54.4 |
| Dashboard，50 张 | 27 | 10 | 13 | 56.0 |

这些数字是当前规则下的筛选分布，**不是准确率**。Dashboard 来源中实际分类为仪表盘的有 29 张、业务管理页 11 张、非界面 5 张，其他功能 5 张。

### 真实案例 DB045

Luna 描述指出深绿背景上的暗色文字对比不足。Jev 返回可读性 `1.46/4`，换算为 `36.5/100`；视觉一致性为 `44.5`。原五项加权分为 `55.6375`，加入严重缺陷限制后，质量总分为 **36.5，低质量**。

分类结果为 `detail`（详情页）和 `other`（其他领域）。没有将“畜牧交易”的描述线索冒充成模型已输出的专门行业类别。

[五个实际 JSON 字段记录](docs/db045/) 包括 Luna 输出、Jev 分类输入/输出和可读性评分输入/输出。它们是原记录的字段提取；同一次实际请求还包含其他问题。页面结构完整度来自另一次请求。保存的 `response` 是解析后的 API 响应，不是 HTTP 抓包。

## 快速开始：离线复现，无需 API 密钥

需要 Python 3.10+。核心脚本仅使用标准库。

```bash
git clone https://github.com/starry913/ui-quality-curator.git
cd ui-quality-curator
python tools/replay.py
python -m unittest discover -s tests -v
```

`replay.py` 读取已保存的真实模型响应，重算 100 张样本的分数和标签，并生成两份静态报告。**不会调用模型或读取 API 密钥。**

- 打开根目录生成的 `index.html` 进入实验导航。
- 也可直接打开 `experiments/landing-page-random-50/review.html` 或 `experiments/dashboard-random-50/review.html`。
- 报告支持按三档质量、页面功能、业务领域筛选、按分数排序和下载当前 CSV。
- 原图未随代码发布；缺少预览时显示公开来源作品链接。将自己的预览保存为 `previews/<sample_id>.jpg` 后重新生成报告即可显示。

## 使用自己的描述进行新推理

这是保留原始实验脚本的研究原型，两个实验目录目前都严格校验 **50 个样本编号**。请先复制一个实验目录作为新实验，准备对应的 `samples.csv`、`experiment.json` 和 `captions_structured_v4.json`；确保编号匹配，并移除复制来的旧响应文件，以免断点跳过旧记录。请勿覆盖已提交的基准记录。

1. 按 `captions_structured_v5.json` 的字段组织自己的视觉描述。描述只能记录可见证据，不能从来源类别猜测页面类型。
2. 在终端设置 `TYPESAFE_API_KEY`，或将 `.env.example` 复制为本地 `.env` 并填写自己的密钥。`.env` 已忽略。
3. 在新实验目录运行：

```bash
python run_classification_v4.py
python run_structure_v5.py
python build_report_v5.py
```

前两个步骤会调用 `https://api.typesafe.ai/v1/systemone`，可能产生 API 费用；报告生成步骤不调用 API。请求使用 `jev-latest`，实际响应模型记录在结果中，历史样本为 `jev-1.13.0`。模型版本变化可能影响复现。运行器保存检查点，并在输入变化时拒绝混用旧结果。

新实验初始化时，至少清除 `jev_results_v4.json`、`jev_results_v5.json` 及由旧记录生成的导出和报告；保留或重新生成问题配置。结构阶段还保留了 LP006、LP030 的历史人工观察补充，新实验请使用不同编号，或移除这两条基准专用补充。

## 目录

```text
experiments/
  landing-page-random-50/   # 50 张描述、响应、评分规则和报告脚本
  dashboard-random-50/      # 另一组 50 张，使用相同最终评分规则
docs/
  project-overview.png      # 5 个 JSON 字段节选的方法图，预留插图位置
  db045/                    # 一个真实样本的输入问题与原始输出字段
tools/replay.py              # 离线重算并生成报告导航
tests/test_replay.py         # 分数、分档、缺陷上限、HTML 和来源追溯检查
```

`v3`、`v4`、`v5` 文件名保留了迭代来源：`run_scores_v3.py` 提供五项评分标准；`run_classification_v4.py` 负责分类与第一阶段评分；`run_structure_v5.py` 和 `build_report_v5.py` 提供当前总分规则与报告。`build_scores_report_v3.py` 在当前流程中仅作为静态样式模板读取。

## 数据与局限

仓库发布代码、描述与评分证据，不发布原始采集图库、API 密钥、运行数据库、用户目录路径或无关海报项目。`samples.csv` 保留公开作品链接及哈希用于追溯；原作品权利属于其作者，本仓库不授予第三方图片的使用许可。

评分依赖描述的准确性，可能丢失图像细节；分类候选集合也存在覆盖不足，例如当前没有单独的畜牧业类别。待复核标记只用于优先检查分界样本或可能影响保留决定的结构歧义，不保证捕获全部错误。

下一步是建立人工标注集、评估评分一致性，再比较筛选数据对下游前端生成质量的影响。
