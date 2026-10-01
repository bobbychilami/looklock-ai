"""Typed models for the YouCam API responses we consume.

Every shape here is transcribed from the official OpenAPI descriptions at
https://docs.makeupar.com (see README "YouCam integration notes"). Models are
deliberately permissive (extra fields allowed, most values typed loosely)
because the vendor evolves payloads between feature versions. We parse only
what the product loop needs and pass the rest through untouched.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TaskStatus = Literal["running", "success", "error"]

# --- AI Clothes Virtual Try-On v4.0 enums ---------------------------------- #
# Transcribed verbatim from `RunClothV4Task` in the published OpenAPI
# (https://docs.makeupar.com/_bundle/reference/ai_clothes.json).
GarmentCategory = Literal["full_body", "lower_body", "upper_body", "shoes", "auto", "outer"]
MultiPersonFilter = Literal["off", "normal", "strict"]


class YouCamEnvelope(BaseModel):
    """Common envelope: every documented response carries `status`."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    status: int | None = None


# --------------------------------------------------------------------------- #
# File API  --  POST /s2s/v2.0/file
# --------------------------------------------------------------------------- #


class FileUploadTicket(BaseModel):
    """One presigned upload destination returned by the File API.

    Header values are coerced to strings because the published example mixes
    types (`"Content-Length": 50000`).
    """

    model_config = ConfigDict(extra="allow")

    url: str
    method: str = "PUT"
    headers: dict[str, Any] = Field(default_factory=dict)

    def header_strings(self) -> dict[str, str]:
        return {str(key): str(value) for key, value in self.headers.items()}


class FileDescriptor(BaseModel):
    """One file entry: its `file_id` plus the ticket used to upload the bytes.

    `requests[].headers` is typed loosely because the published example mixes
    strings and integers (`"Content-Length": 50000`). Values are stringified on
    the way out to the storage host.
    """

    model_config = ConfigDict(extra="allow")

    content_type: str | None = None
    file_name: str | None = None
    file_id: str | None = None
    requests: list[FileUploadTicket] = Field(default_factory=list)


class FileUploadEnvelope(YouCamEnvelope):
    """The documented `data` object of `POST /s2s/v2.0/file`."""

    files: list[FileDescriptor] = Field(default_factory=list)


class FileCreateResponse(YouCamEnvelope):
    """Response of `POST /s2s/v2.0/file`.

    The published OpenAPI declares `data: null` alongside a `$ref`, which leaves
    the nesting ambiguous: the `curl` samples show descriptors under
    `data.files`, while `BasicFileResponse` describes a top-level `files` array.
    Both are accepted and normalised through :attr:`file`.
    """

    data: FileUploadEnvelope | None = None
    files: list[FileDescriptor] = Field(default_factory=list)

    @property
    def file(self) -> FileDescriptor | None:
        if self.data is not None and self.data.files:
            return self.data.files[0]
        return self.files[0] if self.files else None


# --------------------------------------------------------------------------- #
# Task submission  --  POST /s2s/v2.0/task/{feature}
# --------------------------------------------------------------------------- #


class ClothV4TaskRequest(BaseModel):
    """Body of `POST /s2s/v2.0/task/cloth-v4`.

    The published schema `RunClothV4Task` is an `allOf` of an `anyOf` of four
    variants (src by id/url x ref by id/url) plus optional properties. The
    validator below enforces the same "exactly one of each pair" rule, so an
    impossible combination fails here instead of coming back as a confusing
    `InvalidParameters` from the vendor.

    `garment_category` is required by every V4 variant. `template_id` exists only
    in the V2.0 schema (`RunClothsTaskV2`) and is deliberately not modelled here:
    on V4.0 a reference garment is mandatory.

    Unknown fields are rejected so a typo cannot be silently dropped by a vendor
    that ignores extras.
    """

    model_config = ConfigDict(extra="forbid")

    src_file_id: str | None = None
    src_file_url: str | None = None
    ref_file_id: str | None = None
    ref_file_url: str | None = None

    garment_category: GarmentCategory = "auto"
    filter_multi_person: MultiPersonFilter = "off"
    change_shoes: bool = True

    @model_validator(mode="after")
    def _exactly_one_source_and_one_reference(self) -> ClothV4TaskRequest:
        src = [bool(self.src_file_id), bool(self.src_file_url)]
        ref = [bool(self.ref_file_id), bool(self.ref_file_url)]
        if sum(src) != 1:
            raise ValueError("Provide exactly one of src_file_id or src_file_url.")
        if sum(ref) != 1:
            raise ValueError("Provide exactly one of ref_file_id or ref_file_url.")
        return self


class RunTaskResponse(YouCamEnvelope):
    data: dict[str, Any] | None = None

    @property
    def task_id(self) -> str | None:
        if not self.data:
            return None
        task_id = self.data.get("task_id")
        return str(task_id) if task_id else None


# --------------------------------------------------------------------------- #
# Task status  --  GET /s2s/v2.0/task/{feature}/{task_id}
# --------------------------------------------------------------------------- #


class SkinAnalysisScore(BaseModel):
    """One concern score.

    Per-action fields differ: `hd_pore` carries `region`, other HD/SD actions do
    not always. Keep everything optional and retain the raw payload.
    """

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    region: str | None = None
    raw_score: float | None = None
    ui_score: int | None = None
    score: float | None = None
    mask_urls: list[str] = Field(default_factory=list)


class TaskResultPayload(BaseModel):
    """`data.results`.

    Image-producing features return `url` (valid 2 hours). Skin analysis returns
    `url` only for `format=zip`, or an `output` list when `format=json`.
    """

    model_config = ConfigDict(extra="allow")

    url: str | None = None
    output: list[SkinAnalysisScore] = Field(default_factory=list)
    color: dict[str, Any] | None = None
    face_quality: dict[str, Any] | None = None


class TaskStatusData(BaseModel):
    task_status: TaskStatus | None = None
    error: str | None = None
    error_message: str | None = None
    results: TaskResultPayload | None = None


class TaskStatusResponse(YouCamEnvelope):
    data: TaskStatusData | None = None


class YouCamErrorPayload(YouCamEnvelope):
    """Documented 400/401/429 bodies."""

    error: str | None = None
    error_code: str | None = None
