from datetime import datetime

from pydantic import BaseModel, Field


class RelativeBase(BaseModel):

    first_name: str
    last_name: str
    hebrew_name: str
    
    birth_date: datetime
    birth_date_day_h:int 
    birth_date_month_h:int
    birth_date_year_h:int
    
    passing_date: datetime
    passing_date_day_h:int
    passing_date_month_h:int
    passing_date_year_h:int

    relation_to_contact: str

    notes: str

    class Config:
        orm_mode = True
        #from_attributes=True


class RelativeCreate(RelativeBase):
    pass


class RelativeRead(RelativeBase):
    id: int
    contact_id: int


class ContactBase(BaseModel):
    first_name: str
    last_name: str
    hebrew_name: str 

    birth_date: datetime
    birth_date_day_h:int #Hebrew date representation
    birth_date_month_h:int #Hebrew date representation
    birth_date_year_h:int #Hebrew date representation
    
    phone_primary: str    
    phone_secondary: str   
    email: str
    address: str
    city: str
    country: str
    
    province: str    
    notes: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    

    class Config:
        orm_mode = True
        #from_attributes=True


class ContactPartialUpdate(BaseModel):
    
    first_name: str | None = None
    last_name: str | None = None
    hebrew_name: str | None = None 
       
    birth_date: datetime | None = None
    birth_date_day_h:int | None = None #Hebrew date representation
    birth_date_month_h:int | None = None #Hebrew date representation
    birth_date_year_h:int | None = None #Hebrew date representation
    
    phone_primary: str | None = None   
    phone_secondary: str | None = None  
    email: str | None = None
    address: str | None = None
    city: str | None = None
    province: str | None = None 
    country: str | None = None
    
       
    notes: str | None = None
    updated_at: datetime = Field(default_factory=datetime.now)



class ContactCreate(ContactBase):
    pass


class ContactRead(ContactBase):
    id: int
    relatives: list[RelativeRead]
