from sqlalchemy import Column, Integer, Text, String, UniqueConstraint, ForeignKey, REAL
from .db import Base

class Upload(Base):
    __tablename__ = "uploads"
    id = Column(Integer, primary_key=True)
    filename = Column(Text, nullable=False)
    file_hash_sha1 = Column(String(40), nullable=False, unique=True)
    uploaded_at_utc = Column(Text, nullable=False)
    notes = Column(Text)

class ReportMonth(Base):
    __tablename__ = "report_months"
    id = Column(Integer, primary_key=True)
    report_month = Column(Text, nullable=False, unique=True)  # 'YYYY-MM-01'

class Brand(Base):
    __tablename__ = "brands"
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False, unique=True)

class Chain(Base):
    __tablename__ = "chains"
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False, unique=True)

class SpinsFact(Base):
    __tablename__ = "spins_facts"
    id = Column(Integer, primary_key=True)
    report_month_id = Column(Integer, ForeignKey("report_months.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    chain_id = Column(Integer, ForeignKey("chains.id"), nullable=False)
    dollars = Column(REAL, nullable=False)
    units = Column(REAL, nullable=False)
    velocity = Column(REAL, nullable=True)

    __table_args__ = (
        UniqueConstraint("report_month_id", "brand_id", "chain_id", name="uq_fact"),
    )
