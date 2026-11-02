from datetime import datetime, timedelta
from itertools import count
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

app = FastAPI()

CLINICIANS = ["Dr. Smith", "Dr. Lee"]


class ScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_name: str
    clinician: str
    start_time: datetime
    duration: Literal[30, 60]

    @field_validator("patient_name", "clinician")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_time_slot(self):
        if (
            self.start_time.minute not in (0, 15, 30, 45)
            or self.start_time.second != 0
            or self.start_time.microsecond != 0
        ):
            raise ValueError("start_time must use a 15-minute interval")
        return self


class Schedule(ScheduleCreate):
    id: int


class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinician: str | None = None
    start_time: datetime | None = None
    duration: Literal[30, 60] | None = None

    @field_validator("clinician")
    @classmethod
    def clinician_must_not_be_blank(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("clinician must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("updated fields must not be null")
        if self.start_time is not None and (
            self.start_time.minute not in (0, 15, 30, 45)
            or self.start_time.second != 0
            or self.start_time.microsecond != 0
        ):
            raise ValueError("start_time must use a 15-minute interval")
        return self


SCHEDULES: list[Schedule] = []
SCHEDULES_LOCK = Lock()
SCHEDULE_IDS = count(1)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/clinicians")
def get_clinicians() -> list[str]:
    return CLINICIANS


@app.get("/api/schedules", response_model=list[Schedule])
def get_schedules() -> list[Schedule]:
    with SCHEDULES_LOCK:
        return sorted(SCHEDULES, key=lambda schedule: schedule.start_time)


@app.post(
    "/api/schedules",
    response_model=Schedule,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule(schedule: ScheduleCreate) -> Schedule:
    if schedule.clinician not in CLINICIANS:
        raise HTTPException(status_code=400, detail="Unknown clinician")

    with SCHEDULES_LOCK:
        overlaps = any(
            existing.clinician == schedule.clinician
            and schedule.start_time
            < existing.start_time + timedelta(minutes=existing.duration)
            and existing.start_time
            < schedule.start_time + timedelta(minutes=schedule.duration)
            for existing in SCHEDULES
        )
        if overlaps:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Time is scheduled with another patient",
            )

        created = Schedule(id=next(SCHEDULE_IDS), **schedule.model_dump())
        SCHEDULES.append(created)
    return created


@app.patch("/api/schedules/{schedule_id}", response_model=Schedule)
def reschedule(schedule_id: int, updates: ScheduleUpdate) -> Schedule:
    with SCHEDULES_LOCK:
        index = next(
            (index for index, schedule in enumerate(SCHEDULES) if schedule.id == schedule_id),
            None,
        )
        if index is None:
            raise HTTPException(status_code=404, detail="Schedule not found")

        candidate_data = SCHEDULES[index].model_dump()
        candidate_data.update(updates.model_dump(exclude_unset=True))
        candidate = Schedule(**candidate_data)

        if candidate.clinician not in CLINICIANS:
            raise HTTPException(status_code=400, detail="Unknown clinician")

        overlaps = any(
            existing.id != schedule_id
            and existing.clinician == candidate.clinician
            and candidate.start_time
            < existing.start_time + timedelta(minutes=existing.duration)
            and existing.start_time
            < candidate.start_time + timedelta(minutes=candidate.duration)
            for existing in SCHEDULES
        )
        if overlaps:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Time is scheduled with another patient",
            )

        SCHEDULES[index] = candidate
        return candidate


@app.delete("/api/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_schedule(schedule_id: int) -> Response:
    with SCHEDULES_LOCK:
        for index, schedule in enumerate(SCHEDULES):
            if schedule.id == schedule_id:
                del SCHEDULES[index]
                return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail="Schedule not found")

