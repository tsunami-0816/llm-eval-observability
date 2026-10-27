# llm-eval-observability

LLM应用评测与可观测平台：调用追踪 + Prompt版本管理 + bad case回归 + 监控看板。

## 技术栈
Python FastAPI + SQLite + Vue3 + ECharts

## 功能
- LLM调用追踪SDK
- Prompt版本A/B对比
- 评测集自动执行
- bad case标注回归
- 监控看板

## 启动
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --port 8002
```
