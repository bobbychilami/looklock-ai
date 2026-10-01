"""Parsing tests for the vendored YouCam response shapes.

Fixtures are transcribed from the official examples at
https://docs.makeupar.com so a payload change shows up as a test failure.
"""

from __future__ import annotations

from app.services.youcam.schemas import (
    FileCreateResponse,
    RunTaskResponse,
    TaskStatusResponse,
)

FILE_CREATE_PAYLOAD = {
    "status": 200,
    "data": {
        "files": [
            {
                "content_type": "image/jpg",
                "file_name": "my-selfie.jpg",
                "file_id": "U8aqJbsXGT537jtGnEDFHqxdDXqh8+oTF/cSkLimzuvVwMP+Jb1XbjPsf7ZgUgLY",
                "requests": [
                    {
                        "headers": {"Content-Type": "image/jpg", "Content-Length": 50000},
                        "url": "https://example.com/presigned-upload-url",
                        "method": "PUT",
                    }
                ],
            }
        ]
    },
}

RUN_TASK_PAYLOAD = {
    "status": 200,
    "data": {"task_id": "grH0CvsgXuAIHLUzD0V1Ol34hoet3R1tvdbtiVHrDb6_UqCLKIejAIajwxrhOAfe"},
}

SKIN_ANALYSIS_RUNNING = {
    "status": 200,
    "data": {"task_status": "running"},
}

SKIN_ANALYSIS_SUCCESS = {
    "status": 200,
    "data": {
        "task_status": "success",
        "results": {
            "output": [
                {
                    "type": "hd_texture",
                    "region": "whole",
                    "raw_score": 98.5,
                    "ui_score": 97,
                    "score": 97.66,
                },
                {"type": "hd_skin_type", "region": "T-zone", "ui_score": 40},
            ]
        },
    },
}

SKIN_ANALYSIS_ERROR = {
    "status": 200,
    "data": {
        "task_status": "error",
        "error": "error_no_face",
        "error_message": "No face detected",
    },
}

COLOR_TONE_SUCCESS = {
    "status": 200,
    "data": {
        "task_status": "success",
        "results": {
            "color": {
                "eye_color": "#293F9B",
                "eye_color_name": "Blue",
                "lip_color": "#D23245",
                "eyebrow_color": "#5B2B31",
                "skin_color": "#b9947c",
                "hair_color": "#a0a0a0",
                "hair_color_name": "Auburn",
            }
        },
    },
}

CLOTH_V4_SUCCESS = {
    "status": 200,
    "data": {
        "task_status": "success",
        "results": {"url": "https://example.com/sample-result-url"},
    },
}


def test_file_create_resolves_descriptor_from_data() -> None:
    parsed = FileCreateResponse.model_validate(FILE_CREATE_PAYLOAD)

    descriptor = parsed.file
    assert descriptor is not None
    assert descriptor.file_id is not None
    assert descriptor.requests[0].method == "PUT"
    assert descriptor.requests[0].header_strings()["Content-Type"] == "image/jpg"
    assert descriptor.requests[0].header_strings()["Content-Length"] == "50000"


def test_file_create_accepts_top_level_files_array() -> None:
    payload = {"status": 200, "files": FILE_CREATE_PAYLOAD["data"]["files"]}
    parsed = FileCreateResponse.model_validate(payload)

    assert parsed.file is not None
    assert parsed.file.file_id is not None


def test_run_task_exposes_task_id() -> None:
    parsed = RunTaskResponse.model_validate(RUN_TASK_PAYLOAD)

    assert parsed.task_id == RUN_TASK_PAYLOAD["data"]["task_id"]


def test_status_running_has_no_results() -> None:
    parsed = TaskStatusResponse.model_validate(SKIN_ANALYSIS_RUNNING)

    assert parsed.data is not None
    assert parsed.data.task_status == "running"
    assert parsed.data.results is None


def test_status_success_exposes_inline_scores() -> None:
    parsed = TaskStatusResponse.model_validate(SKIN_ANALYSIS_SUCCESS)

    assert parsed.data is not None
    assert parsed.data.task_status == "success"
    assert parsed.data.results is not None
    assert [entry.type for entry in parsed.data.results.output] == ["hd_texture", "hd_skin_type"]


def test_status_error_carries_engine_code() -> None:
    parsed = TaskStatusResponse.model_validate(SKIN_ANALYSIS_ERROR)

    assert parsed.data is not None
    assert parsed.data.task_status == "error"
    assert parsed.data.error == "error_no_face"
    assert parsed.data.error_message == "No face detected"


def test_color_tone_result_shape() -> None:
    parsed = TaskStatusResponse.model_validate(COLOR_TONE_SUCCESS)

    assert parsed.data is not None and parsed.data.results is not None
    color = parsed.data.results.color
    assert color is not None
    assert color["skin_color"] == "#b9947c"
    assert color["eye_color_name"] == "Blue"


def test_cloth_v4_result_carries_download_url() -> None:
    parsed = TaskStatusResponse.model_validate(CLOTH_V4_SUCCESS)

    assert parsed.data is not None and parsed.data.results is not None
    assert parsed.data.results.url == "https://example.com/sample-result-url"


def test_unknown_fields_are_tolerated() -> None:
    payload = {"status": 200, "data": {"task_status": "success", "brand_new_field": [1, 2]}}
    parsed = TaskStatusResponse.model_validate(payload)

    assert parsed.data is not None
    assert parsed.data.task_status == "success"
