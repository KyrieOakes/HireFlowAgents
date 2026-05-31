# 测试数据目录

## 数据说明

当前所有测试数据均为 **LLM 生成的 synthetic 数据**，不包含真实个人信息。

## 目录结构

```
data/
├── jobs/           # 岗位描述 (JD) 文件
│   └── *.txt       # 纯文本格式的 JD
├── resumes/        # 简历文件
│   └── *.txt       # 纯文本格式的简历
└── synthetic/      # LLM 生成的合成数据 (备用)
```

## 使用方式

### 1. 用 CLI 运行自定义数据

```bash
# 将 JD 文件保存到 data/jobs/ai-engineer.txt
# 将简历文件保存到 data/resumes/
python -m app.cli run data/jobs/ai-engineer.txt data/resumes/
```

### 2. 通过 API 上传

```bash
# 启动 API 后
curl -X POST http://localhost:8000/jobs/upload \
  -H "Content-Type: application/json" \
  -d '{"jd_text": "岗位描述全文..."}'

curl -X POST http://localhost:8000/resumes/upload \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "简历全文...", "filename": "resume_001.txt"}'
```

### 3. 内置 Demo 数据

```bash
python -m app.cli demo
# 使用 app/cli.py 中硬编码的 1个JD + 3份简历
```

## 测试数据规模建议

| 阶段 | JD 数 | 简历数 | 用途 |
|---|---|---|---|
| MVP 开发测试 | 1-2 | 3-5 | 快速验证 Pipeline |
| 功能测试 | 3-5 | 10-20 | 验证排序质量 |
| 评估 | 5 | 30 | 运行评估指标 |
| 正式演示 | 5 | 50-100 | 展示系统能力 |

## 数据格式要求

### JD 文件格式

纯文本或 Markdown 格式，应包含:
- 岗位名称
- 岗位职责
- 必备技能
- 加分技能
- 学历要求
- 经验要求

### 简历文件格式

纯文本或 Markdown 格式 (PDF/DOCX 暂未支持)，应包含:
- 姓名 / 联系方式
- 教育背景
- 技能列表
- 项目经历
- 工作/实习经历

## 隐私声明

❗ **不要使用未经许可的真实私人简历。**
当前所有数据均为 LLM 生成的 synthetic 数据。
如需使用真实简历进行测试，必须先进行匿名化处理 (去除姓名、联系方式等 PII)。
