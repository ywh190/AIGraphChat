from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.models import schemas
from app.services import search_service, ai_service

router = APIRouter()

@router.get("/prescriptions/{query}", response_model=List[schemas.Prescription])
def search_prescriptions(query: str, limit: int = 10, db: Session = Depends(get_db)):
    """搜索方剂"""
    query = query.strip()
    return search_service.search_prescriptions(db, query, limit)

@router.get("/herbs/{query}", response_model=List[schemas.Herb])
def search_herbs(query: str, limit: int = 10, db: Session = Depends(get_db)):
    """搜索药材"""
    query = query.strip()
    return search_service.search_herbs(db, query, limit)

@router.post("/semantic", response_model=List[schemas.Prescription])
def semantic_search(query: schemas.SearchQuery, db: Session = Depends(get_db)):
    """语义搜索"""
    trimmed_query = query.query.strip() if query.query else ""
    return search_service.semantic_search(db, trimmed_query, query.limit)

@router.get("/advanced/{query}")
def advanced_search(query: str, db: Session = Depends(get_db)):
    """高级搜索（结合关键词和语义）"""
    query = query.strip()
    return search_service.advanced_search(db, query)