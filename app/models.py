from pydantic import BaseModel, Field
from typing import Optional


# --- Auth ---

class PinSetup(BaseModel):
    pin: str = Field(min_length=4, max_length=12)

class PinVerify(BaseModel):
    pin: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


# --- Children ---

class ChildCreate(BaseModel):
    name: str
    payout_method: str = "ln_address"
    ln_address: Optional[str] = None

class ChildResponse(BaseModel):
    id: int
    name: str
    active: bool
    payout_method: str
    ln_address: Optional[str] = None


# --- Tasks ---

class TaskCreate(BaseModel):
    title: str
    reward_czk: float = Field(gt=0, description="Odměna v CZK (např. 5.00)")
    sort_order: int = 0
    daily_limit: int = Field(default=1, ge=0, description="Max splnění za den (0 = neomezeno)")

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    reward_czk: Optional[float] = Field(default=None, gt=0)
    active: Optional[bool] = None
    sort_order: Optional[int] = None
    daily_limit: Optional[int] = Field(default=None, ge=0)

class TaskResponse(BaseModel):
    id: int
    title: str
    reward_czk: float
    active: bool
    sort_order: int
    daily_limit: int = 1


# --- Completions ---

class CompletionCreate(BaseModel):
    child_id: int
    task_id: int

class CompletionReview(BaseModel):
    note: Optional[str] = None

class CompletionResponse(BaseModel):
    id: int
    child_id: int
    task_id: int
    task_title: Optional[str] = None
    reward_czk: Optional[float] = None
    reward_sats: Optional[int] = None
    rate_czk_per_btc: Optional[float] = None
    status: str
    submitted_at: str
    reviewed_at: Optional[str] = None
    review_note: Optional[str] = None


# --- Payouts (dříve Settlements) ---

class PayoutResponse(BaseModel):
    id: Optional[int] = None
    child_id: int
    total_sats: int
    total_czk: float
    pending_count: int = 0
    status: str
    ln_payment_hash: Optional[str] = None
    paid_at: Optional[str] = None


# --- CoinGecko ---

class RateResponse(BaseModel):
    rate_czk_per_btc: float
    rate_usd_per_btc: float
    source: str
