from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field

class UserProfile(BaseModel):
    id: int
    email: str
    full_name: str
    organization: str
    role: str
    distributor_id: Optional[int] = None
    is_active: bool
    created_at: Optional[datetime] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile

class OrderListItem(BaseModel):
    id: int
    kp_number: Optional[str] = None
    company_name: Optional[str] = None
    bin: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    client_name: Optional[str] = None
    order_status: str
    total_amount: float
    distributor_id: Optional[int] = None
    distributor_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    sla_breached: bool = False
    wait_time_hours: Optional[float] = None

class OrdersListResponse(BaseModel):
    items: List[OrderListItem]
    total: int
    pages: int
    page: int
    limit: int

class OrderDetailResponse(BaseModel):
    id: int
    kp_number: Optional[str] = None
    company_name: Optional[str] = None
    bin: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    client_name: Optional[str] = None
    tg_user_id: Optional[int] = None
    tg_username: Optional[str] = None
    order_status: str
    manager_notes: Optional[str] = ""
    total_amount: float
    distributor_id: Optional[int] = None
    distributor_name: Optional[str] = None
    selected_bundle: Any = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    sla_breached: bool = False
    wait_time_hours: Optional[float] = None

class OrderStatusUpdateRequest(BaseModel):
    order_status: str
    manager_notes: Optional[str] = None

# -------------------------------------------------------------------------
# Sprint 3 Analytics Schemas
# -------------------------------------------------------------------------
class RegionShare(BaseModel):
    distributor_id: int
    city: str
    orders_count: int
    revenue_kzt: float
    share_percent: float

class ChannelBreakdown(BaseModel):
    direct_catalog_count: int
    ai_fitting_count: int

class AnalyticsSummaryResponse(BaseModel):
    total_revenue_kzt: float
    total_orders_count: int
    average_check_kzt: float
    by_region: List[RegionShare]
    by_channel: ChannelBreakdown

class TopProductItem(BaseModel):
    sku: str
    name: str
    system_code: str
    total_qty: int
    total_revenue_kzt: float

class BreachedLeadItem(BaseModel):
    id: int
    kp_number: Optional[str] = None
    company_name: Optional[str] = None
    city: Optional[str] = None
    client_name: Optional[str] = None
    phone: Optional[str] = None
    order_status: str
    created_at: Optional[datetime] = None
    wait_time_hours: float
    wait_time_formatted: str
    sla_breached: bool = True

class AnalyticsSlaResponse(BaseModel):
    average_response_time_minutes: float
    average_response_time_formatted: str
    processed_orders_count: int
    breached_leads_count: int
    breached_leads: List[BreachedLeadItem]

# -------------------------------------------------------------------------
# Sprint 3 Products Management Schemas
# -------------------------------------------------------------------------
class AdminProductItem(BaseModel):
    sku: str
    name: str
    category: str
    system_code: Optional[str] = None
    price_eur: Optional[float] = None
    current_price_kzt: float
    is_focus_item: bool
    is_active_in_catalog: bool

class ProductToggleResponse(BaseModel):
    sku: str
    name: str
    is_active_in_catalog: bool
    message: str
