import re

from pydantic import BaseModel, EmailStr, field_validator

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,20}$")


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not USERNAME_REGEX.match(v):
            raise ValueError(
                "El usuario debe tener entre 3 y 20 caracteres (letras, números o guion bajo)."
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        if len(v.encode("utf-8")) > 72:
            # Límite real de bcrypt (72 bytes, no caracteres — un emoji o una
            # letra con acento puede pesar varios bytes). Sin este chequeo,
            # bcrypt lanza un error interno feo y el registro responde 500
            # en vez de un mensaje claro.
            raise ValueError("La contraseña no puede tener más de 72 caracteres.")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    bfb_points: int
    preferred_language: str
    is_admin: bool = False

    class Config:
        from_attributes = True


class LanguageUpdate(BaseModel):
    preferred_language: str

    @field_validator("preferred_language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ("es", "en"):
            raise ValueError("Idioma no soportado. Usa 'es' o 'en'.")
        return v
