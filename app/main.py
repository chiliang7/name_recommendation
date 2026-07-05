# -*- coding: utf-8 -*-
"""FastAPI 後端。啟動:uvicorn app.main:app --reload --port 8000
(若未安裝 fastapi/uvicorn,可改用 python3 server.py)"""
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import core

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = FastAPI(title="寶寶取名助手")


class AnalyzeReq(BaseModel):
    surname: str
    given: str
    year: int = 2026
    use_modern: bool = False


@app.post("/api/analyze")
def analyze(req: AnalyzeReq):
    try:
        return core.analyze(req.surname, req.given, req.year, req.use_modern)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/suggest-chars")
def suggest_chars(year: int = 2026, gender: str = ""):
    return core.suggest_chars(year, gender)


@app.get("/api/suggest-names")
def suggest_names(surname: str, year: int = 2026, gender: str = "", length: int = 2,
                  rarity: int = 1, luck: int = 1, max_strokes: int = 0,
                  like: str = "", dislike: str = ""):
    try:
        return core.suggest_names(surname, year, gender, length,
                                  rarity=rarity, luck=luck, max_strokes=max_strokes,
                                  like=like, dislike=dislike)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/rules")
def rules(year: int = 2026):
    return core.zodiac_rules(year)


@app.get("/")
def index():
    return FileResponse(os.path.join(ROOT, "static", "index.html"))


app.mount("/static", StaticFiles(directory=os.path.join(ROOT, "static")), name="static")
