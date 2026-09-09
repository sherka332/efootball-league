from pydantic import BaseModel, Field

class TelegramAuth(BaseModel):
    init_data: str = Field(min_length=1)

class ResultIn(BaseModel):
    home_goals: int = Field(ge=0, le=99)
    away_goals: int = Field(ge=0, le=99)
    note: str | None = Field(default=None, max_length=500)

class TeamJoin(BaseModel):
    team_id: int

class SeasonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

class BanIn(BaseModel):
    banned: bool

class MessageIn(BaseModel):
    receiver_id: int
    text: str = Field(min_length=1, max_length=2000)
