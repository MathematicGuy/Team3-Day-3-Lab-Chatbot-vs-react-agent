"""
user_info_tools.py
~~~~~~~~~~~~~~~~~~
Tools để thu thập và quản lý thông tin người dùng.

Bao gồm:
  - Thông tin cá nhân (tên, email, phone)
  - Thông tin địa chỉ
  - Yêu cầu/Preferences
  - Lịch sử tương tác
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, ValidationError


# ---------------------------------------------------------------------------
# Pydantic Models — Validate thông tin người dùng
# ---------------------------------------------------------------------------

class PersonalInfo(BaseModel):
    """Thông tin cá nhân người dùng - match với invoice_tools."""
    passenger_name: str = Field(..., min_length=2, max_length=100, description="Họ tên hành khách")
    passenger_email: Optional[str] = Field(None, description="Địa chỉ email")
    passenger_phone: Optional[str] = Field(None, description="Số điện thoại")
    date_of_birth: Optional[str] = Field(None, description="Ngày sinh (YYYY-MM-DD)")

    @field_validator("passenger_email", mode="before", check_fields=False)
    @classmethod
    def _validate_email(cls, v):
        if v is None or v == "":
            return None
        v = str(v).strip()
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, v):
            raise ValueError(f"Email không hợp lệ: {v}")
        return v

    @field_validator("passenger_phone", mode="before", check_fields=False)
    @classmethod
    def _validate_phone(cls, v):
        if v is None or v == "":
            return None
        v = str(v).strip()
        phone_pattern = r"^[\d\s\+\-\(\)]{7,15}$"
        if not re.match(phone_pattern, v):
            raise ValueError(f"Số điện thoại không hợp lệ: {v}")
        return v

    @field_validator("date_of_birth", mode="before", check_fields=False)
    @classmethod
    def _validate_dob(cls, v):
        if v is None or v == "":
            return None
        v = str(v).strip()
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Ngày sinh phải có định dạng YYYY-MM-DD: {v}")
        return v


class AddressInfo(BaseModel):
    """Thông tin địa chỉ."""
    street: str = Field(..., min_length=3, description="Địa chỉ đường phố")
    city: str = Field(..., min_length=2, description="Thành phố/Tỉnh")
    state: Optional[str] = Field(None, description="Bang/Tỉnh (tùy chọn)")
    postal_code: Optional[str] = Field(None, description="Mã bưu điện")
    country: str = Field(default="Vietnam", description="Quốc gia")

    @field_validator("postal_code", mode="before", check_fields=False)
    @classmethod
    def _validate_postal(cls, v):
        if v is None or v == "":
            return None
        v = str(v).strip()
        if not re.match(r"^[\w\s\-]{3,10}$", v):
            raise ValueError(f"Mã bưu điện không hợp lệ: {v}")
        return v


class TravelPreferences(BaseModel):
    """Yêu cầu/Preferences của người dùng."""
    preferred_airline: Optional[str] = Field(None, description="Hãng hàng không ưa thích")
    seat_preference: Optional[str] = Field(None, description="Yêu cầu chỗ ngồi (window, aisle, middle)")
    meal_preference: Optional[str] = Field(None, description="Yêu cầu bữa ăn (vegetarian, vegan, etc.)")
    baggage_preference: Optional[int] = Field(None, ge=0, description="Số lượng hành lý xách tay")
    special_requests: Optional[str] = Field(None, max_length=500, description="Yêu cầu đặc biệt")
    max_budget: Optional[float] = Field(None, gt=0, description="Ngân sách tối đa")
    preferred_class: Optional[str] = Field(default="economy", description="Hạng vé ưa thích")

    @field_validator("seat_preference", mode="before", check_fields=False)
    @classmethod
    def _validate_seat(cls, v):
        if v is None or v == "":
            return None
        v = str(v).strip().lower()
        valid_seats = {"window", "aisle", "middle", "any"}
        if v not in valid_seats:
            raise ValueError(f"Vị trí chỗ ngồi phải là: {', '.join(valid_seats)}")
        return v


class UserProfile(BaseModel):
    """Hồ sơ người dùng hoàn chỉnh."""
    user_id: str = Field(..., description="ID người dùng")
    personal_info: PersonalInfo = Field(..., description="Thông tin cá nhân")
    address_info: Optional[AddressInfo] = Field(None, description="Thông tin địa chỉ")
    travel_preferences: Optional[TravelPreferences] = Field(None, description="Yêu cầu du lịch")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class UserInfoException(Exception):
    """Exception cho user_info_tools."""
    pass


# ---------------------------------------------------------------------------
# Tools — Thu thập thông tin
# ---------------------------------------------------------------------------

def collect_personal_info(
    passenger_name: str,
    passenger_email: Optional[str] = None,
    passenger_phone: Optional[str] = None,
    date_of_birth: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Thu thập và xác thực thông tin cá nhân.
    Dữ liệu đầu ra fit trực tiếp với generate_invoice().

    Args:
        passenger_name: Họ tên hành khách (bắt buộc)
        passenger_email: Email (tùy chọn)
        passenger_phone: Số điện thoại (tùy chọn)
        date_of_birth: Ngày sinh YYYY-MM-DD (tùy chọn)

    Returns:
        {
            "status": "success" | "error",
            "message": "...",
            "personal_info": {...}  # nếu success
        }
    """
    try:
        info = PersonalInfo(
            passenger_name=passenger_name,
            passenger_email=passenger_email,
            passenger_phone=passenger_phone,
            date_of_birth=date_of_birth,
        )
        return {
            "status": "success",
            "message": "✓ Thông tin cá nhân hợp lệ.",
            "personal_info": info.model_dump(),
        }
    except ValidationError as exc:
        errors = [
            {"field": error["loc"][0], "message": error["msg"]}
            for error in exc.errors()
        ]
        error_msg = "\n".join(f"  • {e['field']}: {e['message']}" for e in errors)
        return {
            "status": "error",
            "message": f"❌ Thông tin không hợp lệ:\n{error_msg}",
            "personal_info": None,
        }


