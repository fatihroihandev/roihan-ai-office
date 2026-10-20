from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.projects.uploads import FileKind


def _strip(value: str | None) -> str | None:
    return value.strip() if isinstance(value, str) else value


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)

    _strip_name = field_validator("name", "description", mode="before")(_strip)

    @field_validator("name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v:
            raise ValueError("Nama proyek tidak boleh kosong")
        return v


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    status: Literal["active", "archived"] | None = None

    _strip_fields = field_validator("name", "description", mode="before")(_strip)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    kind: FileKind
    original_name: str
    stored_name: str
    relative_path: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
