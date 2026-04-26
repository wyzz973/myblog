from pydantic import BaseModel


class SitePayload(BaseModel):
    handle: str
    name: str
    name_en: str
    role: str
    tagline: str
    bio: str
    location: str
    email: str
    github: str
    pronouns: str | None = None
    uptime: str
    posts: int
    words: int
    commits52w: int
    footer_note: str
    default_theme: str
    accent_color: str
    accent2_color: str
    violet_color: str
    danger_color: str
    typing_line: str
    stack_chips: list[str]


class ProfilePayload(BaseModel):
    name: str
    name_en: str
    role: str
    bio: str
    location: str
    pronouns: str | None
    avatar_path: str | None
    typing_line: str
    stack_chips: list[str]
