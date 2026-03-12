"""Base classes for the Visa dispute rules engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, timedelta

from visa_disputes_agent.models.enums import (
    DisputeCategory,
    DisputeCondition,
    Region,
    TransactionEnvironment,
)


@dataclass
class DisputeReasonRule:
    """Encodes the conditions under which a dispute can be initiated."""

    condition: DisputeCondition
    description: str
    applicable_regions: list[Region] = field(default_factory=lambda: [Region.ALL])
    requirements: list[str] = field(default_factory=list)


@dataclass
class InvalidDisputeRule:
    """Encodes conditions that make a dispute invalid."""

    condition: DisputeCondition
    description: str
    applicable_regions: list[Region] = field(default_factory=lambda: [Region.ALL])


@dataclass
class TimeLimitRule:
    """Encodes time limit rules for dispute filing."""

    condition: DisputeCondition
    calendar_days: int
    start_from: str  # e.g., "transaction_processing_date", "transaction_date"
    applicable_regions: list[Region] = field(default_factory=lambda: [Region.ALL])
    waiting_period_days: int = 0
    waiting_period_description: str = ""
    max_calendar_days: int = 0  # absolute maximum (e.g., 540 days)
    notes: str = ""

    def calculate_deadline(self, start_date: date) -> date:
        """Calculate the deadline date from a start date."""
        deadline = start_date + timedelta(days=self.calendar_days)
        if self.max_calendar_days > 0:
            absolute_max = start_date + timedelta(days=self.max_calendar_days)
            deadline = min(deadline, absolute_max)
        return deadline

    def is_within_limit(self, start_date: date, filing_date: date) -> bool:
        """Check if filing date is within the time limit."""
        deadline = self.calculate_deadline(start_date)
        return filing_date <= deadline


@dataclass
class DocumentationRequirement:
    """Encodes documentation/certification requirements for a dispute."""

    condition: DisputeCondition
    required_items: list[str]
    certifications: list[str] = field(default_factory=list)
    applicable_regions: list[Region] = field(default_factory=lambda: [Region.ALL])


@dataclass
class DisputeResponseRequirement:
    """Encodes what an acquirer must provide in response to a dispute."""

    condition: DisputeCondition
    required_evidence: list[str]
    applicable_regions: list[Region] = field(default_factory=lambda: [Region.ALL])


@dataclass
class PreArbitrationRequirement:
    """Encodes requirements for pre-arbitration attempts."""

    condition: DisputeCondition
    required_documentation: list[str]
    applicable_regions: list[Region] = field(default_factory=lambda: [Region.ALL])


@dataclass
class CompellingEvidenceItem:
    """A single item of compelling evidence that can be submitted."""

    item_number: int
    description: str
    applicable_conditions: list[DisputeCondition]
    applicable_environments: list[TransactionEnvironment] = field(default_factory=list)
    sub_requirements: list[str] = field(default_factory=list)
    min_sub_requirements: int = 0  # Minimum number of sub-requirements to satisfy


class DisputeRuleSet(ABC):
    """Abstract base class for a set of rules governing a dispute category."""

    @property
    @abstractmethod
    def category(self) -> DisputeCategory:
        """The dispute category this rule set covers."""
        ...

    @property
    @abstractmethod
    def conditions(self) -> list[DisputeCondition]:
        """List of dispute conditions in this category."""
        ...

    @abstractmethod
    def get_dispute_reasons(self, condition: DisputeCondition) -> list[DisputeReasonRule]:
        """Get valid dispute reasons for a condition."""
        ...

    @abstractmethod
    def get_invalid_dispute_rules(self, condition: DisputeCondition) -> list[InvalidDisputeRule]:
        """Get rules that would make a dispute invalid."""
        ...

    @abstractmethod
    def get_time_limits(self, condition: DisputeCondition) -> list[TimeLimitRule]:
        """Get time limit rules for a condition."""
        ...

    @abstractmethod
    def get_documentation_requirements(
        self, condition: DisputeCondition
    ) -> list[DocumentationRequirement]:
        """Get documentation requirements for a condition."""
        ...

    @abstractmethod
    def get_response_requirements(
        self, condition: DisputeCondition
    ) -> list[DisputeResponseRequirement]:
        """Get dispute response requirements for a condition."""
        ...
