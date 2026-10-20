"""Orchestration for the virtual try-on proof of concept.

The YouCam API is asynchronous and takes a while, so the HTTP route cannot
answer with a finished image. This module owns the two halves that split:

* a **job** - a small record of where the request currently is, so the browser
  can poll our own endpoint and see real progress instead of a spinner;
* the **runner** - the coroutine that walks the documented four-step flow:
  upload source image, upload reference image, submit `cloth-v4`, poll it.

Storage is a bounded in-process dict. That is deliberate for this phase: nothing
is persisted, no database is introduced, and a restart simply forgets the job.
The known consequence - the 2-hour result URL cannot be recovered after a
restart - is listed in the README as a blocker rather than papered over here.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Literal

from app.core.config import Settings, get_settings
from app.core.image_validation import ValidatedImage, build_file_name
from app.services.youcam.errors import YouCamTaskError
from app.services.youcam.schemas import GarmentCategory, MultiPersonFilter, TaskStatus
from app.services.youcam.service import YouCamService, get_youcam_service

logger = logging.getLogger(__name__)

TryOnPhase = Literal[
    "queued",
    "uploading_source_image",
    "uploading_reference_image",
    "submitting_task",
    "polling_task",
    "completed",
    "failed",
]

TERMINAL_PHASES: frozenset[str] = frozenset({"completed", "failed"})

#: Order used by the UI to render the step list.
PHASE_SEQUENCE: tuple[TryOnPhase, ...] = (
    "queued",
    "uploading_source_image",
    "uploading_reference_image",
    "submitting_task",
    "polling_task",
    "completed",
)

#: The result URL is a presigned object-store link documented as valid for
#: 2 hours. Surfaced so the UI can say so instead of implying permanence.
RESULT_URL_TTL_HOURS = 2


@dataclass
class TryOnJob:
    """Mutable progress record for one try-on request.

    Only ever mutated from the event loop thread that runs the job coroutine, so
    no lock is needed; readers are the poll endpoint on the same loop.
    """

    job_id: str
    garment_category: GarmentCategory
    filter_multi_person: MultiPersonFilter
    phase: TryOnPhase = "queued"
    #: Set by the product try-on route so the UI can label a job. The
    #: integration proof-of-concept route leaves these unset.
    product_id: str | None = None
    product_name: str | None = None
    youcam_task_id: str | None = None
    youcam_task_status: str | None = None
    result_url: str | None = None
    error: str | None = None
    error_code: str | None = None
    created_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.monotonic)

    def _touch(self) -> None:
        self.updated_at = time.monotonic()

    def advance(self, phase: TryOnPhase) -> None:
        self.phase = phase
        self._touch()

    def observe_status(self, status: TaskStatus) -> None:
        """Record the vendor's own task status so the UI can show it verbatim."""
        self.youcam_task_status = status
        self._touch()

    def finish(self, *, task_id: str, result_url: str) -> None:
        self.youcam_task_id = task_id
        self.result_url = result_url
        self.phase = "completed"
        self._touch()

    def fail(self, message: str, *, error_code: str | None = None) -> None:
        self.error = message
        self.error_code = error_code
        self.phase = "failed"
        self._touch()

    @property
    def is_terminal(self) -> bool:
        return self.phase in TERMINAL_PHASES


class TryOnJobStore:
    """Bounded, TTL-scoped, in-memory job table.

    Not a database and not a cache: it exists so a browser can ask "what phase
    is my request in?". Entries are dropped once they are older than the TTL so
    a long-running dev server cannot grow without bound.
    """

    def __init__(self, *, ttl_seconds: float = 900.0, max_jobs: int = 50) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_jobs = max_jobs
        self._jobs: dict[str, TryOnJob] = {}

    def create(
        self,
        *,
        garment_category: GarmentCategory,
        filter_multi_person: MultiPersonFilter,
    ) -> TryOnJob:
        self._evict()
        job = TryOnJob(
            job_id=secrets.token_urlsafe(12),
            garment_category=garment_category,
            filter_multi_person=filter_multi_person,
        )
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> TryOnJob | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if self._is_expired(job):
            del self._jobs[job_id]
            return None
        return job

    def _is_expired(self, job: TryOnJob) -> bool:
        return (time.monotonic() - job.updated_at) > self._ttl_seconds

    def _evict(self) -> None:
        for job_id, job in list(self._jobs.items()):
            if self._is_expired(job):
                del self._jobs[job_id]
        overflow = len(self._jobs) - self._max_jobs
        if overflow > 0:
            oldest = sorted(self._jobs.values(), key=lambda job: job.created_at)
            for job in oldest[:overflow]:
                del self._jobs[job.job_id]

    def clear(self) -> None:
        self._jobs.clear()


