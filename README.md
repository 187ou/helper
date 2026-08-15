# 桌面智能助手 (Desktop Assistant)

私有化本地运行的 AI 个人工作台，集成任务编排、自适应演化、知识库、办公自动化、生活健康管理。

## ✨ 核心能力

### 🧠 LangGraph DAG 任务编排
- 自然语言指令自动拆解为 DAG 任务链路
- 支持串行/并行节点、断点续跑、失败重试
- SSE 流式输出，实时查看执行进度

### 🔄 自适应演化引擎
- **双维度打分**：工作/生活双维度 LLM 评估任务质量
- **权重迭代**：高频习惯自动提权，过期行为衰减
- **流程优化**：自动识别冗余步骤，合并可并行的串行环节
- **模板固化**：高频任务自动沉淀为可复用模板

### 🔍 混合检索 (RAG)
- Chroma 向量库 + BM25 全文索引
- RRF (Reciprocal Rank Fusion) 融合排序
- 支持 PDF/Word/TXT/Markdown/Excel 多格式文档

### 🛠️ 沙箱工具生成
- LLM 自动生成轻量化 Python 工具
- AST 静态安全检查 + 子进程隔离执行
- 超时保护、黑名单机制

### 💼 全场景覆盖
- 职场办公：文书撰写、Excel 处理、报销整理、文件归档
- 生活健康：记账复盘、健康提醒、习惯打卡
- 私有知识库：向量检索、笔记管理、文档摘要

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────┐
│                  Frontend (React + Vite)             │
│  Ant Design · ReactFlow · XYFlow · TailwindCSS      │
└────────────────────────┬────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────┐
│              Backend (FastAPI + Uvicorn)             │
│  ┌───────────┐ ┌────────────┐ ┌────────────────┐   │
│  │ Agent Core│ │ Evolution  │ │ Memory Store   │   │
│  │ LangGraph │ │ Engine     │ │ SQLite + Chroma│   │
│  │ LLM Client│ │ Judge/Weight│ │ BM25 + Vector │   │
│  └───────────┘ └────────────┘ └────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.13, FastAPI, LangGraph, LangChain |
| 存储 | SQLite (WAL), Chroma (向量), BM25 (全文) |
| 前端 | React 19, Vite, Ant Design 6, ReactFlow |
| AI | OpenAI 兼容 API / Ollama 本地双模式 |
| 沙箱 | AST 检查 + 子进程隔离 + 超时控制 |

## 🚀 快速开始

### 环境要求
- Python >= 3.13, < 3.14
- Node.js >= 18

### 1. 后端启动

```bash
# 安装依赖
uv sync

# 配置 LLM（编辑 conf/app_config.yaml 或启动后在前端设置）
# 支持 OpenAI 兼容 API 和 Ollama 本地模式

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
├── agent_core/          # AI Agent 核心
│   ├── graph_builder.py     # LangGraph DAG 构建
│   ├── node_executor.py     # 节点执行器（流式 + 校验重试）
│   ├── task_parser.py       # 自然语言任务拆解
│   ├── task_scheduler.py    # 任务调度（含演化闭环）
│   ├── llm_client.py        # LLM 客户端（双模式）
│   └── result_validator.py  # 结果校验与纠错
├── evolution_core/      # 自适应演化引擎
│   ├── judge_score.py       # 双维度打分
│   ├── weight_evolve.py     # 权重迭代（提权/衰减）
│   ├── flow_optimize.py     # 流程优化
│   ├── template_save.py     # 模板固化
│   ├── sandbox_tool_gen.py  # 沙箱工具生成
│   └── evo_log.py           # 演化日志
├── memory_store/        # 数据存储层
│   ├── sqlite_db.py         # SQLite 结构化存储
│   ├── chroma_kb.py         # Chroma 向量知识库
│   ├── bm25_index.py        # BM25 全文索引
│   └── repositories/        # Repository 模式数据访问
├── service/             # 业务服务层
├── api/                 # FastAPI 路由
├── tools/               # 工具集（PDF/Excel/沙箱）
├── config/              # 配置管理（OmegaConf）
├── core/                # 上下文、日志
├── frontend/            # React 前端
├── main.py              # 程序入口
└── pyproject.toml       # 项目依赖
```

## 🔒 隐私安全

- **纯本地运行**：所有数据存储在 `user_data/` 目录，无云端上传
- **沙箱隔离**：AI 生成脚本在受限环境执行，禁止危险操作
- **数据备份**：支持一键备份/恢复/重置

## 📝 API 概览

| 路由 | 功能 |
|------|------|
| `/api/chat/` | AI 对话（含 SSE 流式） |
| `/api/task/` | 任务 CRUD + 状态流转 + DAG |
| `/api/evolution/` | 演化中心（打分/权重/日志） |
| `/api/kb/` | 知识库（上传/检索/管理） |
| `/api/work/` | 办公模块（文书/Excel/报销） |
| `/api/life/` | 生活模块（记账/健康/习惯） |
| `/api/tool/` | 沙箱工具库 |
| `/api/search/` | 全局混合检索 |
| `/api/system/` | 系统能力（备份/恢复/重置） |

## 📄 License

MIT
