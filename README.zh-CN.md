# OpenDataFusion

**API 优先的开源低代码数据平台，覆盖数据交付的完整闭环。**

连接数据源，完成数据同步与加工，构建数据集和指标，发布受治理的数据接口，
搭建看板与内部应用，并在同一个项目空间中完成运维。外部 AI 操作方可以通过
MCP 使用同一套能力。

[English](README.md) · [简体中文](README.zh-CN.md)

[![CI](https://github.com/CildCo/opendatafusion/actions/workflows/ci.yml/badge.svg)](https://github.com/CildCo/opendatafusion/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/CildCo/opendatafusion?include_prereleases&sort=semver)](https://github.com/CildCo/opendatafusion/releases)
[![Container](https://img.shields.io/badge/container-ghcr.io%2FCildCo%2Fopendatafusion-2496ed)](https://github.com/CildCo/opendatafusion/pkgs/container/opendatafusion)

![OpenDataFusion 概览](docs/images/dashboard.png)

## 为什么选择 OpenDataFusion

- **一条完整交付链路**：数据源 → 管道 → 数据集/指标 → 接口、看板或应用；
  血缘、质量、审批和审计都在同一套产品模型里。
- **为运维而设计**：PostgreSQL 持久化任务队列、可重试 worker、单 leader
  调度器、游标安全回填、健康事件、指标和备份脚本。
- **治理状态可见**：列脱敏、行策略、受限数据源、质量规则和审批发布都是
  明确的产品状态，而不是藏在错误路径里的行为。
- **无需内置聊天框即可被 AI 操作**：MCP 服务向外部智能体提供只读工具和
  受审批保护的写工具；所有管理动作同时也通过 HTTP API 提供。

## 功能概览

| 领域 | 能力 |
| --- | --- |
| **数据源** | PostgreSQL、MySQL/MariaDB、SQLite、Oracle、SQL Server、ClickHouse、HTTP、Elasticsearch，以及 CSV/TSV/Parquet/JSON/Excel 文件；DSN 加密、连通性测试、元数据同步和 schema drift 告警。 |
| **管道 Studio** | 可视化 DAG：source、filter、select、rename、cast、join、aggregate、union、dedupe、quality、sink；schema 校验、节点级错误策略、预览、版本化发布、cron、游标查看/重置、有界回填。 |
| **接口 Studio** | 可视化单表查询或受控 SQL；类型化参数；预览/测试；审批发布与回滚；生成文档；AK/SK 签名调用 `/openapi/{key}`。 |
| **模型 Studio** | 数据集和指标资产；schema、预览、审批发布；面向 AI 的读取工具。 |
| **看板 Studio** | 12 列栅格看板，卡片、折线/柱状/饼图、表格和文本；参数与 widget 过滤器；拖拽调整；版本化发布；只读运行页和限时分享链接。 |
| **应用 Studio** | 多页内部应用，支持参数、指标卡、表格、行详情抽屉，以及基于已发布数据集的带审计新增/修改/删除表单。 |
| **目录与血缘** | 表和字段搜索、标签、列级血缘、下游影响分析和健康事件。 |
| **治理** | 列分类与脱敏、行策略、数据标准、freshness/regex/enum/schema 质量规则，以及带审计的策略变更。 |
| **运维** | 运维中心、队列概览、任务重试、告警确认、Prometheus 指标、请求 ID、JSON 日志、备份恢复和 HA 指南。 |
| **开放 API 与 MCP** | 管理 API、签名公共网关、streamable HTTP MCP、stdio MCP，以及审批令牌保护的写工具。 |

## 架构

```text
                 ┌──────────────────────────────┐
                 │  反向代理 / TLS              │
                 └──────────────┬───────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐      ┌─────────────────┐     ┌─────────────────┐
│ odf-api       │      │ odf-mcp         │     │ 静态控制台      │
│ FastAPI       │      │ streamable HTTP │     │ Vue 3 / /ui/    │
└───────┬───────┘      └────────┬────────┘     └─────────────────┘
        │                       │
        └───────────┬───────────┘
                    ▼
          ┌──────────────────┐
          │ PostgreSQL       │
          │ 控制面 + 任务队列│
          └───────┬──────────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
┌───────────────┐    ┌─────────────────┐
│ odf-scheduler │    │ odf-worker × N  │
│ leader lock   │    │ SKIP LOCKED     │
└───────────────┘    └─────────────────┘
```

API 无状态；调度与执行持久化并可独立扩展。详见
[架构](docs/ARCHITECTURE.md)、[交付](docs/DELIVERY.md)、[HA](docs/HA.md) 和
[安全](docs/SECURITY.md)。

## 快速开始

### Docker Compose

```bash
git clone https://github.com/CildCo/opendatafusion.git
cd opendatafusion/deploy/docker
cp .env.example .env
./../../scripts/generate-env.sh .env
docker compose up -d --build
docker compose exec api python -m odf.cli create-admin \
  --username admin --password 'ChangeMe123!'
```

打开 <http://localhost:18080/ui/> 登录。API 端口为 `18080`，MCP 端口为
`18082`。

### 本地开发

```bash
cd impl
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
# 设置 ODF_DATABASE_URL、ODF_JWT_SECRET、ODF_FERNET_KEY
.venv/bin/alembic upgrade head
.venv/bin/python -m odf.cli create-admin \
  --username admin --password 'ChangeMe123!'

# 分别在三个终端运行
.venv/bin/uvicorn odf.main:app --host 127.0.0.1 --port 18080
.venv/bin/python -m odf.scheduler
.venv/bin/python -m odf.worker
```

前端构建产物位于 `impl/odf/static`，由 `/ui/` 提供。前端开发见
[frontend/README.md](frontend/README.md)。

## 文档

| 文档 | 内容 |
| --- | --- |
| [架构](docs/ARCHITECTURE.md) | 进程、执行语义、扩展和故障模型 |
| [交付](docs/DELIVERY.md) | Docker、Compose、Helm 和 systemd |
| [治理](docs/GOVERNANCE.md) | 目录、血缘、脱敏、行策略、质量和审计 |
| [HA](docs/HA.md) | leader 选举、worker 扩展、备份与恢复 |
| [安全](docs/SECURITY.md) | 信任边界、密钥、SSRF 防护和漏洞报告 |
| [性能](docs/PERFORMANCE.md) | 指标、连接池、压测和基准结果 |
| [基准测试](docs/BENCHMARKS.md) | 30GB 多源结果和缓存实验 |
| [测试](docs/TESTING.md) | 单元、集成、浏览器和完整矩阵测试 |

## 开发

- 后端：Python 3.11、FastAPI、SQLAlchemy 2、Alembic、PostgreSQL。
- 前端：Vue 3、Vite、Element Plus、Vue Flow、CodeMirror、ECharts。
- 默认分支：`main`。Pull Request 会运行单元、集成、浏览器和 Helm 检查。
- 提交前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
- 安全问题请按 [SECURITY.md](SECURITY.md) 私下报告，不要开公开 Issue。

## 社区

- [GitHub Issues](https://github.com/CildCo/opendatafusion/issues)：缺陷和明确的
  功能请求。
- [GitHub Discussions](https://github.com/CildCo/opendatafusion/discussions)：
  设计讨论、部署问题和经验分享。
- [路线图](ROADMAP.md) 和 [变更日志](CHANGELOG.md)。
- [行为准则](CODE_OF_CONDUCT.md)。

## 许可证

Apache License 2.0，见 [LICENSE](LICENSE)。项目名称和标识的使用见
[TRADEMARK.md](TRADEMARK.md)；欢迎 Fork，但请勿暗示官方背书。
