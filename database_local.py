from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models import Base, Contact

DATABASE_URL = "sqlite+aiosqlite:///GeneratedTests.db"
engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def create_all_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# MODIFIED FUNCTION TO RETURN EXPLICIT ID
async def save_contact_to_db(contact_data: dict) -> tuple[str, int]:
    """Saves a contact record to the database and returns a message and the new record ID."""
    async with async_session_maker() as session:
        # Create a new Contact instance from the dictionary data
        new_contact = Contact(**contact_data)
        
        # Add the new contact
        session.add(new_contact)
        # Commit the transaction to save the record and populate the ID
        await session.commit()
        
        # Refresh the instance to ensure the auto-generated ID is available
        await session.refresh(new_contact)
        
        # Return a message and the ID
        return f"Contact record for {new_contact.first_name} {new_contact.last_name} successfully saved.", new_contact.id