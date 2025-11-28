from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from server.db.database import get_db
from server.db.models import review as FinancialAnalysisModel  
from server.db.schemas import ReviewSchema as FinancialAnalysisSchema, ReviewCreate as FinancialAnalysisCreate

router = APIRouter(prefix="/api/v1", tags=["financeReview"])

# 기존과 동일한 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 목록 조회
@router.get("/reviews/", response_model=List[FinancialAnalysisSchema])
def read_financial_analyses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    try:
        logger.info(f"재무분석 목록 조회 요청: skip={skip}, limit={limit}")
        analyses = db.query(FinancialAnalysisModel).offset(skip).limit(limit).all()
        logger.info(f"조회된 재무분석 수: {len(analyses)}")
        
        # 기존과 동일한 방식으로 로깅
        for analysis in analyses:
            logger.info(f"분석 ID: {analysis.id}, 주제: {getattr(analysis, 'agenda', 'N/A')}")
            
        return analyses
    except Exception as e:
        logger.error(f"재무분석 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"재무분석 목록 조회 실패: {str(e)}")



# 생성
@router.post("/reviews/", response_model=FinancialAnalysisSchema)
def create_financial_analysis(analysis: FinancialAnalysisCreate, db: Session = Depends(get_db)):
    try:
        logger.info(f"재무분석 생성 요청: {analysis.model_dump()}")
        db_analysis = FinancialAnalysisModel(**analysis.model_dump())
        db.add(db_analysis)
        db.commit()
        db.refresh(db_analysis)
        logger.info(f"재무분석 생성 완료: ID={db_analysis.id}")
        return db_analysis
    except Exception as e:
        logger.error(f"재무분석 생성 실패: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"재무분석 생성 실패: {str(e)}")


# 재무분석 조회 (기존 스타일 유지)
@router.get("/reviews/{analysis_id}", response_model=FinancialAnalysisSchema)
def read_financial_analysis(analysis_id: int, db: Session = Depends(get_db)):
    try:
        logger.info(f"재무분석 조회 요청: ID={analysis_id}")
        db_analysis = db.query(FinancialAnalysisModel).filter(FinancialAnalysisModel.id == analysis_id).first()
        if db_analysis is None:
            logger.warning(f"재무분석을 찾을 수 없음: ID={analysis_id}")
            raise HTTPException(status_code=404, detail="Financial analysis not found")
        logger.info(f"재무분석 조회 성공: ID={analysis_id}")
        return db_analysis
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"재무분석 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"재무분석 조회 실패: {str(e)}")


# 재무분석 삭제 (기존 스타일 유지)
@router.delete("/reviews/{analysis_id}")
def delete_financial_analysis(analysis_id: int, db: Session = Depends(get_db)):
    try:
        logger.info(f"재무분석 삭제 요청: ID={analysis_id}")
        db_analysis = db.query(FinancialAnalysisModel).filter(FinancialAnalysisModel.id == analysis_id).first()
        if db_analysis is None:
            logger.warning(f"삭제할 재무분석을 찾을 수 없음: ID={analysis_id}")
            raise HTTPException(status_code=404, detail="Financial analysis not found")

        db.delete(db_analysis)
        db.commit()
        logger.info(f"재무분석 삭제 완료: ID={analysis_id}")
        return {"detail": "Financial analysis successfully deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"재무분석 삭제 실패: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"재무분석 삭제 실패: {str(e)}")

