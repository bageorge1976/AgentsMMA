import contextlib
from collections.abc import Sequence

from datetime import datetime
from re import A

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import schemas
from database import (
    create_all_tables,
    get_async_session,
)
from models import Relative, Contact


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all_tables()
    yield


app = FastAPI(lifespan=lifespan)


async def pagination(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=0),
) -> tuple[int, int]:
    capped_limit = min(100, limit)
    return (skip, capped_limit)


async def get_contact_or_404(
    id: int, session: AsyncSession = Depends(get_async_session)
) -> Contact:
    select_query = (
        select(Contact).options(selectinload(Contact.relatives)).where(Contact.id == id)
    )
    result = await session.execute(select_query)
    contact = result.scalar_one_or_none()

    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return contact


@app.get("/contacts", response_model=list[schemas.ContactRead])
async def list_contacts(
    pagination: tuple[int, int] = Depends(pagination),
    session: AsyncSession = Depends(get_async_session),
) -> Sequence[Contact]:
    skip, limit = pagination
    select_query = (
        select(Contact).options(selectinload(Contact.comments)).offset(skip).limit(limit)
    )
    result = await session.execute(select_query)

    return result.scalars().all()


@app.get("/contacts/{id}", response_model=schemas.ContactRead)
async def get_contact(contact: Contact = Depends(get_contact_or_404)) -> Contact:
    return contact


@app.post(
    "/contacts", response_model=schemas.ContactRead, status_code=status.HTTP_201_CREATED
)
async def create_contact(
    contact_create: schemas.ContactCreate, session: AsyncSession = Depends(get_async_session)
) -> Contact:
    #contact = Contact(**contact_create.dict(), relatives=[])
    contact = Contact(first_name="Bogdan",
        last_name="Georgescu",
        hebrew_name= "בורגאן גאורגסקו",
        birth_date=datetime(1976,1,16),
    birth_date_day_h=14, #Hebrew date representation
    birth_date_month_h=2, #Hebrew date representation
    birth_date_year_h=5776, #Hebrew date representation
    
    phone_primary="14032829220",    
    phone_secondary="15879669220",  
    email="bageorge1976@gmail.com",
    address="805 80 Point McKay CR NW",
    city="Calgary",
    country="Canada",
    
    title="PhD",
    notes="A sample contact",
    created_at=datetime.now(),
    updated_at=datetime.now(), relatives=[])
    session.add(contact)
    await session.commit()

    return contact


@app.patch("/contacts/{id}", response_model=schemas.ContactRead)
async def update_contact(
    contact_update: schemas.ContactPartialUpdate,
    contact: Contact = Depends(get_contact_or_404),
    session: AsyncSession = Depends(get_async_session),
) -> Contact:
    contact_update_dict = contact_update.dict(exclude_unset=True)
    for key, value in contact_update_dict.items():
        setattr(contact, key, value)

    session.add(contact)
    await session.commit()

    return contact


@app.delete("/contacts/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact: Contact = Depends(get_contact_or_404),
    session: AsyncSession = Depends(get_async_session),
):
    await session.delete(contact)
    await session.commit()


@app.post(
    "/contacts/{id}/relatives",
    response_model=schemas.RelativeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_relative(
    relative_create: schemas.RelativeCreate,
    contact: Contact = Depends(get_contact_or_404),
    session: AsyncSession = Depends(get_async_session),
) -> Relative:
    relative = Relative(**relative_create.dict(), contact=contact)
    session.add(relative)
    await session.commit()

    return relative
