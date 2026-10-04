# -*- coding: utf-8 -*-
"""FastAPI 後端。啟動:uvicorn app.main:app --reload --port 8000
(若未安裝 fastapi/uvicorn,可改用 python3 server.py)"""
import os
from typing import Optional

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


class BaziReq(BaseModel):
    birth_date: str
    birth_time: Optional[str] = None
    timezone: str = "UTC+08:00"
    day_boundary: str = "midnight"


@app.post("/api/bazi")
def bazi(req: BaziReq):
    try:
        return core.analyze_bazi(req.birth_date, req.birth_time, req.timezone, req.day_boundary)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
                  limit: int = 100, rarity: int = 1, luck: int = 1,
                  max_strokes: int = 0, like: str = "", dislike: str = "",
                  exclude: str = "", strokes_operator: str = "<=",
                  strokes_basis: str = "modern", fixed_first: str = "", fixed_second: str = "",
                  zong_elements: str = "", zong_ten_gods: str = "",
                  exclude_unfavorable: bool = True, relax_zodiac: bool = False,
                  required_ten_gods: str = "", match_all_ten_gods: bool = True, relax_phonetic: bool = False):
    try:
        return core.suggest_names(surname, year, gender, length, limit=limit,
                                  rarity=rarity, luck=luck, max_strokes=max_strokes,
                                  like=like, dislike=dislike, exclude=exclude,
                                  strokes_operator=strokes_operator, strokes_basis=strokes_basis,
                                  fixed_first=fixed_first, fixed_second=fixed_second, zong_elements=zong_elements,
                                  zong_ten_gods=zong_ten_gods, exclude_unfavorable=exclude_unfavorable, relax_zodiac=relax_zodiac,
                                  required_ten_gods=required_ten_gods, match_all_ten_gods=match_all_ten_gods, relax_phonetic=relax_phonetic)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class SuggestNamesReq(BaseModel):
    surname: str
    year: int = 2026
    gender: str = ""
    length: int = 2
    limit: int = 100
    rarity: int = 1
    luck: int = 1
    max_strokes: int = 0
    strokes_operator: str = "<="
    strokes_basis: str = "modern"
    fixed_first: str = ""
    fixed_second: str = ""
    zong_elements: str = ""
    zong_ten_gods: str = ""
    exclude_unfavorable: bool = True
    relax_zodiac: bool = False
    required_ten_gods: str = ""
    match_all_ten_gods: bool = True
    relax_phonetic: bool = False
    like: str = ""
    dislike: str = ""
    exclude: str = ""  # 已看過的名字(換一批不重複),可能很長故走 POST


@app.post("/api/suggest-names")
def suggest_names_post(req: SuggestNamesReq):
    try:
        return core.suggest_names(req.surname, req.year, req.gender, req.length,
                                  limit=req.limit,
                                  rarity=req.rarity, luck=req.luck,
                                  max_strokes=req.max_strokes,
                                  like=req.like, dislike=req.dislike,
                                  exclude=req.exclude,
                                  strokes_operator=req.strokes_operator, strokes_basis=req.strokes_basis,
                                  fixed_first=req.fixed_first, fixed_second=req.fixed_second, zong_elements=req.zong_elements,
                                  zong_ten_gods=req.zong_ten_gods, exclude_unfavorable=req.exclude_unfavorable, relax_zodiac=req.relax_zodiac,
                                  required_ten_gods=req.required_ten_gods, match_all_ten_gods=req.match_all_ten_gods, relax_phonetic=req.relax_phonetic)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/rules")
def rules(year: int = 2026):
    return core.zodiac_rules(year)


@app.get("/")
def index():
    return FileResponse(os.path.join(ROOT, "static", "index.html"))


app.mount("/static", StaticFiles(directory=os.path.join(ROOT, "static")), name="static")
