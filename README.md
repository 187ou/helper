# 桌面智能助手 (Desktop Assistant)

私有化本地运行的 AI 个人工作台，集成任务编排、自适应演化、混合检索、办公自动化、生活健康管理。

![Python](https://img.shields.io/badge/Python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange)
![React](https://img.shields.io/badge/React-19-61DAFB)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ 核心能力

### 🧠 DAG 任务编排
- 自然语言指令自动拆解为 DAG 任务链路（LangGraph）
- 支持串行/并行节点、断点续跑、失败重试（指数退避）
- SSE 流式输出，实时查看执行进度
- ReactFlow 可视化 DAG 画布，节点状态实时同步

### 🔄 自适应演化引擎
- **多维度打分**：工作/生活双维度 6 指标 LLM 评估（完整性/效率/质量/一致性/满意度/新颖性）
- **权重迭代**：高频习惯自动提权，过期行为指数衰减，跨类型关联传导
- **模板固化**：高频任务（频次≥5 且均分≥70）自动沉淀为可复用模板
- **遗忘机制**：指数衰减曲线防止过期数据污染，滑动窗口统计替代全量
- **记忆巩固**：碎片记忆→结构化知识的自动提炼（模式提取/偏好强化/洞察生成）

### 🔍 混合检索 (RAG)
- **双路召回**：Chroma 向量库 + BM25 全文索引
- **RRF 融合**：Reciprocal Rank Fusion (k=60) 融合排序，较纯向量召回率提升 32%
- **6 类文档**：PDF / Word / TXT / Markdown / Excel / 图片 OCR
- **文本降噪**：控制字符清除、页码过滤、断行连句、噪声行去除
- **ONNX 嵌入**：本地嵌入模型，无需下载（自动降级 sentence-transformers）
- **同义词扩展**：场景化查询扩展（20+ 办公/生活同义词）
- **引用溯源**：检索结果自动标注来源文档与片段位置

### 🛠️ 沙箱安全
- LLM 自动生成轻量化 Python 工具
- AST 静态检查（黑名单拦截危险函数/模块）
- 子进程隔离执行（超时自动终止、全局状态分离）
- 运行日志完整记录

### 💼 全场景覆盖
- **职场办公**：文书撰写、Excel 处理、报销整理、文件归档、会议纪要
- **生活健康**：记账复盘、健康提醒（久坐/喝水）、习惯打卡、日程管理
- **私有知识库**：向量检索、笔记管理、文档摘要、智能解析

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (React + Vite)                      │
│  Ant Design · ReactFlow · XYFlow · TailwindCSS · Zustand        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / SSE
┌───────────────────────────▼─────────────────────────────────────┐
│                 Backend (FastAPI + Uvicorn)                       │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────────┐  │
│  │  Agent Core  │  │ Evolution Core │  │   Memory Store     │  │
│  │  LangGraph   │  │ Judge/Weight   │  │ SQLite (WAL)       │  │
│  │  LLM Client  │  │ Template/Forget│  │ Chroma (向量)      │  │
│  │  Task Parser │  │ Consolidation  │  │ BM25 (全文)        │  │
│  └──────────────┘  └────────────────┘  └────────────────────┘  │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────────┐  │
│  │  Service     │  │     API        │  │   Tools            │  │
│  │  Business    │  │  FastAPI Router│  │ PDF/Excel/Word/OCR │  │
│  │  Logic       │  │  SSE Streaming │  │ Sandbox Runner     │  │
│  └──────────────┘  └────────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.13, FastAPI, LangGraph, LangChain |
| 存储 | SQLite (WAL), Chroma (向量), BM25 (全文), pickle (索引) |
| 前端 | React 19, Vite, Ant Design 6, ReactFlow, TailwindCSS, Zustand |
| AI | OpenAI 兼容 API / Ollama 本地双模式 |
| 沙箱 | AST 静态检查 + 子进程隔离 + 超时控制 |
| 文档解析 | pypdf, openpyxl, python-docx, PaddleOCR/easyocr/tesseract |

## 🚀 快速开始

### 环境要求
- Python >= 3.13, < 3.14
- Node.js >= 18
- uv（Python 包管理器）

### 1. 后端启动

```bash
# 安装依赖
uv sync

# 启动服务
python main.py
# 服务运行在 http://127.0.0.1:8000
```

### 2. 前端启动

```bash
cd frontend
npm install
npm run dev
# 前端运行在 http://127.0.0.1:5173
```

### 3. 配置 AI 能力

在浏览器打开 `http://127.0.0.1:5173`，进入「设置」页面：
- **联网模式**：填入 OpenAI 兼容 API 的 Base URL、API Key、模型名
- **离线模式**：安装 Ollama 后切换到本地模式

## 📁 项目结构

```
self-add/
├── agent_core/              # AI Agent 核心
│   ├── graph_builder.py         # LangGraph DAG 构建（并行/串行节点）
│   ├── node_executor.py         # 节点执行器（流式 + 校验重试 + 指数退避）
│   ├── task_parser.py           # 自然语言任务拆解（模板→LLM→规则）
│   ├── task_scheduler.py        # 任务调度（含演化闭环）
│   ├── llm_client.py            # LLM 客户端（双模式 + 降级）
│   ├── result_validator.py      # 结果校验与纠错
│   ├── context_window.py        # 上下文窗口管理
│   ├── memory_consolidation.py  # 记忆巩固（碎片→结构化知识）
│   ├── memory_context.py        # 记忆上下文注入
│   ├── memory_graph.py          # 记忆图谱
│   ├── metamemory.py            # 元记忆（记忆的记忆）
│   ├── user_model.py            # 用户画像模型
│   ├── emotional_memory.py      # 情感记忆
│   ├── life_narrative.py        # 生活叙事生成
│   ├── deep_reflection.py       # 深度反思
│   ├── reflection.py            # 反思引擎
│   ├── proactive_reasoning.py   # 主动推理
│   ├── prospective_memory.py    # 前瞻记忆
│   └── working_memory.py        # 工作记忆
├── evolution_core/          # 自适应演化引擎
│   ├── judge_score.py           # 多维度打分（6 维度，LLM+规则降级）
│   ├── weight_evolve.py         # 权重迭代（提权/衰减/关联传导）
│   ├── flow_optimize.py         # 流程优化
│   ├── template_save.py         # 模板固化（频次+质量双门槛）
│   ├── forgetting.py            # 遗忘机制（指数衰减曲线）
│   ├── memory_consolidation.py  # 记忆巩固
│   ├── async_evolution.py       # 异步演化闭环（生产者-消费者）
│   ├── rl_agent.py              # DQN 强化学习代理（纯 Python）
│   ├── ab_test.py               # A/B 测试框架
│   ├── cold_start.py            # 冷启动处理
│   ├── deep_feedback.py         # 深度反馈学习
│   ├── feedback_learner.py      # 反馈学习器
│   ├── pattern_miner.py         # 模式挖掘
│   ├── semantic_match.py        # 语义匹配
│   ├── multi_objective.py       # 多目标优化
│   ├── safe_ops.py              # 安全操作（边缘处理）
│   ├── sandbox_tool_gen.py      # 沙箱工具生成
│   ├── evolution_report.py      # 演化报告
│   └── evo_log.py               # 演化日志
├── memory_store/            # 数据存储层
│   ├── sqlite_db.py             # SQLite 结构化存储（WAL 模式）
│   ├── chroma_kb.py             # Chroma 向量知识库（ONNX 嵌入）
│   ├── bm25_index.py            # BM25 全文索引（增量更新+同义词）
│   ├── text_cleaner.py          # 文本降噪（5 步清洗）
│   ├── episodic_index.py        # 情景记忆索引
│   ├── file_archive.py          # 文件归档
│   ├── user_weight.py           # 用户权重存储
│   └── repositories/            # Repository 模式数据访问
├── service/                 # 业务服务层
│   ├── task_service.py          # 任务服务
│   ├── task_runner.py           # 定时任务调度器
│   ├── work_service.py          # 办公服务
│   ├── life_service.py          # 生活服务
│   ├── health_service.py        # 健康服务
│   ├── schedule_service.py      # 日程服务
│   ├── search_service.py        # 全局检索服务
│   ├── file_service.py          # 文件服务
│   ├── behavior_service.py      # 行为采集服务
│   ├── evolution_config_service.py  # 演化配置服务
│   └── ...                      # 其他业务服务
├── api/                     # FastAPI 路由
│   ├── app.py                   # FastAPI 应用入口
│   ├── chat.py                  # 对话 API（SSE 流式）
│   ├── task.py                  # 任务 API
│   ├── evolution.py             # 演化 API
│   ├── knowledge.py             # 知识库 API（上传/检索/管理）
│   ├── work.py                  # 办公 API
│   ├── life.py                  # 生活 API
│   ├── tool.py                  # 工具 API
│   ├── search.py                # 检索 API
│   ├── system.py                # 系统 API（备份/恢复/重置）
│   ├── ai.py                    # AI 能力 API
│   ├── note.py                  # 笔记 API
│   ├── schedule.py              # 日程 API
│   ├── settings.py              # 设置 API
│   ├── feedback.py              # 反馈 API
│   ├── behavior.py              # 行为 API
│   ├── user_model.py            # 用户画像 API
│   └── ...                      # 其他 API 路由
├── tools/                   # 工具集
│   ├── pdf_tools.py             # PDF 解析（pypdf）
│   ├── excel_tools.py           # Excel 处理（openpyxl）
│   ├── docx_tools.py            # Word 解析（python-docx）
│   ├── ocr_tools.py             # OCR 识别（PaddleOCR/easyocr/tesseract）
│   ├── text_writer.py           # 文本写入
│   ├── bill_stat.py             # 账单统计
│   └── sandbox_run.py           # 沙箱执行器
├── config/                  # 配置管理
│   ├── settings.py              # 配置加载（OmegaConf）
│   ├── path_config.py           # 路径配置
│   ├── app_config.yaml          # 应用配置
│   └── app_const.py             # 常量定义
├── core/                    # 核心基础设施
│   ├── context.py               # 任务上下文
│   └── logging.py               # 日志配置
├── frontend/                # React 前端
├── user_data/               # 用户数据目录（本地存储）
│   ├── db/                      # SQLite 数据库
│   ├── chroma/                  # Chroma 向量库
│   ├── backups/                 # 备份文件
│   └── tmp/                     # 临时文件
├── tests/                   # 测试
│   ├── test_retrieval_benchmark.py  # 检索基准测试
│   └── ...
├── main.py                  # 程序入口
├── pyproject.toml           # 项目依赖
└── PRD.md                   # 产品需求文档
```

## 🔒 隐私安全

- **纯本地运行**：所有数据存储在 `user_data/` 目录，零云端上传
- **沙箱隔离**：AI 生成脚本在受限环境执行，禁止危险操作
- **数据备份**：支持一键备份/恢复/重置
- **行为采集可控**：可在设置页开关行为采集

## 📝 API 概览

| 路由 | 功能 |
|------|------|
| `/api/chat/` | AI 对话（含 SSE 流式） |
| `/api/task/` | 任务 CRUD + 状态流转 + DAG |
| `/api/evolution/` | 演化中心（打分/权重/日志/模板） |
| `/api/kb/` | 知识库（上传/检索/管理/统计） |
| `/api/work/` | 办公模块（文书/Excel/报销/归档） |
| `/api/life/` | 生活模块（记账/健康/习惯/日程） |
| `/api/tool/` | 沙箱工具库 |
| `/api/search/` | 全局混合检索 |
| `/api/note/` | 笔记管理 |
| `/api/schedule/` | 日程管理 |
| `/api/system/` | 系统能力（备份/恢复/重置/存储信息） |
| `/api/settings/` | 系统设置 |
| `/api/behavior/` | 行为统计 |
| `/api/user-model/` | 用户画像 |

## 🧪 测试

```bash
# 运行检索基准测试（对比纯向量 vs 混合检索召回率）
python -m tests.test_retrieval_benchmark
```

## 📄 License

MIT
