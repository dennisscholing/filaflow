from decimal import Decimal
from pydantic import BaseModel, Field, field_validator


class LoginInput(BaseModel):
    email: str
    password: str


class UserCreateInput(BaseModel):
    email: str
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=256)
    role: str = "operator"

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        if value not in {"admin", "operator"}:
            raise ValueError("Role must be admin or operator")
        return value


class UserStatusInput(BaseModel):
    active: bool


class SpoolInput(BaseModel):
    brand: str = "Generic"
    material_name: str
    material_type: str = "PLA"
    color_name: str = ""
    color_hex: str = "#808080"
    location: str = ""
    lot_number: str = ""
    serial_number: str = ""
    diameter_mm: Decimal = Decimal("1.75")
    density_g_cm3: Decimal = Decimal("1.24")
    tare_weight_g: Decimal = Decimal("0")
    initial_weight_g: Decimal
    initial_length_m: Decimal | None = None
    low_stock_weight_g: Decimal = Decimal("100")
    purchase_price: Decimal | None = None
    currency: str = "EUR"
    opt_brand_uuid: str | None = None
    opt_material_uuid: str | None = None
    opt_package_uuid: str | None = None
    opt_container_uuid: str | None = None
    catalog_snapshot: dict = Field(default_factory=dict)


class WeighInput(BaseModel):
    total_weight_g: Decimal | None = None
    net_weight_g: Decimal | None = None
    note: str = "Manual weighing"


class PrinterInput(BaseModel):
    name: str
    manufacturer: str = ""
    model: str = ""
    slicer_profile: str = ""
    notes: str = ""
    preset: str = "single"
    tool_count: int | None = Field(default=None, ge=1, le=64)


class LoadoutInput(BaseModel):
    spool_id: str | None


class JobMapItem(BaseModel):
    usage_id: str
    spool_id: str


class JobMapInput(BaseModel):
    mappings: list[JobMapItem]


class JobBookItem(BaseModel):
    usage_id: str
    actual_weight_g: Decimal | None = None
    actual_length_m: Decimal | None = None


class JobBookInput(BaseModel):
    usages: list[JobBookItem]
    allow_negative: bool = False


class TokenInput(BaseModel):
    name: str
    printer_id: str | None = None
