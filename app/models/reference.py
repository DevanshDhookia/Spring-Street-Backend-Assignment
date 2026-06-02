from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import CHAR

from .base import Base


class Region(Base):
    __tablename__ = "regions"

    country_code = Column(CHAR(2), primary_key=True)
    country_name = Column(Text, nullable=False)
    region = Column(Text, nullable=False)
    msci_class = Column(Text)


class Sector(Base):
    __tablename__ = "sectors"

    code = Column(Text, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
