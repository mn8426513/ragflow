# RAGFlow 项目结构详细文档 (Project Structure Documentation)

> **版本**: v0.26.0 | **生成日期**: 2026-07-16 | **语言**: 简体中文 / English

---

## 目录 (Table of Contents)

1. [项目概述 (Project Overview)](#1-项目概述)
2. [运行时架构 (Runtime Architecture)](#2-运行时架构)
3. [目录结构总览 (Directory Structure Overview)](#3-目录结构总览)
4. [后端核心模块 (Backend Core Modules)](#4-后端核心模块)
   - [4.1 API 层 (`api/`)](#41-api-层-api)
   - [4.2 RAG 引擎 (`rag/`)](#42-rag-引擎-rag)
   - [4.3 Agent 系统 (`agent/`)](#43-agent-系统-agent)
   - [4.4 文档解析 (`deepdoc/`)](#44-文档解析-deepdoc)
   - [4.5 公共模块 (`common/`)](#45-公共模块-common)
5. [前端架构 (`web/`)](#5-前端架构-web)
6. [Go 后端引擎 (`internal/`)](#6-go-后端引擎-internal)
7. [基础设施与部署](#7-基础设施与部署)
8. [数据流全景图 (Data Flow)](#8-数据流全景图)
9. [配置系统](#9-配置系统)
10. [测试架构](#10-测试架构)

---

## 1. 项目概述

**RAGFlow** 是一个基于深度文档理解的开源 RAG (Retrieval-Augmented Generation，检索增强生成) 引擎。它是一个全栈应用，主要功能包括:

- **深度文档解析**: 支持 PDF、DOCX、XLSX、PPT、Markdown、HTML、EPUB、JSON、图片、音频等 15+ 种格式
- **智能分块与索引**: 基于 Token 或标题层级的文档分块，支持向量化和全文索引
- **混合检索**: 向量相似度 + BM25 全文检索 + 重排序 (Reranking)
- **知识图谱 RAG (GraphRAG)**: 从文档中提取实体和关系，构建知识图谱，支持图增强检索
- **Agent 工作流**: 可视化拖拽式 Agent 画布，支持 LLM、工具调用、条件分支、循环等组件
- **多租户支持**: 完整的团队管理、权限控制和 API Key 体系

### 技术栈 (Technology Stack)

| 层级 | 技术 |
|------|------|
| **Python 后端** | Python 3.10-3.13, Quart (异步 Flask), Peewee ORM |
| **Go 后端** | Go + Gin 框架, C++ 分词库 (CGo 绑定) |
| **前端** | React 18, TypeScript, Vite 7, Tailwind CSS, shadcn/ui |
| **数据库** | MySQL / PostgreSQL |
| **检索引擎** | Elasticsearch / Infinity / OpenSearch / OceanBase |
| **缓存/队列** | Redis (缓存 + 消息队列 Stream) |
| **对象存储** | MinIO / S3 / OSS / GCS / Azure Blob |
| **容器化** | Docker + Docker Compose, Helm (Kubernetes) |

---

## 2. 运行时架构

RAGFlow 以 **两种独立的 Python 进程** 运行，由 `docker/launch_backend_service.sh` 编排:

```
┌─────────────────────────────────────────────────────────┐
│                    RAGFlow 运行时                         │
│                                                         │
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │   API Server        │  │   Task Executor(s)       │  │
│  │   (api/ragflow_     │  │   (rag/svr/task_         │  │
│  │    server.py)       │  │    executor.py)          │  │
│  │                     │  │                          │  │
│  │   Quart HTTP 服务   │  │   从 Redis Stream 消费    │  │
│  │   端口: 9380        │  │   文档处理任务            │  │
│  │   处理用户请求       │  │   解析→分块→嵌入→索引     │  │
│  └────────┬────────────┘  └───────────┬──────────────┘  │
│           │                           │                  │
│           └───────────┬───────────────┘                  │
│                       │                                  │
│              ┌────────┴────────┐                         │
│              │   Redis Stream  │  ← 消息队列/任务分发     │
│              └─────────────────┘                         │
│                                                         │
│  另外还有:                                              │
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │   Admin Server      │  │   MCP Server             │  │
│  │   (端口: 9381)      │  │   (端口: 9382)           │  │
│  └─────────────────────┘  └──────────────────────────┘  │
│                                                         │
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │   Go API Server     │  │   Go Admin Server        │  │
│  │   (端口: 9384)      │  │   (端口: 9383)           │  │
│  └─────────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 关键要点

- **API Server** 和 **Task Executor** 导入不同的代码路径，修改代码时需要注意当前模块属于哪个进程
- Task Executor 可以有多个并行实例（由 `WS` 环境变量控制），通过 Redis 消费者组实现负载均衡
- Go 后端是可选的重写版本，支持混合模式部署

---

## 3. 目录结构总览

```
ragflow/
├── api/                    # Python API 服务器 (Quart 异步框架)
│   ├── apps/               # 路由处理 + 认证 + 服务层
│   ├── db/                 # 数据库模型 (Peewee ORM) + DB 服务层
│   ├── common/             # API 内部共享代码
│   ├── utils/              # API 工具函数
│   └── ragflow_server.py   # ★ 服务器入口点
│
├── rag/                    # ★ RAG 核心引擎
│   ├── app/                # 文档解析应用层 (按格式分派)
│   ├── flow/               # 新管道架构 (DSL-based DAG)
│   ├── nlp/                # NLP/搜索/查询处理
│   ├── llm/                # LLM 集成 (30+ 厂商)
│   ├── graphrag/           # 知识图谱 RAG
│   ├── svr/                # Task Executor 服务
│   ├── prompts/            # 40+ LLM 提示词模板
│   ├── utils/              # 存储连接器、工具函数
│   └── res/                # 资源文件 (同义词词典等)
│
├── agent/                  # ★ Agent 工作流系统
│   ├── canvas.py           # DAG 执行引擎 (Graph + Canvas)
│   ├── component/          # 23 个工作流组件
│   ├── tools/              # 22 个 LLM 工具实现
│   ├── templates/          # 25 个预构建 Agent 模板
│   ├── plugin/             # 外部插件系统
│   └── sandbox/            # 代码执行沙箱 (Docker)
│
├── deepdoc/                # ★ 深度文档解析
│   ├── parser/             # 15+ 种文档格式解析器
│   └── vision/             # OCR/版面分析/表格识别
│
├── common/                 # 共享工具模块
│   ├── settings.py         # 全局设置管理
│   ├── constants.py        # 全局常量和枚举
│   ├── data_source/        # 30+ 外部数据源连接器
│   └── doc_store/          # 文档存储抽象层
│
├── web/                    # React/TypeScript 前端
│   └── src/
│       ├── pages/          # 页面组件 (按功能组织)
│       ├── components/     # 共享组件 + shadcn/ui 库
│       ├── hooks/          # React Query 封装
│       ├── services/       # API 服务层
│       ├── utils/          # 工具函数
│       ├── locales/        # 17 种语言翻译
│       └── interfaces/     # TypeScript 类型定义
│
├── internal/               # Go 后端引擎 (可选)
│   ├── handler/            # HTTP 请求处理器
│   ├── service/            # 业务逻辑服务
│   ├── dao/                # 数据访问层
│   ├── cpp/                # C++ 分词库
│   └── cmd/                # Go 可执行入口
│
├── docker/                 # Docker 部署配置
├── helm/                   # Kubernetes Helm Charts
├── sdk/                    # Python SDK (ragflow-sdk)
├── test/                   # 测试套件
├── docs/                   # Mintlify 文档站
├── conf/                   # 静态配置文件
├── memory/                 # 记忆模块
├── mcp/                    # MCP 协议实现
└── admin/                  # 管理工具 CLI
```

---

## 4. 后端核心模块

### 4.1 API 层 (`api/`)

#### 入口点: `api/ragflow_server.py`

```
启动流程:
  1. 初始化日志系统
  2. 加载配置 (service_conf.yaml + 环境变量)
  3. 初始化数据库 (创建表 + 填充初始数据)
  4. 加载全局插件 (从 embedded_plugins/)
  5. 启动后台进度更新线程 (每6秒)
  6. 启动 Quart HTTP 服务器 (端口 9380)
```

#### 应用工厂: `api/apps/__init__.py`

核心功能:
- 创建 Quart 应用实例，配置 CORS、Session (Redis-backed)、OpenAPI
- **认证系统**: 支持 JWT (Bearer Token)、API Token、Beta Token 三种模式
- **Blueprint 自动发现**: 扫描 `*_app.py`、`restful_apis/*.py`、`sdk/*.py` 文件并注册路由

**URL 路由规则:**

| 来源 | URL 前缀 | 说明 |
|------|----------|------|
| `api/apps/restful_apis/*.py` | `/api/v1/` | 新版 RESTful API |
| `api/apps/*_app.py` | `/v1/<page_name>/` | 传统 API |
| `api/apps/sdk/*.py` | `/v1/` | SDK API |
| `api/apps/backward_compat.py` | 同时提供 `/api/v1/` 和 `/v1/` | 向后兼容层 |

#### API 架构层次 (三层架构)

```
┌─────────────────────────────────────────────┐
│  RESTful API Controllers                    │
│  (api/apps/restful_apis/*.py)               │  ← 路由处理, Pydantic 验证
│  e.g., dataset_api.py, document_api.py,     │
│        chat_api.py, agent_api.py            │
├─────────────────────────────────────────────┤
│  API Business Logic                         │
│  (api/apps/services/*.py)                   │  ← 业务逻辑层
│  e.g., dataset_api_service.py,              │
│        document_api_service.py              │
├─────────────────────────────────────────────┤
│  DB Service Layer                           │
│  (api/db/services/*.py)                     │  ← 数据库 CRUD 操作
│  全部继承 CommonService 基类                  │
│  e.g., knowledgebase_service.py,            │
│        document_service.py, dialog_service  │
├─────────────────────────────────────────────┤
│  DB Models                                  │
│  (api/db/db_models.py, 1757 行)             │  ← Peewee ORM 模型
│  支持 MySQL 和 PostgreSQL                    │
│  自定义字段: JSONField, ListField            │
└─────────────────────────────────────────────┘
```

#### 关键 API 端点

| 模块 | 文件 | 主要功能 |
|------|------|----------|
| 数据集管理 | `dataset_api.py` | 知识库 CRUD, 搜索, GraphRAG/RAPTOR 索引 |
| 文档管理 | `document_api.py` | 上传, 解析, 下载, 重命名, 预览 |
| 聊天对话 | `chat_api.py` | 会话管理, 对话补全 (流式), 思维导图 |
| Agent 画布 | `agent_api.py` | Agent CRUD, 画布执行, 版本管理 |
| 大模型管理 | `models_api.py` | LLM 提供商管理, 默认模型配置 |
| 文件管理 | `file_api.py` | 文件/文件夹 CRUD, 上传, 层级结构 |
| 用户管理 | `user_api.py` | 登录/注册, OAuth, 密码重置, 团队管理 |
| 系统管理 | `system_api.py` | 版本, 健康检查, API Token, 日志级别 |
| 记忆管理 | `memory_api.py` | Agent 记忆配置 CRUD |
| MCP 服务 | `mcp_api.py` | MCP Server 配置管理 |

#### 认证系统 (`api/apps/auth/`)

| 文件 | 说明 |
|------|------|
| `oauth.py` | 通用 OAuth2 客户端 |
| `oidc.py` | OpenID Connect 客户端 (支持 JWKS 验证) |
| `github.py` | GitHub 特定 OAuth 客户端 |

---

### 4.2 RAG 引擎 (`rag/`)

#### 4.2.1 文档摄入管道 (`rag/flow/`)

新一代基于 DSL 的管道架构，将文档处理分解为 DAG 组件:

```
File(获取文件) → Parser(解析文档) → Chunker(分块) → Extractor(提取元数据) → Tokenizer(分词)
```

| 组件 | 文件 | 功能 |
|------|------|------|
| **File** | `file.py` | 从存储获取文档二进制内容 |
| **Parser** | `parser/parser.py` | 根据扩展名分派到正确的解析器 (PDF→DeepDOC, DOCX→python-docx 等) |
| **Chunker** | `chunker/` | 将文档切分为嵌入大小的块 (TokenChunker 按 token 数, TitleChunker 按标题层级) |
| **Extractor** | `extractor/extractor.py` | LLM 生成关键词、问题、摘要等元数据 |
| **Tokenizer** | `tokenizer/tokenizer.py` | 最终分词，生成 `content_ltks`、`content_sm_ltks` 等字段 |

#### 4.2.2 文档解析应用层 (`rag/app/`)

按文件类型的解析入口（传统路径）:

| 文件 | 适用文档类型 |
|------|-------------|
| `naive.py` | **通用/默认解析器**: PDF, DOCX, XLSX, TXT, Markdown, HTML, EPUB, JSON |
| `paper.py` | 学术论文 (提取标题、摘要、章节、参考文献) |
| `book.py` | 书籍 (处理章/节层级结构) |
| `laws.py` | 法律文档 |
| `resume.py` | 简历/CV (结构化字段提取) |
| `manual.py` | 技术手册/文档 |
| `picture.py` | 图片 (OCR 或 VLM 描述) |
| `audio.py` | 音频 (ASR 语音转文字) |
| `table.py` | 表格 (Excel, CSV) |
| `qa.py` | 问答对数据集 |
| `email.py` | 邮件 (.eml, .msg) |

#### 4.2.3 NLP/搜索/查询 (`rag/nlp/`)

| 文件 | 核心类/功能 |
|------|-----------|
| `search.py` | **`Dealer`** - 混合检索协调器: 向量 + BM25 + 重排序 + 引用插入 |
| `query.py` | **`FulltextQueryer`** - 全文搜索查询构建: BM25 加权, 同义词扩展, 中文细粒度分词 |
| `rag_tokenizer.py` | 分词器包装: `tokenize()`, 中英文检测, 繁简转换, 全半角转换 |
| `synonym.py` | **`Dealer`** - 同义词检测: 自定义词典 + NLTK WordNet |
| `term_weight.py` | 词项权重计算 (TF-IDF 风格) |

#### 4.2.4 LLM 集成 (`rag/llm/`)

工厂模式，运行时类发现。使用 `LLMBundle` 作为统一调用接口。

| 文件 | 支持提供商数 | 核心功能 |
|------|-----------|----------|
| `chat_model.py` | 30+ | Chat/Completion 模型: OpenAI, Anthropic, Gemini, Bedrock, Azure, Ollama, DeepSeek, Groq, Cohere, Tongyi-Qianwen, ZHIPU-AI, MiniMax, SILICONFLOW 等 |
| `embedding_model.py` | 25+ | 嵌入模型: OpenAI, Builtin (本地 BGE/Qwen3), HuggingFace, Ollama, Gemini, Jina, Cohere 等 |
| `rerank_model.py` | 20+ | 重排序模型: Jina, Cohere, NVIDIA, Voyage, QWen, HuggingFace 等 |
| `cv_model.py` | - | 视觉模型 (图片→文字 / VLM) |
| `ocr_model.py` | - | OCR 模型 (MinerU, Docling, PaddleOCR) |
| `sequence2txt_model.py` | - | 语音转文字 (ASR) |
| `tts_model.py` | - | 文字转语音 (TTS) |

#### 4.2.5 知识图谱 RAG (`rag/graphrag/`)

实现 Microsoft GraphRAG 风格的知识图谱构建:

```
文档分块 → 实体/关系提取 → (全局子图合并) → 实体消歧 → Leiden 社区检测 → 社区摘要生成
```

| 文件 | 功能 |
|------|------|
| `general/index.py` | **主编排器**: 协调整个 GraphRAG 管道，支持检查点/恢复、并行处理 |
| `general/extractor.py` | LLM 驱动的实体+关系提取 (通用/GraphRAG 风格) |
| `general/community_reports_extractor.py` | 使用 Leiden 算法 + LLM 生成社区摘要 |
| `general/leiden.py` | Leiden 社区检测算法 |
| `light/graph_extractor.py` | LightRAG 风格提取 (更轻量快速) |
| `ner/graph_extractor.py` | spaCy NER 提取 (无需 LLM) |
| `entity_resolution.py` | LLM 驱动的实体去重/合并 |
| `search.py` | **`KGSearch`** - 知识图谱增强搜索 |

#### 4.2.6 Task Executor (`rag/svr/`)

后台任务执行引擎:

```python
# rag/svr/task_executor.py - 启动入口
# 从 Redis Stream 消费任务: te.1.common (高优先级) > te.0.common (普通优先级)
# 
# 处理流程:
#   1. 解析文档 (dispatch to rag.app.*)
#   2. 分块 (tokenize + merge)
#   3. 提取关键词/问题
#   4. 嵌入向量化
#   5. 索引到检索引擎
#   6. (可选) RAPTOR 摘要
#   7. (可选) GraphRAG 知识图谱
#
# 并发控制: task_limiter, chunk_limiter, embed_limiter, kg_limiter
```

重构版 (`task_executor_refactor/`):

| 文件 | 功能 |
|------|------|
| `task_manager.py` | 任务生命周期管理 |
| `chunk_service.py` | 分块 CRUD |
| `embedding_service.py` | 嵌入生成与索引 |
| `raptor_service.py` | RAPTOR 分层摘要服务 |
| `post_processor.py` | 索引后处理 |

#### 4.2.7 提示词模板 (`rag/prompts/`)

40+ Markdown 格式的提示词模板:

- **简历**: `resume_basic_info.md`, `resume_education.md`, `resume_work_exp.md`
- **目录**: `toc_detection.md`, `toc_extraction.md`, `toc_relevance_system.md`
- **查询**: `question_prompt.md`, `multi_queries_gen.md`, `keyword_prompt.md`
- **引用**: `citation_prompt.md`, `citation_plus.md`
- **Agent 工具**: `next_step.md`, `reflect.md`, `tool_call_summary.md`
- **视觉**: `vision_llm_describe_prompt.md`, `vision_llm_figure_describe_prompt.md`

---

### 4.3 Agent 系统 (`agent/`)

#### 4.3.1 执行引擎 (`agent/canvas.py`)

```
Canvas.run() ─ 异步生成器, 产出 SSE 事件
  │
  ├─ 1. 加载 DSL → Graph 中的组件 DAG
  ├─ 2. 拓扑排序 → 执行路径 path[]
  ├─ 3. 批量并发执行 (_run_batch, 最多5个线程)
  ├─ 4. 控制流处理:
  │     • Categorize/Switch: 动态改变 path
  │     • Iteration/Loop: 子图循环执行
  │     • ExitLoop: 跳出循环
  ├─ 5. 流式输出: LLM → partial generator → Message SSE
  └─ 6. 产出事件: workflow_started → node_started
                   → message → node_finished
                   → workflow_finished
```

#### 4.3.2 工作流组件 (`agent/component/`)

23 个组件，通过文件系统扫描 + `importlib` 自动发现:

| 组件 | `component_name` | 功能描述 |
|------|-----------------|----------|
| **Begin** | `Begin` | 入口节点，处理初始查询和文件上传 |
| **LLM** | `LLM` | 核心 LLM 对话，支持流式、结构化输出、引用 |
| **Agent** | `Agent` | 工具调用 LLM，多轮 ReAct 循环 |
| **Switch** | `Switch` | 条件分支 (多条件 + AND/OR 逻辑) |
| **Categorize** | `Categorize` | LLM 分类器 (将输入分到预定义类别) |
| **Iteration** | `Iteration` | 数组迭代循环 |
| **IterationItem** | `IterationItem` | 迭代循环体 |
| **Loop** | `Loop` | 通用循环 (带终止条件) |
| **LoopItem** | `LoopItem` | 循环体 |
| **ExitLoop** | `ExitLoop` | 提前退出循环 |
| **Message** | `Message` | 最终输出节点 (Jinja2模板, 格式转换) |
| **UserFillUp** | `UserFillUp` | 交互式表单 |
| **Invoke** | `Invoke` | HTTP 请求节点 |
| **Browser** | `Browser` | 浏览器自动化 (Playwright) |
| **DocGenerator** | `DocGenerator` | 文档生成 (PDF/DOCX/TXT/Markdown) |
| **ExcelProcessor** | `ExcelProcessor` | Excel 读写/合并/转换 |
| **DataOperations** | `DataOperations` | 数据变换 (select_keys, combine, filter等) |
| **ListOperations** | `ListOperations` | 数组操作 (nth, head, filter, sort等) |
| **StringTransform** | `StringTransform` | 字符串分割/合并 |
| **VariableAggregator** | `VariableAggregator` | 变量聚合 |
| **VariableAssigner** | `VariableAssigner` | 变量赋值/修改 |

#### 4.3.3 工具实现 (`agent/tools/`)

22 个 LLM 可调用工具，同样通过文件系统扫描自动发现:

| 工具类别 | 工具 |
|----------|------|
| **搜索** | DuckDuckGo, Google, Tavily, SearXNG, Wikipedia |
| **学术** | ArXiv, PubMed, Google Scholar |
| **检索增强** | Retrieval (内部知识库检索, 支持 KG 增强) |
| **网页** | Crawler (crawl4ai 内容提取) |
| **代码/数据** | CodeExec (Python 沙箱), ExeSQL (多数据库 SQL) |
| **通讯** | Email (SMTP) |
| **翻译** | DeepL |
| **代码平台** | GitHub API |
| **金融** | YahooFinance, AkShare, TuShare, Jin10 (金十数据), WenCai (问财) |
| **天气** | QWeather |

#### 4.3.4 预构建模板 (`agent/templates/`)

25 个 JSON 格式的 Agent 工作流模板:

- **Deep Research**: 多 Agent 深度研究 (WebSearch Specialist → Content Deep Reader → Research Synthesizer)
- **SEO Article Writer**: SEO 文章写作
- **Academic Paper Generator**: 学术论文生成 (带反思循环)
- **Data Analysis Beginner Assistant**: 数据分析助手
- **CV Analysis**: 简历分析与候选人评估
- **Smart Customer Service**: 智能客服
- **Stock Market Research**: 股市研究
- **Text2SQL**: 自然语言转 SQL
- **Trip Planner**: 旅行规划
- **Advanced Ingestion Pipeline**: 高级文档摄入管道
- 等多种模板

#### 4.3.5 代码沙箱 (`agent/sandbox/`)

Docker 化的安全代码执行环境:
- Docker Compose 部署的 FastAPI 微服务
- 多提供商支持: 本地 Docker, E2B 云沙箱, 阿里云 Code Interpreter, SSH 远程执行
- Python 和 Node.js 沙箱基础镜像

---

### 4.4 文档解析 (`deepdoc/`)

#### PDF 解析管道 (最复杂的解析器)

```
PDF 文件
  │
  ├─ 1. 渲染: pdfplumber → 页面图片 + 字符数据
  ├─ 2. 乱码检测: PUA/CID 检测 + 字体编码检测
  ├─ 3. OCR: 文本检测 (边界框) + 文本识别 (字符读取)
  ├─ 4. 版面分析: YOLOv10 (ONNX) → 11 种布局类型
  │     • Text, Title, Figure, Figure caption,
  │       Table, Table caption, Header, Footer,
  │       Reference, Equation
  ├─ 5. 表格结构识别: TSR (ONNX) → 行/列/表头/跨格
  │     • 自动旋转校正 (0/90/180/270度)
  ├─ 6. 文本合并:
  │     • 水平合并 (同行同类型)
  │     • 垂直合并 (XGBoost 模型判断是否连段)
  │     • 列识别 (K-Means 聚类)
  ├─ 7. 表格/图片提取: 裁剪 + HTML 表格构建
  └─ 8. 过滤: DFS 基线分组 + 短碎片过滤
```

#### PDF 解析器类型

| 解析器 | 文件 | 说明 |
|--------|------|------|
| `RAGFlowPdfParser` | `pdf_parser.py` | 主解析器: OCR + 版面分析 + 表格识别 |
| `PlainParser` | `pdf_parser.py` | 简单文本提取 (pypdf, 无 OCR) |
| `VisionParser` | `pdf_parser.py` | VLM 逐页描述 |
| `PaddleOCRParser` | `paddleocr_parser.py` | 远程 PaddleOCR API |
| `MinerUParser` | `mineru_parser.py` | 远程 MinerU API (多后端) |
| `DoclingParser` | `docling_parser.py` | IBM Docling (本地+远程) |
| `TCADPParser` | `tcadp_parser.py` | 腾讯云文档重建 |
| `OpenDataLoaderParser` | `opendataloader_parser.py` | 远程 OpenDataLoader |

#### 其他格式解析器

| 格式 | 解析器类 | 库 |
|------|---------|-----|
| DOCX | `RAGFlowDocxParser` | `python-docx` |
| XLSX/CSV | `RAGFlowExcelParser` | `openpyxl` + `pandas` |
| PPT | `RAGFlowPptParser` | `python-pptx` |
| HTML | `RAGFlowHtmlParser` | `BeautifulSoup` |
| Markdown | `RAGFlowMarkdownParser` | 自定义 |
| EPUB | `RAGFlowEpubParser` | ZIP + HTML |
| JSON/JSONL | `RAGFlowJsonParser` | 递归分块 |
| TXT | `RAGFlowTxtParser` | 分隔符分块 |

#### 通用数据结构

```python
# Box (OCR/文本块的核心数据单元)
{
    "text": str,           # 提取/识别的文本
    "x0/x1/top/bottom": float,  # 坐标
    "page_number": int,    # 页码 (1-based)
    "layout_type": str,    # 布局类型
    "position_tag": str,   # @@page\tx0\tx1\ttop\tbottom##
}

# Section (返回给下游的文本块)
(text: str, position_tag: str)

# Table (返回给下游的表格)
((PIL.Image, html_or_caption: str), positions: list)
```

#### 视觉模块 (`deepdoc/vision/`)

| 文件 | 功能 |
|------|------|
| `ocr.py` | OCR 引擎: 文本检测 + 文本识别 |
| `layout_recognizer.py` | 版面识别 (YOLOv10 ONNX) + Ascend NPU 版 |
| `table_structure_recognizer.py` | 表格结构识别: 行/列/表头/跨格 + HTML 构建 |
| `recognizer.py` | 基础识别器: ONNX 模型运行器 |
| `seeit.py` | 可视化: 绘制边界框和标签 |
| `operators.py` | 图像预处理/后处理算子 (NMS 等) |

---

### 4.5 公共模块 (`common/`)

#### 核心文件

| 文件 | 说明 |
|------|------|
| `settings.py` | **全局设置**: 加载 service_conf.yaml → 初始化所有存储/搜索连接 → 管理 LLM 默认配置 |
| `constants.py` | **全局常量**: `RetCode` 枚举, `LLMType` 枚举, `Storage` 枚举, 自定义字段类型 |
| `config_utils.py` | 配置加载: `load_yaml_conf()`, `decrypt_database_config()`, `get_base_config()` |
| `exceptions.py` | 异常体系: `TaskCanceledException`, `ModelException` (带 retryable 标志) |
| `crypto_utils.py` | 加密工具: RSA 加解密, 密码哈希, API Key 生成/验证 |
| `mcp_tool_call_conn.py` | MCP 工具调用连接器 |
| `log_utils.py` | 日志初始化 |
| `versions.py` | 版本信息 |

#### 外部数据源连接器 (`common/data_source/`)

30+ 外部平台连接器:
- **代码平台**: GitHub, GitLab, Bitbucket
- **协作工具**: Google Drive, Jira, Slack, Notion, Confluence, SharePoint, OneDrive
- **通讯**: Gmail, Outlook, Discord, Teams, DingTalk (钉钉)
- **CRM/商务**: Salesforce
- **其他**: RSS, IMAP, WebDAV, Seafile, Moodle, Zendesk, AirTable, Asana, Box, Dropbox

#### 文档存储抽象 (`common/doc_store/`)

统一接口，多引擎支持:
- **Elasticsearch**: `es_conn_base.py` + `es_conn_pool.py`
- **Infinity**: `infinity_conn_base.py` + `infinity_conn_pool.py`
- **OceanBase**: `ob_conn_base.py` + `ob_conn_pool.py`

---

## 5. 前端架构 (`web/`)

### 技术栈

```
React 18 + TypeScript + Vite 7
├── shadcn/ui (Radix UI 原语 + Tailwind CSS)
├── @tanstack/react-query v5    (服务器状态管理)
├── Zustand v4                   (Agent 画布图状态)
├── react-router v7              (路由)
├── react-hook-form + zod        (表单验证)
├── i18next + react-i18next      (17 种语言国际化)
├── @xyflow/react                (Agent 画布可视化)
├── axios                        (HTTP 客户端)
├── recharts                     (图表)
└── immer                        (不可变数据)
```

### 目录结构

```
web/src/
├── main.tsx                # 应用入口: ReactDOM.createRoot, initLanguage()
├── app.tsx                 # 根组件: QueryClient → Theme → Router
├── routes.tsx              # 路由定义 (react-router v7, 懒加载)
│
├── pages/                  # 页面组件 (按功能域组织)
│   ├── home/               # 首页/仪表盘
│   ├── login-next/         # 登录页
│   ├── datasets/           # 知识库列表
│   ├── dataset/            # 知识库详情 (文件/检索测试/知识图谱/设置)
│   ├── next-chats/         # 聊天对话 (会话列表/聊天界面/分享/嵌入)
│   ├── next-searches/      # 搜索
│   ├── agents/             # Agent 列表/模板/日志
│   ├── agent/              # Agent 画布编辑器 (最大模块)
│   │   ├── canvas/         # xyflow 画布集成
│   │   ├── form/           # 组件配置表单
│   │   ├── store.ts        # Zustand 图状态
│   │   ├── hooks/          # 画布相关 hooks
│   │   └── ...
│   ├── chunk/              # 分块管理
│   ├── user-setting/       # 用户设置 (资料/模型/团队/API/MCP)
│   ├── files/              # 文件管理器
│   ├── memories/           # 记忆管理
│   ├── admin/              # 管理控制台 (独立布局)
│   ├── dataflow-result/    # 数据流结果
│   └── document-viewer/    # 文档查看器
│
├── components/             # 组件库
│   ├── ui/                 # shadcn/ui 组件 (65+ 组件, 锁定不可直接修改)
│   ├── message-input/      # 聊天输入框
│   ├── next-message-item/  # 聊天消息气泡
│   ├── parse-configuration/# 文档解析配置
│   ├── llm-select/         # LLM 模型选择器
│   ├── jsonjoy-builder/    # JSON Schema 表单构建器
│   └── ...                 # 更多共享组件
│
├── hooks/                  # React Query 封装
│   ├── use-knowledge-request.ts   # 知识库 hooks
│   ├── use-chat-request.ts       # 聊天 hooks
│   ├── use-agent-request.ts      # Agent hooks
│   ├── use-llm-request.tsx       # LLM hooks
│   └── ...
│
├── services/               # API 服务层
│   ├── knowledge-service.ts
│   ├── agent-service.ts
│   ├── next-chat-service.ts
│   └── ...
│
├── utils/                  # 工具函数
│   ├── next-request.ts     # ★ 主要 axios 实例 (请求/响应拦截器)
│   ├── api.ts              # ★ API 端点 URL 注册表
│   ├── register-server.ts  # 服务工厂
│   └── ...
│
├── locales/                # 国际化 (17 种语言, 懒加载)
│   ├── en.ts (157KB)       # 英文 (默认内联加载)
│   ├── zh.ts (130KB)       # 简体中文
│   └── ...                 # 15 种其他语言
│
├── interfaces/             # TypeScript 类型定义
│   ├── database/           # 数据库类型 (agent, chat, dataset, document 等)
│   └── request/            # API 请求类型
│
├── constants/              # 常量定义
├── layouts/                # 布局组件 (RootLayout + Header)
├── wrappers/               # 路由守卫 (auth.tsx)
└── theme/                  # 主题配置
```

### API 层架构 (三层)

```
┌──────────────────────────────────┐
│  React Query Hooks               │  ← useQuery / useMutation
│  (hooks/use-*-request.ts)        │
├──────────────────────────────────┤
│  Service Layer                   │  ← registerServer / registerNextServer
│  (services/*.ts)                 │
├──────────────────────────────────┤
│  HTTP Client                     │
│  (utils/next-request.ts)         │  ← axios 单例 + 拦截器
│  - 请求: snake_case 转换,        │
│    添加 Authorization header     │
│  - 响应: 401 重定向登录,          │
│    错误提示, LLM 列表缓存         │
├──────────────────────────────────┤
│  API URL Registry                │
│  (utils/api.ts)                  │  ← 集中式 URL 管理
│  webAPI = '/v1'                  │
│  restAPIv1 = '/api/v1'           │
└──────────────────────────────────┘
```

### 状态管理

| 方案 | 用途 |
|------|------|
| **Zustand** | Agent 画布图状态 (`useGraphStore`): nodes, edges, selection |
| **React Query** | 所有服务器状态 (缓存, 自动重新获取, 乐观更新) |
| **React Context** | 主题切换 (dark/light) |
| **react-hook-form** | 表单状态 |

---

## 6. Go 后端引擎 (`internal/`)

Go 语言重写的后端引擎（可选，支持混合部署）:

| 目录 | 说明 |
|------|------|
| `cmd/` | 可执行入口: `server_main.go` (API), `admin_server.go` (管理), `ingestion_server.go` (摄入), `ragflow_cli.go` (CLI) |
| `handler/` | Gin HTTP 请求处理器 (20+ 处理器，与 Python API 功能对应) |
| `service/` | 业务逻辑服务层 |
| `dao/` | 数据访问层 (SQL/ES 交互) |
| `entity/` | 数据实体定义 |
| `router/` | URL 路由配置 |
| `cpp/` | **C++ 原生分词库** (CGo 绑定): RAG 分析器, 17 种语言的 Snowball 词干提取器, OpenCC 繁简转换, RE2 正则引擎, PCRE2 |
| `tokenizer/` | C++ 分词器的 Go 接口 |
| `ingestion/` | gRPC 文档摄入管道 |
| `storage/` | 文件/对象存储抽象 (S3, MinIO, OSS) |
| `common/` | Go 共享工具 |

### 代理方案 (Vite 配置)

```
API_PROXY_SCHEME 环境变量控制:
  python  → Go API(9384) + Admin(9383) → Python API(9380) + Admin(9381)
  go      → Go API(9384) + Admin(9383)
  hybrid  → Go API(9384) + Admin(9383) + 部分路由到 Python(9380)
```

---

## 7. 基础设施与部署

### Docker 部署

```bash
# 完整栈部署
cd docker
docker compose -f docker-compose.yml up -d

# 服务组成:
#   ragflow-server  (API Server + Task Executor)
#   mysql           (数据库)
#   elasticsearch   (检索引擎, 默认)
#   redis           (缓存/队列)
#   minio           (对象存储)
```

关键文件:
- `docker/docker-compose.yml` - 主编排文件
- `docker/docker-compose-base.yml` - 基础服务
- `docker/.env` - 环境变量 (DOC_ENGINE, 密码, 端口等)
- `docker/entrypoint.sh` - 容器入口点 (支持多种服务角色)
- `docker/launch_backend_service.sh` - 后端启动脚本
- `docker/nginx/` - Nginx 反向代理配置

### Kubernetes (Helm)

```
helm/
├── Chart.yaml            # Chart 元数据
├── values.yaml           # 默认配置
└── templates/
    ├── ragflow.yaml      # 主部署 + 服务
    ├── mysql.yaml        # MySQL StatefulSet
    ├── elasticsearch.yaml# ES StatefulSet
    ├── minio.yaml        # MinIO 部署
    ├── redis.yaml        # Redis 部署
    ├── ingress.yaml      # Ingress 配置
    └── ...
```

### 配置文件

| 文件 | 说明 |
|------|------|
| `conf/service_conf.yaml` | 主服务配置 (主机/端口/数据库连接) |
| `conf/llm_factories.json` (270KB) | LLM 提供商定义 |
| `conf/all_models.json` (157KB) | 所有支持的模型目录 |
| `conf/system_settings.json` | 系统设置 Schema |
| `conf/models/*.json` | 每个 LLM 提供商的详细配置 (~50 个文件) |

---

## 8. 数据流全景图

### 文档摄入流程 (Document → Chunks → Index)

```
┌──────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐    ┌──────────┐
│  File    │───→│  Parser  │───→│  Chunker  │───→│Tokenizer │───→│  Index   │
│ 获取文件  │    │ 解析文档  │    │  分块     │    │  分词    │    │  索引    │
└──────────┘    └──────────┘    └───────────┘    └──────────┘    └──────────┘
                     │                                          │
                     │  PDF → DeepDOC/MinerU/Docling/...       │ ES/Infinity/
                     │  DOCX → python-docx                     │ OceanBase
                     │  Image → OCR/VLM                        │
                     │  Audio → ASR                            │
                     │                                    ┌─────┴──────┐
                     │                                    │ 可选后处理:  │
                     │                                    │ • RAPTOR    │
                     │                                    │ • GraphRAG  │
                     │                                    └────────────┘
```

### 搜索/检索流程 (Query → Chunks → Answer)

```
┌──────────┐    ┌────────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Query   │───→│ Fulltext   │───→│ Hybrid   │───→│ Re-rank  │───→│   LLM    │
│  用户查询  │    │ Queryer   │    │ Search   │    │  重排序   │    │  生成回答 │
└──────────┘    │ 查询构建   │    │ 混合检索  │    └──────────┘    └──────────┘
                └────────────┘    └──────────┘
                     │                 │
                • 分词            • 全文匹配 (BM25)
                • 同义词扩展       • 向量相似度
                • 词项加权        • 融合排序
                • N-gram          • 引用插入
```

### Agent 工作流执行

```
┌────────────┐    ┌──────────────┐    ┌──────────────┐
│  DSL JSON  │───→│  Graph.load  │───→│ Canvas.run() │
│  工作流定义  │    │  实例化组件   │    │  异步生成器   │
└────────────┘    └──────────────┘    └──────────────┘
                                              │
                                    ┌─────────┴─────────┐
                                    │  拓扑顺序执行组件:  │
                                    │  Begin → LLM →    │
                                    │  Message (流式输出) │
                                    │                   │
                                    │  控制流:           │
                                    │  Switch/Categorize │
                                    │  Iteration/Loop   │
                                    │  工具调用:         │
                                    │   Retrieval,      │
                                    │   WebSearch, ...  │
                                    └───────────────────┘
```

---

## 9. 配置系统

### 配置加载顺序

```
1. conf/service_conf.yaml        ← 主配置文件
2. docker/.env                   ← 环境变量
3. 运行时环境变量                ← 最高优先级
```

### 关键环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DOC_ENGINE` | 检索引擎 | `elasticsearch` (可选: `infinity`, `oceanbase`, `opensearch`) |
| `TZ` | 时区 | `Asia/Shanghai` |
| `WS` | Task Executor 并行数 | `1` |
| `QUART_RESPONSE_TIMEOUT` | API 响应超时 | `600` (秒) |
| `MAX_CONTENT_LENGTH` | 最大请求体 | `1GB` |
| `LITELLM_LOCAL_MODEL_COST_MAP` | 阻止 LiteLLM 网络访问 | `True` |

### 数据库引擎切换

```bash
# 切换到 Infinity
DOC_ENGINE=infinity docker compose down -v && docker compose up -d

# 切换到 OceanBase
DOC_ENGINE=oceanbase docker compose down -v && docker compose up -d
```

---

## 10. 测试架构

### Python 测试

```
test/
├── unit_test/              # 单元测试 (pytest + markers: p1/p2/p3)
│   ├── common/             # 公共模块测试
│   ├── api/                # API 测试
│   ├── deepdoc/parser/     # 文档解析器测试
│   ├── rag/                # RAG 引擎测试
│   └── memory/             # 记忆模块测试
├── testcases/              # 集成和 API 测试
│   ├── restful_api/        # RESTful 路由测试
│   ├── test_http_api/      # HTTP 层测试
│   ├── test_sdk_api/       # SDK 测试
│   └── test_web_api/       # Web 层测试
├── benchmark/              # 性能基准测试
├── fixtures/               # 测试数据 (MinerU 样本输出等)
└── playwright/             # E2E 浏览器测试 (Playwright)
    ├── auth/               # 认证流程测试
    └── e2e/                # 端到端功能测试
```

### 前端测试

```
web/
├── jest.config.ts          # Jest 单元测试
├── .storybook/             # Storybook v9 组件展示
└── src/stories/            # 组件故事
```

### Go 测试

```
internal/
├── handler/*_test.go       # 每个处理器都有对应的测试文件
├── service/*_test.go       # 每个服务都有对应的测试文件
├── dao/*_test.go           # 每个 DAO 都有对应的测试文件
└── utility/*_test.go       # 工具函数测试
```

### 运行测试

```bash
# Python
uv run pytest                          # 所有测试
uv run pytest -m p1                    # 高优先级测试
uv run pytest test/unit_test/rag/      # 特定模块

# 前端
cd web && npm run test                 # Jest 测试
cd web && npm run lint                 # ESLint

# Go
./run_go_tests.sh                      # Go 测试脚本
```

---

## 附录 A: 关键文件速查表

| 文件路径 | 作用 |
|----------|------|
| `api/ragflow_server.py` | ★ API 服务器入口 |
| `api/apps/__init__.py` | ★ Quart 应用工厂 + 认证 + 路由自动发现 |
| `api/db/db_models.py` | ★ 所有 Peewee ORM 数据库模型 |
| `api/db/services/common_service.py` | ★ 通用 CRUD 服务基类 |
| `agent/canvas.py` | ★ Agent DAG 执行引擎 (Graph + Canvas) |
| `agent/component/__init__.py` | ★ 组件自动发现与注册 |
| `agent/tools/__init__.py` | ★ 工具自动发现与注册 |
| `rag/flow/pipeline.py` | ★ 文档摄入管道 (新架构) |
| `rag/nlp/search.py` | ★ 混合检索协调器 (Dealer) |
| `rag/nlp/query.py` | ★ 全文搜索查询构建 (FulltextQueryer) |
| `rag/llm/chat_model.py` | ★ LLM 集成 (30+ 提供商) |
| `rag/svr/task_executor.py` | ★ 后台任务执行器 |
| `rag/graphrag/general/index.py` | ★ GraphRAG 管道编排器 |
| `common/settings.py` | ★ 全局设置初始化 |
| `common/constants.py` | ★ 全局常量和枚举 |
| `deepdoc/parser/pdf_parser.py` | ★ PDF 解析器 (最复杂的解析器) |
| `web/src/utils/next-request.ts` | ★ 前端 axios HTTP 客户端 |
| `web/src/utils/api.ts` | ★ 前端 API URL 注册表 |
| `web/src/routes.tsx` | ★ 前端路由定义 |
| `docker/entrypoint.sh` | ★ Docker 容器入口点 |

## 附录 B: 开发命令速查

```bash
# === 后端 ===
uv sync --python 3.13 --all-extras     # 安装 Python 依赖
source .venv/bin/activate              # 激活虚拟环境
export PYTHONPATH=$(pwd)               # 设置 Python 路径
bash docker/launch_backend_service.sh  # 启动后端
uv run pytest                          # 运行测试
ruff check && ruff format              # 代码质量

# === 前端 ===
cd web && npm install                  # 安装依赖
cd web && npm run dev                  # 开发服务器 (端口 9222)
cd web && npm run build                # 生产构建
cd web && npm run lint                 # ESLint 检查

# === Docker ===
cd docker
docker compose -f docker-compose.yml up -d    # 完整栈部署
docker logs -f ragflow-server                 # 查看服务器日志
docker compose down -v && docker compose up -d # 重建 (切换引擎时)
```

---

> **文档版本**: 1.0 | **最后更新**: 2026-07-16
> 本文档基于 RAGFlow v0.26.0 代码库生成
