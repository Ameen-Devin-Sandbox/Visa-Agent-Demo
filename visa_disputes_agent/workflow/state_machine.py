"""Dispute processing workflow state machine."""

from __future__ import annotations

from datetime import datetime

import structlog

from visa_disputes_agent.models.dispute import DisputeTask
from visa_disputes_agent.models.enums import DisputeWorkflowState

logger = structlog.get_logger()

# Valid state transitions
VALID_TRANSITIONS: dict[DisputeWorkflowState, list[DisputeWorkflowState]] = {
    DisputeWorkflowState.INTAKE: [
        DisputeWorkflowState.VALIDATION,
        DisputeWorkflowState.ESCALATED_TO_HUMAN,
    ],
    DisputeWorkflowState.VALIDATION: [
        DisputeWorkflowState.CATEGORIZATION,
        DisputeWorkflowState.ESCALATED_TO_HUMAN,
    ],
    DisputeWorkflowState.CATEGORIZATION: [
        DisputeWorkflowState.RULE_EVALUATION,
        DisputeWorkflowState.ESCALATED_TO_HUMAN,
    ],
    DisputeWorkflowState.RULE_EVALUATION: [
        DisputeWorkflowState.EVIDENCE_REVIEW,
        DisputeWorkflowState.TIME_LIMIT_CHECK,
        DisputeWorkflowState.DECISION,
        DisputeWorkflowState.ESCALATED_TO_HUMAN,
    ],
    DisputeWorkflowState.EVIDENCE_REVIEW: [
        DisputeWorkflowState.TIME_LIMIT_CHECK,
        DisputeWorkflowState.DECISION,
        DisputeWorkflowState.ESCALATED_TO_HUMAN,
    ],
    DisputeWorkflowState.TIME_LIMIT_CHECK: [
        DisputeWorkflowState.DECISION,
        DisputeWorkflowState.ESCALATED_TO_HUMAN,
    ],
    DisputeWorkflowState.DECISION: [
        DisputeWorkflowState.RESPONSE_GENERATION,
        DisputeWorkflowState.PRE_ARBITRATION,
        DisputeWorkflowState.RESOLUTION,
        DisputeWorkflowState.ESCALATED_TO_HUMAN,
    ],
    DisputeWorkflowState.RESPONSE_GENERATION: [
        DisputeWorkflowState.RESOLUTION,
        DisputeWorkflowState.PRE_ARBITRATION,
        DisputeWorkflowState.ESCALATED_TO_HUMAN,
    ],
    DisputeWorkflowState.PRE_ARBITRATION: [
        DisputeWorkflowState.ARBITRATION,
        DisputeWorkflowState.RESOLUTION,
        DisputeWorkflowState.ESCALATED_TO_HUMAN,
    ],
    DisputeWorkflowState.ARBITRATION: [
        DisputeWorkflowState.RESOLUTION,
        DisputeWorkflowState.ESCALATED_TO_HUMAN,
    ],
    DisputeWorkflowState.RESOLUTION: [],  # Terminal state
    DisputeWorkflowState.ESCALATED_TO_HUMAN: [
        # Human can return task to any active state
        DisputeWorkflowState.VALIDATION,
        DisputeWorkflowState.CATEGORIZATION,
        DisputeWorkflowState.RULE_EVALUATION,
        DisputeWorkflowState.DECISION,
        DisputeWorkflowState.RESOLUTION,
    ],
}


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current: DisputeWorkflowState, target: DisputeWorkflowState) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid workflow transition from {current.value} to {target.value}"
        )


class DisputeWorkflow:
    """Manages the state machine for dispute processing lifecycle.

    Enforces valid state transitions and tracks the complete history
    of state changes for audit purposes.
    """

    def __init__(self, task: DisputeTask) -> None:
        self._task = task
        self._history: list[tuple[DisputeWorkflowState, DisputeWorkflowState, datetime]] = []

    @property
    def current_state(self) -> DisputeWorkflowState:
        """Get the current workflow state."""
        return self._task.workflow_state

    @property
    def history(self) -> list[tuple[DisputeWorkflowState, DisputeWorkflowState, datetime]]:
        """Get the complete state transition history."""
        return list(self._history)

    def can_transition_to(self, target: DisputeWorkflowState) -> bool:
        """Check if a transition to the target state is valid."""
        valid_targets = VALID_TRANSITIONS.get(self.current_state, [])
        return target in valid_targets

    def transition_to(self, target: DisputeWorkflowState, reason: str = "") -> None:
        """Transition to a new workflow state.

        Raises InvalidTransitionError if the transition is not valid.
        """
        if not self.can_transition_to(target):
            raise InvalidTransitionError(self.current_state, target)

        previous = self.current_state
        now = datetime.utcnow()

        self._task.workflow_state = target
        self._task.updated_at = now
        self._history.append((previous, target, now))

        self._task.add_log_entry(
            action="workflow_transition",
            details=f"Transitioned from {previous.value} to {target.value}. {reason}".strip(),
        )

        logger.info(
            "workflow_transition",
            task_id=str(self._task.task_id),
            from_state=previous.value,
            to_state=target.value,
            reason=reason,
        )

    def is_terminal(self) -> bool:
        """Check if the workflow has reached a terminal state."""
        return self.current_state == DisputeWorkflowState.RESOLUTION

    def is_escalated(self) -> bool:
        """Check if the workflow is currently escalated to human review."""
        return self.current_state == DisputeWorkflowState.ESCALATED_TO_HUMAN

    def get_next_states(self) -> list[DisputeWorkflowState]:
        """Get the list of valid next states from the current state."""
        return VALID_TRANSITIONS.get(self.current_state, [])
