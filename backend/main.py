from fastapi import FastAPI
from pydantic import BaseModel
import sqlite3
from datetime import datetime

app = FastAPI(title="LLM Eval Observability")
DB = "eval.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS traces(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project TEXT, model TEXT, input TEXT, output TEXT,
        latency_ms INTEGER, tokens INTEGER, cost REAL, ts TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS prompts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, version TEXT, content TEXT, ts TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS eval_cases(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        input TEXT, expected TEXT, actual TEXT,
        score REAL, is_bad INTEGER DEFAULT 0, ts TEXT)""")
    conn.commit()
    conn.close()

init_db()

class Trace(BaseModel):
    project: str
    model: str
    input: str
    output: str
    latency_ms: int
    tokens: int
    cost: float

@app.post("/api/traces")
def save_trace(t: Trace):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO traces(project,model,input,output,latency_ms,tokens,cost,ts) VALUES(?,?,?,?,?,?,?,?)",
        (t.project, t.model, t.input, t.output, t.latency_ms, t.tokens, t.cost, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"status": "saved"}

@app.get("/api/dashboard/stats")
def stats():
    conn = sqlite3.connect(DB)
    total = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
    avg_latency = conn.execute("SELECT AVG(latency_ms) FROM traces").fetchone()[0] or 0
    total_cost = conn.execute("SELECT SUM(cost) FROM traces").fetchone()[0] or 0
    conn.close()
    return {"total_calls": total, "avg_latency_ms": round(avg_latency,1), "total_cost": round(total_cost,4)}

class PromptVer(BaseModel):
    name: str
    version: str
    content: str

@app.post("/api/prompts")
def save_prompt(p: PromptVer):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO prompts(name,version,content,ts) VALUES(?,?,?,?)",
        (p.name, p.version, p.content, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"status": "saved"}

@app.get("/api/prompts")
def list_prompts():
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT id,name,version,content FROM prompts ORDER BY id DESC").fetchall()
    conn.close()
    return [{"id":r[0],"name":r[1],"version":r[2],"content":r[3]} for r in rows]

class EvalCase(BaseModel):
    input: str
    expected: str
    actual: str = ""
    score: float = 0
    is_bad: bool = False

@app.post("/api/eval/cases")
def add_case(c: EvalCase):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO eval_cases(input,expected,actual,score,is_bad,ts) VALUES(?,?,?,?,?,?)",
        (c.input, c.expected, c.actual, c.score, 1 if c.is_bad else 0, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"status": "saved"}

@app.get("/api/eval/cases")
def list_cases():
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT id,input,expected,actual,score,is_bad FROM eval_cases ORDER BY id DESC").fetchall()
    conn.close()
    return [{"id":r[0],"input":r[1],"expected":r[2],"actual":r[3],"score":r[4],"is_bad":bool(r[5])} for r in rows]
