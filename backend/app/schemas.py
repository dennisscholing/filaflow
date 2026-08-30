from decimal import Decimal
from typing import Literal

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


class UserPreferenceInput(BaseModel):
    preferred_unit: Literal["grams", "meters", "both"]


class PasswordChangeInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class AdminPasswordResetInput(BaseModel):
    temporary_password: str = Field(min_length=12, max_length=256)


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

    @field_validator("color_hex")
    @classmethod
    def valid_hex(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 7 or not value.startswith("#") or any(character not in "0123456789ABCDEF" for character in value[1:]):
            raise ValueError("Color must be a six-digit HEX value")
        return value

    @field_validator("diameter_mm", "density_g_cm3")
    @classmethod
    def positive_conversion_value(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Diameter and density must be greater than zero")
        return value


class SpoolUpdateInput(BaseModel):
    brand: str = Field(min_length=1, max_length=120)
    material_name: str = Field(min_length=1, max_length=160)
    material_type: str = Field(min_length=1, max_length=40)
    color_name: str = Field(default="", max_length=80)
    color_hex: str = "#808080"
    location: str = Field(default="", max_length=120)
    lot_number: str = Field(default="", max_length=80)
    serial_number: str = Field(default="", max_length=80)
    diameter_mm: Decimal = Field(gt=0)
    density_g_cm3: Decimal = Field(gt=0)
    tare_weight_g: Decimal = Field(ge=0)
    low_stock_weight_g: Decimal = Field(ge=0)
    purchase_price: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)

    @field_validator("color_hex")
    @classmethod
    def valid_hex(cls, value: str) -> str:
        return SpoolInput.valid_hex(value)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class WeighInput(BaseModel):
    total_weight_g: Decimal | None = None
    net_weight_g: Decimal | None = None
    consumed_weight_g: Decimal | None = None
    allow_negative: bool = False
    note: str = "Manual weighing"


class PrinterInput(BaseModel):
    name: str
    manufacturer: str = ""
    model: str = ""
    location: str = ""
    slicer_profile: str = ""
    notes: str = ""
    preset: str = "single"
    tool_count: int | None = Field(default=None, ge=1, le=64)


class PrinterUpdateInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    manufacturer: str = Field(default="", max_length=120)
    model: str = Field(default="", max_length=120)
    location: str = Field(default="", max_length=120)
    slicer_profile: str = Field(default="", max_length=255)
    notes: str = Field(default="", max_length=4000)


class LoadoutInput(BaseModel):
    spool_id: str | None


class JobPrinterInput(BaseModel):
    printer_id: str


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


class InventorySettingsInput(BaseModel):
    reorder_threshold_g: Decimal = Field(ge=0, le=100_000)


class ReorderRuleInput(BaseModel):
    product_key: str = Field(min_length=1, max_length=500)
    threshold_g: Decimal | None = Field(default=None, ge=0, le=100_000)
    ignored: bool = False
    product_snapshot: dict = Field(default_factory=dict)


class LabelElementInput(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    type: Literal["qr", "code", "serial", "brand", "filament", "material", "color_swatch", "color_name", "color_hex", "location", "remaining", "custom_text", "border"]
    x: Decimal = Field(ge=0, le=200)
    y: Decimal = Field(ge=0, le=150)
    width: Decimal = Field(gt=0, le=200)
    height: Decimal = Field(gt=0, le=150)
    font_size: Decimal = Field(default=3.2, ge=1.5, le=20)
    visible: bool = True
    text: str = Field(default="", max_length=160)
    bold: bool = False


class LabelTemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    width_mm: Decimal = Field(ge=20, le=200)
    height_mm: Decimal = Field(ge=15, le=150)
    layout: list[LabelElementInput] = Field(min_length=1, max_length=40)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Template name cannot be empty")
        return value