def collect_address_info(
    street: str,
    city: str,
    state: Optional[str] = None,
    postal_code: Optional[str] = None,
    country: str = "Vietnam",
) -> Dict[str, Any]:
    """
    Thu thập và xác thực thông tin địa chỉ.

    Args:
        street: Địa chỉ đường phố (bắt buộc)
        city: Thành phố/Tỉnh (bắt buộc)
        state: Bang/Tỉnh (tùy chọn)
        postal_code: Mã bưu điện (tùy chọn)
        country: Quốc gia (mặc định: Vietnam)

    Returns:
        {
            "status": "success" | "error",
            "message": "...",
            "address_info": {...}  # nếu success
        }
    """
    try:
        info = AddressInfo(
            street=street,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
        )
        return {
            "status": "success",
            "message": "✓ Thông tin địa chỉ hợp lệ.",
            "address_info": info.model_dump(),
        }
    except ValidationError as exc:
        errors = [
            {"field": error["loc"][0], "message": error["msg"]}
            for error in exc.errors()
        ]
        error_msg = "\n".join(f"  • {e['field']}: {e['message']}" for e in errors)
        return {
            "status": "error",
            "message": f"❌ Thông tin không hợp lệ:\n{error_msg}",
            "address_info": None,
        }


def collect_travel_preferences(
    preferred_airline: Optional[str] = None,
    seat_preference: Optional[str] = None,
    meal_preference: Optional[str] = None,
    baggage_preference: Optional[int] = None,
    special_requests: Optional[str] = None,
    max_budget: Optional[float] = None,
    preferred_class: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Thu thập và xác thực yêu cầu/preferences du lịch.

    Args:
        preferred_airline: Hãng hàng không ưa thích
        seat_preference: Yêu cầu chỗ ngồi (window, aisle, middle, any)
        meal_preference: Yêu cầu bữa ăn (vegetarian, vegan, etc.)
        baggage_preference: Số hành lý xách tay
        special_requests: Yêu cầu đặc biệt
        max_budget: Ngân sách tối đa
        preferred_class: Hạng vé ưa thích (economy, business, first)

    Returns:
        {
            "status": "success" | "error",
            "message": "...",
            "travel_preferences": {...}  # nếu success
        }
    """
    try:
        prefs = TravelPreferences(
            preferred_airline=preferred_airline,
            seat_preference=seat_preference,
            meal_preference=meal_preference,
            baggage_preference=baggage_preference,
            special_requests=special_requests,
            max_budget=max_budget,
            preferred_class=preferred_class,
        )
        return {
            "status": "success",
            "message": "✓ Yêu cầu du lịch đã được xác thực.",
            "travel_preferences": prefs.model_dump(),
        }
    except ValidationError as exc:
        errors = [
            {"field": error["loc"][0], "message": error["msg"]}
            for error in exc.errors()
        ]
        error_msg = "\n".join(f"  • {e['field']}: {e['message']}" for e in errors)
        return {
            "status": "error",
            "message": f"❌ Thông tin không hợp lệ:\n{error_msg}",
            "travel_preferences": None,
        }


def create_user_profile(
    user_id: str,
    personal_info: Dict[str, Any],
    address_info: Optional[Dict[str, Any]] = None,
    travel_preferences: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Tạo hồ sơ người dùng hoàn chỉnh từ các thông tin riêng lẻ.

    Args:
        user_id: ID người dùng
        personal_info: Dict thông tin cá nhân
        address_info: Dict thông tin địa chỉ (tùy chọn)
        travel_preferences: Dict yêu cầu du lịch (tùy chọn)

    Returns:
        {
            "status": "success" | "error",
            "message": "...",
            "user_profile": {...}  # nếu success
        }
    """
    try:
        profile = UserProfile(
            user_id=user_id,
            personal_info=PersonalInfo(**personal_info),
            address_info=AddressInfo(**address_info) if address_info else None,
            travel_preferences=TravelPreferences(**travel_preferences) if travel_preferences else None,
        )
        return {
            "status": "success",
            "message": f"✓ Hồ sơ người dùng {user_id} đã được tạo.",
            "user_profile": profile.model_dump(),
        }
    except (ValidationError, TypeError) as exc:
        return {
            "status": "error",
            "message": f"❌ Lỗi tạo hồ sơ: {str(exc)}",
            "user_profile": None,
        }


def validate_all_user_info(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Xác thực tất cả thông tin người dùng cùng lúc.

    Args:
        user_data: Dict chứa toàn bộ thông tin người dùng

    Returns:
        {
            "status": "success" | "error",
            "is_valid": True | False,
            "messages": [...],
            "validation_summary": {...}
        }
    """
    validation_summary = {
        "personal_info": {"valid": False, "message": ""},
        "address_info": {"valid": False, "message": ""},
        "travel_preferences": {"valid": False, "message": ""},
    }
    messages = []

    # Validate personal info
    personal = user_data.get("personal_info", {})
    if personal:
        result = collect_personal_info(**personal)
        validation_summary["personal_info"]["valid"] = result["status"] == "success"
        validation_summary["personal_info"]["message"] = result["message"]
        messages.append(result["message"])
    else:
        validation_summary["personal_info"]["message"] = "⚠ Không có thông tin cá nhân"

    # Validate address info (nếu có)
    address = user_data.get("address_info")
    if address:
        result = collect_address_info(**address)
        validation_summary["address_info"]["valid"] = result["status"] == "success"
        validation_summary["address_info"]["message"] = result["message"]
        messages.append(result["message"])
    else:
        validation_summary["address_info"]["message"] = "⚠ Không có thông tin địa chỉ"

    # Validate travel preferences (nếu có)
    prefs = user_data.get("travel_preferences")
    if prefs:
        result = collect_travel_preferences(**prefs)
        validation_summary["travel_preferences"]["valid"] = result["status"] == "success"
        validation_summary["travel_preferences"]["message"] = result["message"]
        messages.append(result["message"])
    else:
        validation_summary["travel_preferences"]["message"] = "⚠ Không có yêu cầu du lịch"

    # Tính overall validation
    all_valid = all(v["valid"] for v in validation_summary.values() if "Không có" not in v["message"])

    return {
        "status": "success" if all_valid else "error",
        "is_valid": all_valid,
        "messages": messages,
        "validation_summary": validation_summary,
    }


def format_user_info_display(user_info: Dict[str, Any]) -> str:
    """
    Format thông tin người dùng để hiển thị đẹp.

    Returns:
        Chuỗi text đẹp để in ra chat
    """
    output = "\n" + "=" * 60 + "\n"
    output += "  📋 THÔNG TIN NGƯỜI DÙNG\n"
    output += "=" * 60 + "\n"

    # Personal Info
    personal = user_info.get("personal_info", {})
    if personal:
        output += "\n  👤 THÔNG TIN CÁ NHÂN\n"
        output += f"    • Họ tên: {personal.get('passenger_name', 'N/A')}\n"
        if personal.get("passenger_email"):
            output += f"    • Email: {personal.get('passenger_email')}\n"
        if personal.get("passenger_phone"):
            output += f"    • Điện thoại: {personal.get('passenger_phone')}\n"
        if personal.get("date_of_birth"):
            output += f"    • Ngày sinh: {personal.get('date_of_birth')}\n"

    # Address Info
    address = user_info.get("address_info", {})
    if address:
        output += "\n  🏠 THÔNG TIN ĐỊA CHỈ\n"
        output += f"    • Địa chỉ: {address.get('street', 'N/A')}\n"
        output += f"    • Thành phố: {address.get('city', 'N/A')}\n"
        if address.get("state"):
            output += f"    • Bang/Tỉnh: {address.get('state')}\n"
        if address.get("postal_code"):
            output += f"    • Mã bưu điện: {address.get('postal_code')}\n"
        output += f"    • Quốc gia: {address.get('country', 'Vietnam')}\n"

    # Travel Preferences
    prefs = user_info.get("travel_preferences", {})
    if prefs:
        output += "\n  ✈️  YÊU CẦU DU LỊCH\n"
        if prefs.get("preferred_airline"):
            output += f"    • Hãng ưa thích: {prefs.get('preferred_airline')}\n"
        if prefs.get("seat_preference"):
            output += f"    • Chỗ ngồi: {prefs.get('seat_preference')}\n"
        if prefs.get("meal_preference"):
            output += f"    • Bữa ăn: {prefs.get('meal_preference')}\n"
        if prefs.get("baggage_preference") is not None:
            output += f"    • Hành lý: {prefs.get('baggage_preference')} cái\n"
        if prefs.get("max_budget"):
            output += f"    • Ngân sách: ${prefs.get('max_budget'):,.2f}\n"
        if prefs.get("preferred_class"):
            output += f"    • Hạng vé: {prefs.get('preferred_class')}\n"
        if prefs.get("special_requests"):
            output += f"    • Yêu cầu đặc biệt: {prefs.get('special_requests')}\n"

    output += "\n" + "=" * 60 + "\n"
    return output


def adapt_to_invoice(personal_info: Dict[str, Any], passengers: int = 1) -> Dict[str, Any]:
    """
    Chuyển đổi thông tin từ user_info_tools sang định dạng cho generate_invoice().

    Args:
        personal_info: Dict từ collect_personal_info()
        passengers: Số hành khách (mặc định 1)

    Returns:
        {
            "passenger_name": "...",
            "passenger_email": "...",
            "passenger_phone": "...",
            "passengers": 1
        }
    """
    return {
        "passenger_name": personal_info.get("passenger_name"),
        "passenger_email": personal_info.get("passenger_email"),
        "passenger_phone": personal_info.get("passenger_phone"),
        "passengers": passengers,
    }
