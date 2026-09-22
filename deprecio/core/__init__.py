"""Core analytical and depreciation engine of Deprecio."""

from .metrics import (
    MarketStage,
    SweetSpotAnalysis,
    analyze_sweet_spot,
    calculate_depreciation_drop,
    calculate_edition_gap,
    calculate_residual_value,
)

__all__ = [
    "MarketStage",
    "SweetSpotAnalysis",
    "analyze_sweet_spot",
    "calculate_depreciation_drop",
    "calculate_edition_gap",
    "calculate_residual_value",
]
