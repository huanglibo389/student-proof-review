# 学生证明审查流水线

这是一个本地优先的数学竞赛学生作业审查项目。它把一次审查拆为四个互相独立的证据层：

1. **图像转写**：仅转写题干和学生有效作答，无法辨认的符号保留为 `[不清]`；不把识别结果当作数学结论。
2. **数学审查**：由审查者逐步判断结论、主线和原稿完整性，定位第一处不成立的推理，并给出最小修补。
3. **报告交付**：将已经完成的审查稿编译为黑白 XeLaTeX PDF；公开报告不会包含内部工具或识别过程。
4. **渲染核验**：检查 PDF 是否可渲染、页面是否非空；可额外进行页面版式复核。

项目的目标不是让程序替代数学审查者。尤其是，视觉转写、文件复制、PDF 编译成功，都不能证明一个数学证明正确。

## 当前规则

- 所有本地视觉转写和可选的页面版式复核，**只允许**使用本地 `Qwen3.8 27B`：`/Users/huanglibo/.omlx/models/Qwen3.8-27B-MLX-Mixed-4.95bpw`。
- 默认服务地址为 `http://127.0.0.1:8085/v1`。每次视觉调用前都会读取 `/v1/models` 并核对模型。
- 审查结论由数学审查者填写。报告必须明确区分：`答案正确`、`主线正确`、`原稿完整正确`。
- 对学生稿的批评应指出**第一处**无效推理，并提供不推翻原思路的最小修补。

## 安装

项目只需 Python 3、`requests`、`Pillow`、Pandoc、XeLaTeX 和 Poppler。macOS 上可在项目目录执行：

```bash
python3 -m pip install -e .
```

如本地视觉服务尚未运行，可从原工作目录启动：

```bash
/Users/huanglibo/Documents/New\ project/tools/start_qwen38_27b_4_95bpw_server.sh
```

## 一次完整审查

假设题目图片和学生作答图片已经准备好：

```bash
student-proof-review create \
  --case-name 20260825_good_squares \
  --title "第3题学生解答审查" \
  --image /absolute/path/problem.jpg \
  --image /absolute/path/student-work.jpg

student-proof-review transcribe outputs/20260825_good_squares
```

第二步会生成：

```text
outputs/20260825_good_squares/
├── case.json                 # 输入文件哈希和任务元数据
├── input/                    # 原始输入副本
├── transcription.md          # 内部转写稿，保留待核对处
├── audit.md                  # 等待数学审查者填写的公开报告草稿
└── internal/                 # 内部识别和版式核验记录
```

审查者完成 `audit.md` 后，生成并核验 PDF：

```bash
student-proof-review report outputs/20260825_good_squares
student-proof-review verify outputs/20260825_good_squares
```

若需要使用本地视觉模型复核最终 PDF 的版式：

```bash
student-proof-review verify outputs/20260825_good_squares --vision
```

最终文件位于 `outputs/<case>/report/学生解答审查.pdf`。需要放到桌面时使用：

```bash
student-proof-review deliver outputs/20260825_good_squares \
  --destination /Users/huanglibo/Desktop/macbook
```

## `audit.md` 写作标准

`audit.md` 是最终 PDF 的唯一公开内容来源。建议按以下顺序填写：

```markdown
# 第3题学生解答审查

## 题目

题干正文与公式。

## 评审结论

- 答案正确：是 / 否 / 未完成。
- 主线正确：是 / 否 / 部分正确。
- 原稿完整正确：是 / 否。
- 总评：一句明确判断。

## 学生方法整理

按原稿逻辑重写有效步骤，不把被划掉的草稿混入。

## 第一处需要修补的地方

明确说明哪一步不能由前文推出，并给出最小补法。

## 可采用的修补证明

给出完整、可检查的修补；所有除法、非零条件、边界情形和等号条件都要写出。

## 给学生的建议

简短、具体、可执行。
```

`internal/` 中的转写和版式记录不参与 PDF 编译；报告中也不会出现内部模型或识别过程。

## 常用命令

```bash
# 检查本地服务和当前模型
student-proof-review preflight

# 创建任务，不调用视觉模型
student-proof-review create --case-name demo --title "演示" --image proof.jpg

# 完成视觉转写，并生成审查模板
student-proof-review transcribe outputs/demo

# 从 audit.md 生成 PDF
student-proof-review report outputs/demo

# 渲染并检查 PDF
student-proof-review verify outputs/demo

# 查看所有生成文件
student-proof-review status outputs/demo
```

## 质量边界

- 图像不清楚时，宁可写 `[不清]`，不能猜测公式或符号。
- 在数学审查前，应对转写中的关键符号与原图逐项比对。
- 对“答案正确”“主线正确”“原稿完整正确”必须分别判定，不能用一句“基本正确”替代。
- 编译成功只证明版式流程基本可用；数学正确性仍需逐行审查。
- `verify --vision` 只检查页面排版，不审查数学内容。

## 测试

```bash
python3 -m unittest discover -s tests -v
```
