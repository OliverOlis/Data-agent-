# AI 数据运营分析 Agent MVP

这是一个面向中文业务问题的电商数据分析 Agent 本地 MVP。系统使用版本化指标语义层约束查询，经过只读 SQL 策略检查后访问 SQLite，并返回结构化数据质量结果和运营分析报告。

## 已实现

- 10 个电商指标和中文别名：销售额、订单数、活跃用户、付费率、客单价、复购等；
- 20 条黄金问题/SQL 示例，可作为后续模型检索和离线评测集；
- 可重复的 2026 年电商模拟数据，包含退款、取消、重复事件和复购样本；
- FastAPI：意图解析、指标匹配、澄清问题、SQL 生成、只读执行、质量检查和报告输出；
- 确定性安全策略：单条 SELECT、表白名单、时间条件、行数和执行时限；
- Streamlit 页面：指标口径、质量、报告、数据表和 SQL 过程展示；
- 无需模型 API 即可运行；后续可以把语义解析器替换为 LLM 适配器。

## 本地运行

使用 Python 3.11+：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.app:app --reload
```

启动后访问 `http://127.0.0.1:8000/docs`。调用示例：

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/analyze `
  -H "Content-Type: application/json" `
  -d '{"query":"最近三个月各渠道的销售额"}'
```

启动可视化页面：

```powershell
streamlit run frontend/streamlit_app.py
```

运行测试和黄金评测：

```powershell
python -m pytest -q
python -m scripts.evaluate
```

## 代码结构

```text
backend/       FastAPI 与固定工作流
database/      SQLite schema、元数据表、模拟数据
semantic/      版本化指标/维度定义和黄金示例
policy/        SQL 白名单与只读策略
executor/      有超时和行数上限的 SQLite 执行器
frontend/      Streamlit MVP 页面
tests/         API、语义、数据库、安全和评测测试
```

## 当前边界

MVP 只使用单租户本地 SQLite。它不会修改数据库，也不会把相关性解释为因果关系；“转化率”在缺少起点、终点或窗口时会先追问。生产使用前仍需接入真实身份权限、敏感字段脱敏、审计和模型服务。
