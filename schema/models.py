from dataclasses import dataclass
from pydantic import BaseModel
from typing import Literal, Optional

@dataclass
class ForeignKey:
    column:str
    ref_table:str
    ref_column:str

@dataclass
class Column:
    name:str
    datatype:str

@dataclass
class TableSchema:
    name:str
    columns:list[Column]
    primary_keys:list[str]
    foreign_keys:list[ForeignKey]

class ChatRequest(BaseModel):
    user_message: str
    session_id: Optional[str] = None
    response_mode: Literal["answer", "chart", "both"] = "both"


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    gemini_api_key: Optional[str] = None
    pinecone_api_key: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UpdateKeysRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    pinecone_api_key: Optional[str] = None


# ── Connection Management Models ──────────────────────────────────────────────

class AddConnectionRequest(BaseModel):
    """Add a new named database connection to a session."""
    name: str                              # user-friendly alias, e.g. "prod_analytics"
    connection_string: str                 # SQLAlchemy-style URL
    db_dialect: str = "PostgreSQL"         # PostgreSQL, MySQL, etc.
    session_id: Optional[str] = None


class SwitchConnectionRequest(BaseModel):
    """Switch the active connection for a session."""
    name: str                              # alias of the connection to activate
    session_id: str


class RemoveConnectionRequest(BaseModel):
    """Remove a saved connection from a session."""
    name: str
    session_id: str
