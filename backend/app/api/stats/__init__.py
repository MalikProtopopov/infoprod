"""Пакет stats: ядровый overview_router + analytics-router под флагом.

Реэкспорт сохраняет совместимость импортов (app.api.stats import router / overview_router).
"""
from app.api.stats.analytics import router
from app.api.stats.overview import overview_router

__all__ = ["router", "overview_router"]
