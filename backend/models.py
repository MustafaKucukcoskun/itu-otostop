import re

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum

CRN_RE = re.compile(r'^\d{5}$')


class CRNStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    ALREADY = "already"
    FULL = "full"
    CONFLICT = "conflict"
    UPGRADE = "upgrade"
    DEBOUNCE = "debounce"
    ERROR = "error"


class ConfigRequest(BaseModel):
    token: Optional[str] = Field(default=None, description="JWT Bearer token (gönderilmezse mevcut token korunur)")
    ecrn_list: list[str] = Field(..., description="Eklenecek CRN listesi", max_length=20)
    scrn_list: list[str] = Field(default_factory=list, description="Silinecek CRN listesi", max_length=20)
    kayit_saati: str = Field(default="", pattern=r"^(\d{2}:\d{2}:\d{2})?$")
    max_deneme: int = Field(default=60, ge=1, le=300)
    retry_aralik: float = Field(default=3.0, ge=3.0, le=10.0)
    gecikme_buffer: float = Field(default=0.005, ge=0.0, le=0.1)
    dry_run: bool = Field(default=False, description="Test modu — gerçek kayıt yapmaz")

    @field_validator('ecrn_list', 'scrn_list')
    @classmethod
    def validate_crn_format(cls, v: list[str]) -> list[str]:
        for crn in v:
            if not CRN_RE.match(crn):
                raise ValueError(f"Geçersiz CRN formatı: '{crn}' (5 haneli sayı olmalı)")
        return v


class ConfigResponse(BaseModel):
    ecrn_list: list[str]
    scrn_list: list[str]
    kayit_saati: str
    max_deneme: int
    retry_aralik: float
    gecikme_buffer: float
    token_set: bool
    token_preview: str = ""
    dry_run: bool = False


class CalibrationResult(BaseModel):
    server_offset_ms: float
    rtt_one_way_ms: float
    rtt_full_ms: float
    ntp_offset_ms: Optional[float] = None
    server_ntp_diff_ms: Optional[float] = None
    accuracy_ms: float
    source: str = "manual"  # manual, initial, auto, final


class CRNResultItem(BaseModel):
    crn: str
    status: CRNStatus
    message: str = ""


class RegistrationState(BaseModel):
    phase: str = "idle"  # idle, calibrating, waiting, registering, done
    running: bool = False
    current_attempt: int = 0
    max_attempts: int = 60
    crn_results: list[CRNResultItem] = []
    calibration: Optional[CalibrationResult] = None
    countdown_seconds: Optional[float] = None
    trigger_time: Optional[float] = None


class TokenTestResult(BaseModel):
    valid: bool
    status_code: int
    message: str


class WSEvent(BaseModel):
    type: str  # log, state, crn_update, calibration, countdown, done
    data: dict = {}
    timestamp: float = 0.0
