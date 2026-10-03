from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = Field(default=None, max_length=80)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=80)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: PydanticObjectId
    email: EmailStr
    full_name: str | None = None
    is_admin: bool = False


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
