from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: PydanticObjectId
    email: EmailStr
    full_name: str | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
