from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func

from server.db.database import Base


# 검토 모델
class review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    agenda = Column(String(255), nullable=False)
    rounds = Column(Integer, default=1)
    messages = Column(Text, nullable=False)  # JSON 문자열로 저장
    docs = Column(Text, nullable=True)  # JSON 문자열로 저장
    created_at = Column(DateTime(timezone=True), server_default=func.now())