@dataclass
class TryOnReference:
    """How the reference garment reaches YouCam.

    Mirrors the three ways a catalogue can describe a garment and the three the
    V4.0 task accepts: an image already in YouCam storage (`file_id`), one at a
    publicly reachable `url` the vendor fetches itself, or bundled `image` bytes
    we push through the File API first. Exactly one field is meaningfully set.
    """

    file_id: str | None = None
    url: str | None = None
    image: ValidatedImage | None = None


class TryOnRunner:
    """Runs one try-on job to completion against the YouCam service."""

    def __init__(self, service: YouCamService) -> None:
        self._service = service

    async def run(
        self,
        job: TryOnJob,
        *,
        source: ValidatedImage,
        reference: TryOnReference,
    ) -> TryOnJob:
        """Walk the documented flow, mutating `job` as it goes.

        Any failure is recorded on the job rather than raised: by the time this
        runs the route has already answered with 202, so an exception here has
        nowhere to go except the job's error fields.
        """
        job.advance("uploading_source_image")
        source_file = await self._service.upload_image(
            source.data,
            file_name=build_file_name("source", source.content_type),
            content_type=source.content_type,
        )

        job.advance("uploading_reference_image")
        # The reference reaches the vendor by whichever transport the catalogue
        # used: an id we already own, a public URL it can fetch, or bytes we push
        # through the File API now.
        reference_file_id = reference.file_id
        reference_url = reference.url
        if reference_file_id is None and reference_url is None:
            if reference.image is None:
                raise YouCamTaskError(
                    "The reference garment has no image that can be sent to YouCam."
                )
            reference_file = await self._service.upload_image(
                reference.image.data,
                file_name=build_file_name("reference", reference.image.content_type),
                content_type=reference.image.content_type,
            )
            reference_file_id = reference_file.file_id

        job.advance("submitting_task")
        task_id = await self._service.submit_try_on_garment(
            source_file_id=source_file.file_id,
            reference_file_id=reference_file_id,
            reference_url=reference_url,
            garment_category=job.garment_category,
            filter_multi_person=job.filter_multi_person,
        )
        job.youcam_task_id = task_id
        job.youcam_task_status = "running"
        job.advance("polling_task")

        def _observe(status: TaskStatus) -> None:
            job.observe_status(status)

        result = await self._service.await_try_on_garment(task_id, on_status=_observe)
        job.finish(task_id=result.task_id, result_url=result.result_url)
        logger.info("Try-on job %s completed (task %s)", job.job_id, result.task_id)
        return job


async def execute_try_on_job(
    job: TryOnJob,
    *,
    source: ValidatedImage,
    reference: TryOnReference,
    service: YouCamService | None = None,
) -> None:
    """Run `job` and record any failure on it instead of propagating it."""
    try:
        runner = TryOnRunner(service or get_youcam_service())
        await runner.run(job, source=source, reference=reference)
    except YouCamTaskError as exc:
        logger.info("Try-on job %s failed: %s", job.job_id, exc.message)
        job.fail(exc.message, error_code=exc.error_code)
    except asyncio.CancelledError:
        job.fail("The try-on request was cancelled before YouCam finished.")
        raise
    except Exception as exc:  # noqa: BLE001 - surfaced through the job, never crashes the server
        logger.exception("Try-on job %s failed unexpectedly", job.job_id)
        job.fail(str(exc) or exc.__class__.__name__)


_store: TryOnJobStore | None = None
_running: set[asyncio.Task[None]] = set()


def get_tryon_job_store(settings: Settings | None = None) -> TryOnJobStore:
    """Process-wide job table used as a FastAPI dependency."""
    global _store
    if _store is None:
        resolved = settings or get_settings()
        _store = TryOnJobStore(ttl_seconds=resolved.youcam_tryon_job_ttl_seconds)
    return _store


def start_try_on_job(
    job: TryOnJob,
    *,
    source: ValidatedImage,
    reference: TryOnReference,
    service: YouCamService | None = None,
) -> None:
    """Schedule the job and retain a strong reference to the task.

    The event loop only keeps weak references to tasks, so the set is what stops
    the runner from being garbage collected mid-flight.
    """
    task = asyncio.create_task(
        execute_try_on_job(job, source=source, reference=reference, service=service)
    )
    _running.add(task)
    task.add_done_callback(_running.discard)


async def reset_tryon_jobs() -> None:
    """Cancel in-flight jobs and forget the table (shutdown and tests)."""
    tasks = list(_running)
    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task
    _running.clear()
    global _store
    if _store is not None:
        _store.clear()
        _store = None