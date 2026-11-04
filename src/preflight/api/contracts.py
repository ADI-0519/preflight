"""HTTP contracts contain upload IDs and URLs, never server filesystem paths."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from preflight.schema import NOTICE, Screening

Identifier = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
Text = Annotated[str, Field(max_length=4000)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartScreening(Input):
    upload_id: Identifier
    align: bool = False


class Scene(Input):
    upload_id: Identifier
    on_screen_text: tuple[Text, ...] = Field(default=(), max_length=20)
    voiceover: Text = ""
    duration_seconds: float = Field(default=4, gt=0, le=60, allow_inf_nan=False)


class StartFix(Input):
    screening_id: Identifier
    format: Literal["image", "video"]
    scenes: tuple[Scene, ...] = Field(min_length=1, max_length=10)
    rounds: int = Field(default=3, ge=0, le=3)
    align: bool = False

    @model_validator(mode="after")
    def one_image_scene(self):
        if self.format == "image" and len(self.scenes) != 1:
            raise ValueError("an image draft has exactly one scene")
        return self


class Approval(Input):
    by: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    note: Annotated[str, Field(max_length=2000)] = ""


class SignIn(Input):
    id_token: Annotated[str, Field(min_length=1, max_length=8192)]


class Code(Input):
    code: Annotated[str, Field(pattern=r"^[0-9]{6}$")]


class JobView(Input):
    job_id: Identifier
    kind: Literal["screening", "fix"]
    status: Literal["queued", "running", "completed", "incomplete", "failed"]
    notice: Literal[NOTICE] = NOTICE


class UploadView(Input):
    upload_id: Identifier
    media_type: str
    bytes: int
    expires_at: float
    notice: Literal[NOTICE] = NOTICE


class SceneView(Input):
    still_url: str
    on_screen_text: tuple[str, ...]
    voiceover: str
    duration_seconds: float


class DraftView(Input):
    format: Literal["image", "video"]
    scenes: tuple[SceneView, ...]


class HumanDecision(Input):
    event: Literal["approved"]
    by: str
    at: AwareDatetime
    screening_id: str
    note: str
    public_demo: bool = False


class ApprovalView(Input):
    decision: HumanDecision
    notice: Literal[NOTICE] = NOTICE


class FixView(Input):
    state: Literal["awaiting_approval", "needs_person"]
    draft: DraftView
    open: list[dict]
    screening: Screening
    decision: HumanDecision | None = None
    notice: Literal[NOTICE] = NOTICE
