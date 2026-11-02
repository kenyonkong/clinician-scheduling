import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from main import SCHEDULES, app


async def request(method: str, path: str, **kwargs):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def schedule_payload(
    clinician: str = "Dr. Smith",
    start_time: str = "2026-11-02T09:00:00",
    duration: int = 30,
) -> dict[str, str | int]:
    return {
        "patient_name": "Alex Morgan",
        "clinician": clinician,
        "start_time": start_time,
        "duration": duration,
    }


def post_schedule(payload: dict):
    return asyncio.run(request("POST", "/api/schedules", json=payload))


def patch_schedule(schedule_id: int, payload: dict):
    return asyncio.run(request("PATCH", f"/api/schedules/{schedule_id}", json=payload))


@pytest.fixture(autouse=True)
def clear_schedules():
    SCHEDULES.clear()
    yield
    SCHEDULES.clear()


def test_health() -> None:
    response = asyncio.run(request("GET", "/api/health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_only_supported_clinicians_are_returned() -> None:
    response = asyncio.run(request("GET", "/api/clinicians"))

    assert response.status_code == 200
    assert response.json() == ["Dr. Smith", "Dr. Lee"]


def test_create_and_list_schedule_with_duration() -> None:
    payload = schedule_payload(duration=60)

    created = post_schedule(payload)
    listed = asyncio.run(request("GET", "/api/schedules"))

    assert created.status_code == 201
    assert created.json() == {"id": created.json()["id"], **payload}
    assert listed.status_code == 200
    assert listed.json() == [created.json()]


def test_schedules_are_listed_in_chronological_order() -> None:
    for start_time in (
        "2026-11-02T11:00:00",
        "2026-11-02T09:00:00",
        "2026-11-02T10:00:00",
    ):
        assert post_schedule(schedule_payload(start_time=start_time)).status_code == 201

    response = asyncio.run(request("GET", "/api/schedules"))

    assert response.status_code == 200
    assert [schedule["start_time"] for schedule in response.json()] == [
        "2026-11-02T09:00:00",
        "2026-11-02T10:00:00",
        "2026-11-02T11:00:00",
    ]


def test_all_fields_are_required() -> None:
    response = post_schedule({})

    assert response.status_code == 422


def test_end_time_is_not_part_of_the_schedule_representation() -> None:
    payload = schedule_payload()
    payload["end_time"] = "2026-11-02T09:30:00"

    response = post_schedule(payload)

    assert response.status_code == 422


@pytest.mark.parametrize("duration", [15, 45, 90])
def test_rejects_unsupported_duration(duration: int) -> None:
    response = post_schedule(schedule_payload(duration=duration))

    assert response.status_code == 422


@pytest.mark.parametrize("minute", [0, 15, 30, 45])
def test_allows_quarter_hour_start_times(minute: int) -> None:
    start_time = f"2026-11-02T09:{minute:02d}:00"

    response = post_schedule(schedule_payload(start_time=start_time))

    assert response.status_code == 201


@pytest.mark.parametrize(
    "start_time",
    [
        "2026-11-02T09:05:00",
        "2026-11-02T09:20:00",
        "2026-11-02T09:30:01",
    ],
)
def test_rejects_non_quarter_hour_start_times(start_time: str) -> None:
    response = post_schedule(schedule_payload(start_time=start_time))

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("start_time", "duration"),
    [
        ("2026-11-02T08:30:00", 60),
        ("2026-11-02T09:00:00", 30),
        ("2026-11-02T09:15:00", 30),
        ("2026-11-02T09:30:00", 60),
        ("2026-11-02T09:45:00", 30),
    ],
)
def test_rejects_same_doctor_overlap(start_time: str, duration: int) -> None:
    assert post_schedule(
        schedule_payload(start_time="2026-11-02T09:00:00", duration=60)
    ).status_code == 201

    response = post_schedule(
        schedule_payload(start_time=start_time, duration=duration)
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Time is scheduled with another patient"
    }


@pytest.mark.parametrize(
    ("start_time", "duration"),
    [
        ("2026-11-02T08:30:00", 30),
        ("2026-11-02T10:00:00", 30),
    ],
)
def test_allows_adjacent_same_doctor_appointments(
    start_time: str, duration: int
) -> None:
    assert post_schedule(
        schedule_payload(start_time="2026-11-02T09:00:00", duration=60)
    ).status_code == 201

    response = post_schedule(
        schedule_payload(start_time=start_time, duration=duration)
    )

    assert response.status_code == 201


def test_allows_simultaneous_appointments_for_different_doctors() -> None:
    assert post_schedule(
        schedule_payload(
            clinician="Dr. Smith",
            start_time="2026-11-02T09:00:00",
            duration=60,
        )
    ).status_code == 201

    response = post_schedule(
        schedule_payload(
            clinician="Dr. Lee",
            start_time="2026-11-02T09:00:00",
            duration=60,
        )
    )

    assert response.status_code == 201


def test_rejects_unknown_clinician() -> None:
    response = post_schedule(schedule_payload(clinician="Dr. Unknown"))

    assert response.status_code == 400
    assert response.json() == {"detail": "Unknown clinician"}


def test_cancel_schedule_removes_it_from_memory() -> None:
    created = post_schedule(schedule_payload()).json()

    deleted = asyncio.run(request("DELETE", f"/api/schedules/{created['id']}"))
    listed = asyncio.run(request("GET", "/api/schedules"))

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert listed.json() == []


def test_cancel_unknown_schedule_returns_not_found() -> None:
    response = asyncio.run(request("DELETE", "/api/schedules/999999"))

    assert response.status_code == 404
    assert response.json() == {"detail": "Schedule not found"}


def test_canceling_schedule_frees_its_time_slot() -> None:
    payload = schedule_payload(duration=60)
    created = post_schedule(payload).json()

    deleted = asyncio.run(request("DELETE", f"/api/schedules/{created['id']}"))
    replacement = post_schedule(payload)

    assert deleted.status_code == 204
    assert replacement.status_code == 201


def test_reschedule_updates_start_clinician_and_duration() -> None:
    created = post_schedule(schedule_payload()).json()

    response = patch_schedule(
        created["id"],
        {
            "clinician": "Dr. Lee",
            "start_time": "2026-11-02T10:15:00",
            "duration": 60,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        **created,
        "clinician": "Dr. Lee",
        "start_time": "2026-11-02T10:15:00",
        "duration": 60,
    }


def test_reschedule_supports_partial_updates_without_self_overlap() -> None:
    created = post_schedule(schedule_payload()).json()

    response = patch_schedule(created["id"], {"duration": 60})

    assert response.status_code == 200
    assert response.json()["duration"] == 60


def test_reschedule_rejects_overlap_and_keeps_original_schedule() -> None:
    first = post_schedule(
        schedule_payload(start_time="2026-11-02T09:00:00", duration=60)
    ).json()
    second = post_schedule(
        schedule_payload(start_time="2026-11-02T10:00:00", duration=30)
    ).json()

    response = patch_schedule(second["id"], {"start_time": "2026-11-02T09:30:00"})
    listed = asyncio.run(request("GET", "/api/schedules")).json()

    assert response.status_code == 409
    assert response.json() == {"detail": "Time is scheduled with another patient"}
    assert first in listed
    assert second in listed


def test_reschedule_rejects_overlap_after_changing_clinician() -> None:
    smith = post_schedule(schedule_payload(clinician="Dr. Smith")).json()
    post_schedule(schedule_payload(clinician="Dr. Lee"))

    response = patch_schedule(smith["id"], {"clinician": "Dr. Lee"})

    assert response.status_code == 409


def test_reschedule_rejects_empty_or_unsupported_updates() -> None:
    created = post_schedule(schedule_payload()).json()

    assert patch_schedule(created["id"], {}).status_code == 422
    assert patch_schedule(created["id"], {"patient_name": "New Name"}).status_code == 422


def test_reschedule_unknown_schedule_returns_not_found() -> None:
    response = patch_schedule(999999, {"duration": 60})

    assert response.status_code == 404
    assert response.json() == {"detail": "Schedule not found"}

