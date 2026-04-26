"""Abstract data source adapter.

Every concrete adapter (Semrush real / Semrush mock / CSV) returns the
same shape, so the rest of the pipeline never knows or cares which source
the data came from.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Literal

from app.schemas import RawKeyword, RawPage


@dataclass
class AdapterResult:
    pages: List[RawPage] = field(default_factory=list)
    keywords: List[RawKeyword] = field(default_factory=list)
    source: Literal["semrush", "mock", "csv"] = "mock"
    notes: List[str] = field(default_factory=list)


class DataSourceAdapter(ABC):
    name: Literal["semrush", "mock", "csv"]

    @abstractmethod
    async def fetch(
        self,
        competitor_domains: List[str],
        country: str,
        time_window_days: int,
    ) -> AdapterResult:
        """Return raw pages + keywords for the given competitor domains."""
