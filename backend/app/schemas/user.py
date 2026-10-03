from beanie import PydanticObjectId
from datetime import datetime

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


class AiKeyOut(BaseModel):
    """A connected key as the student sees it — never the key itself."""
    provider: str
    last4: str
    strong_model: str
    small_model: str
    base_url: str | None = None
    added_at: datetime


class AiKeyIn(BaseModel):
    provider: str
    api_key: str = Field(min_length=8, max_length=300)
    base_url: str | None = Field(default=None, max_length=300)
    model: str | None = Field(default=None, max_length=120)


class AiKeysOut(BaseModel):
    ai_keys: list[AiKeyOut]
    message: str = ""


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
    ai_keys: list["AiKeyOut"] = []


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


UserOut.model_rebuild()
