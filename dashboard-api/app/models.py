from enum import Enum

class Role(str, Enum):
    VENDOR_ADMIN = "vendor_admin"
    DISTRIBUTOR_MANAGER = "distributor_manager"

class OrderStatus(str, Enum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    INVOICE_SENT = "INVOICE_SENT"
    TEST_DRIVE = "TEST_DRIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

ALLOWED_ORDER_STATUSES = {s.value for s in OrderStatus}
