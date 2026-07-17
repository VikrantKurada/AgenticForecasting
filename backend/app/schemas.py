from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
    created_at: str
    updated_at: str


class ChatCreate(BaseModel):
    title: str = "New chat"


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    title: str
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    chat_id: str
    role: str
    content: str
    run_id: str | None
    created_at: str
