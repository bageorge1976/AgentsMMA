from calendar import c
from datetime import datetime
from turtle import title
from venv import create

from sqlalchemy import DateTime, ForeignKey, Integer, Null, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Relative(Base):
    __tablename__ = "relatives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hebrew_name: Mapped[str] = mapped_column(String(100), nullable=True)
    
    birth_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, default=Null
    )
    birth_date_day_h:Mapped[int] = mapped_column(Integer, nullable=True)  # Hebrew date representation
    birth_date_month_h:Mapped[int] = mapped_column(Integer, nullable=True)  # Hebrew date representation
    birth_date_year_h:Mapped[int] = mapped_column(Integer, nullable=True)  # Hebrew date representation
    
    passing_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, default=Null
    )
    passing_date_day_h:Mapped[int] = mapped_column(Integer, nullable=True)  # Hebrew date representation
    passing_date_month_h:Mapped[int] = mapped_column(Integer, nullable=True)  # Hebrew date representation
    passing_date_year_h:Mapped[int] = mapped_column(Integer, nullable=True)  # Hebrew date representation

    relation_to_contact: Mapped[str] = mapped_column(String(100), nullable=False)


    notes: Mapped[str] = mapped_column(Text, nullable=False)

    contact: Mapped["Contact"] = relationship("Contact", back_populates="relatives")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hebrew_name: Mapped[str] = mapped_column(String(100), nullable=True)
    
    birth_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=Null
    )
    birth_date_day_h:Mapped[int] = mapped_column(Integer, nullable=True)  # Hebrew date representation
    birth_date_month_h:Mapped[int] = mapped_column(Integer, nullable=True)  # Hebrew date representation
    birth_date_year_h:Mapped[int] = mapped_column(Integer, nullable=True)  # Hebrew date representation
    
    phone_primary: Mapped[str] = mapped_column(String(20), nullable=False)
    phone_secondary: Mapped[str] = mapped_column(String(20), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)

    province: Mapped[str] = mapped_column(String(100), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    

    
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    relatives: Mapped[list[Relative]] = relationship("Relative", cascade="all, delete")
