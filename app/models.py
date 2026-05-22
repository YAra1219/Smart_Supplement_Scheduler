from pydantic import BaseModel, Field
from typing import List, Optional


class MedItem(BaseModel):
    name: str = Field(description="Brand or generic name of the supplement")
    type: str = Field(description="Type of supplement, currently only 'supplement'")
    active_ingredients: List[str] = Field(description="List of core ingredients")
    recommended_dosage: str = Field(description="Official dosage recommendation if visible")
    is_prescription: bool = Field(default=False, description="Whether this is a prescription medication")
    prescription_warning: Optional[str] = Field(default=None, description="Warning message if prescription drug is detected")


class UserRoutine(BaseModel):
    wake_up_time: str
    breakfast_time: str
    lunch_time: str
    dinner_time: str
    sleep_time: str
    current_medications: List[str] = Field(default_factory=list, description="用户当前服用的处方药/OTC药品列表")


class ScheduleEntry(BaseModel):
    time: str = Field(description="24 小时制时间格式，如 '08:00'")
    action: str = Field(description="做什么，如 '服用维生素 D3'")
    reasoning: str = Field(description="为什么这个时间，如 '脂溶性，随餐吸收更好'")


class FinalPlan(BaseModel):
    status: str = Field(description="'success' or 'rejected_due_to_safety'")
    rejection_reason: Optional[str] = Field(None, description="If acute med is detected, reject and explain")
    schedule: List[ScheduleEntry] = Field(default_factory=list)
    warnings: List[str] = Field(description="Any general warnings or disclaimers")
    safety_score: Optional[int] = Field(None, description="Safety score from Layer 1 validation (0-100)")
    data_sources: List[str] = Field(default_factory=list, description="Authoritative data source URLs (RxNorm, OpenFDA, NIH)")
    drug_interactions: List[str] = Field(default_factory=list, description="药物-补剂相互作用警告（置顶显示）")
