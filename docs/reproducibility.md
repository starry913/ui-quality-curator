# 运行与复现说明

## 两种运行方式

| 方式 | 输入 | 是否需要密钥 | 是否调用模型 |
|---|---|---|---|
| 离线重放 | 仓库中的描述与已保存响应 | 否 | 否 |
| 新数据推理 | 自行准备的 50 条视觉描述与样本清单 | Jev 密钥 | 是 |

## 离线重放

在仓库根目录运行：

```bash
python tools/replay.py
python -m unittest discover -s tests -v
```

`replay.py` 分别运行两个实验的报告生成器，使用保存的分项响应重算最终结果，并生成 `index.html` 导航。需要 Python 3.10+，无需安装第三方 Python 包。

报告支持三档质量、页面功能、业务领域筛选，按总分或分项排序，并导出当前 CSV。报告呈现一个质量总分，同时保留六个维度的分项分数及判断依据。

没有原图预览时，报告会显示 `samples.csv` 中的公开作品来源链接。若有相应图片，可保存为实验目录下的 `previews/<sample_id>.jpg` 后重新生成报告。`images/` 和 `previews/` 均已加入忽略规则。

## 为新实验准备输入

当前保留的是固定批量研究原型，运行器严格要求 **50 个样本编号**，并非任意规模的数据服务。

1. 在 `experiments/` 下复制一个实验目录，使用新的目录名与样本编号，保留原基准记录。
2. 准备 `samples.csv`、`experiment.json` 及 `captions_structured_v4.json`。CSV 与 Caption 的 50 个 `sample_id` 应一一对应。
3. 字段格式可参考已保存的 `captions_structured_v5.json`。至少包括 `sample_id`、`content_and_purpose`、`layout_components`、`hierarchy`、`typography_color_components`、`presentation_limits`、`uncertainties`、`function_evidence` 和 `domain_evidence`。
4. 新实验初始化时，移除复制来的 `jev_results_v4.json`、`jev_results_v5.json` 及旧导出与报告，避免续跑逻辑跳过已有编号。

视觉描述应基于实际查看的图片，记录不确定性，避免根据来源标题或搜索类别推断功能。已有 Luna 描述在交互式 Codex 会话中生成；本仓库没有封装一个可独立调用的 Luna API 服务。

结构阶段保留了 LP006、LP030 的历史人工观察补充。新实验请采用不同编号，或在 `run_structure_v5.py` 中移除这两条基准专用补充。

## 配置并调用 Jev

可以设置环境变量 `TYPESAFE_API_KEY`，或将根目录 `.env.example` 复制为本地 `.env` 并填写自己的密钥。运行器优先读取环境变量，随后读取本地配置；`.env` 不参与提交。

在新实验目录中依次运行：

```bash
python run_classification_v4.py
python run_structure_v5.py
python build_report_v5.py
```

- 第一阶段调用 `https://api.typesafe.ai/v1/systemone`，提交视觉描述、页面功能/业务领域分类问题与五项评分问题。
- 第二阶段评估页面结构类别与完整度，随后根据保存的分项结果计算质量总分。
- 报告生成步骤只重放保存结果，不调用 API。

前两个步骤可能产生 API 费用。请求模型参数为 `jev-latest`，实际响应模型名称保存在结果中；历史响应为 `jev-1.13.0`。重新调用服务不能保证与已保存响应逐字一致。

运行器逐条保存检查点，完成的编号会在续跑时跳过。Caption 文件摘要变化时会拒绝混用旧检查点；更换输入应建立新实验或明确管理对应结果文件。

## 记录对应关系

| 文件 | 含义 |
|---|---|
| `samples.csv` | 样本编号、公开作品链接、原始图片哈希与相对路径 |
| `experiment.json` | 来源类别、抽样单位、随机种子与抽样方法 |
| `captions_structured_v4.json` | 第一阶段输入描述 |
| `captions_structured_v5.json` | 结构阶段使用的描述，含必要的数组规范化或基准观察补充 |
| `caption_provenance_v4.json` | 图像查看与原图复核记录 |
| `questions_v4.json` / `questions_v5.json` | 两阶段的实际问题配置 |
| `jev_results_v4.json` | 第一阶段的解析后 API 响应及中间结果 |
| `jev_results_v5.json` | 保留两阶段响应的最终评分与决策记录 |
| `rule_v5.json` | 当前总分与质量分档规则 |
| `review_policy_v5.json` | 人工复核提示策略 |
| `classification_scores_v5.csv` | 方便浏览和分析的最终导出 |

`docs/db045/` 的五个 JSON 是从实际记录中提取的对应字段，并非五次单独的 API 调用。页面功能和可读性问题与其他问题共享一次请求；结构完整度来自第二阶段请求。仓库保存的是解析后的响应对象，没有声称保存了原始 HTTP 抓包。

## 脚本版本与目录

```text
experiments/
  landing-page-random-50/
  dashboard-random-50/
docs/
  project-overview.png     # 方法示意图
  results-preview.png      # 本地检查界面截图
  db045/                   # 真实输入问题与原始输出字段
tools/replay.py             # 两组实验的离线复现与报告导航
tests/test_replay.py        # 分数、分档边界、缺陷上限与报告完整性检查
```

保留 `v3`、`v4`、`v5` 名称用于对应原实验迭代：`run_scores_v3.py` 定义五项评分标准；`run_classification_v4.py` 执行第一阶段分类与评分；`run_structure_v5.py` 与 `build_report_v5.py` 实现当前总分规则和报告。

当前报告生成器只读取 `build_scores_report_v3.py` 内的静态样式模板，不执行该旧报告流程。
