import pytest
from src.models.enums import ProjectStatus
from src.services.project_service import validate_project_status_transition
from src.core.exceptions import InvariantViolationException


def test_valid_project_lifecycle_transitions():
    """Verify valid transitions across the project lifecycle."""
    # PLANNED -> ACTIVE
    assert validate_project_status_transition(ProjectStatus.PLANNED, ProjectStatus.ACTIVE) is True
    # PLANNED -> CANCELLED
    assert validate_project_status_transition(ProjectStatus.PLANNED, ProjectStatus.CANCELLED) is True

    # ACTIVE -> ON_HOLD
    assert validate_project_status_transition(ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD) is True
    # ON_HOLD -> ACTIVE (toggle back)
    assert validate_project_status_transition(ProjectStatus.ON_HOLD, ProjectStatus.ACTIVE) is True
    # ACTIVE -> COMPLETED
    assert validate_project_status_transition(ProjectStatus.ACTIVE, ProjectStatus.COMPLETED) is True
    # ACTIVE -> CANCELLED
    assert validate_project_status_transition(ProjectStatus.ACTIVE, ProjectStatus.CANCELLED) is True
    # ON_HOLD -> CANCELLED
    assert validate_project_status_transition(ProjectStatus.ON_HOLD, ProjectStatus.CANCELLED) is True

    # COMPLETED -> CLOSED
    assert validate_project_status_transition(ProjectStatus.COMPLETED, ProjectStatus.CLOSED) is True


def test_invalid_project_lifecycle_transitions():
    """Verify that illegal status skips and invalid transitions raise InvariantViolationException."""
    # Cannot jump from PLANNED to CLOSED directly
    with pytest.raises(InvariantViolationException) as exc:
        validate_project_status_transition(ProjectStatus.PLANNED, ProjectStatus.CLOSED)
    assert "Cannot transition project from PLANNED to CLOSED" in str(exc.value)

    # Cannot jump from PLANNED to COMPLETED directly
    with pytest.raises(InvariantViolationException):
        validate_project_status_transition(ProjectStatus.PLANNED, ProjectStatus.COMPLETED)

    # Cannot jump from ACTIVE to CLOSED without first being COMPLETED
    with pytest.raises(InvariantViolationException):
        validate_project_status_transition(ProjectStatus.ACTIVE, ProjectStatus.CLOSED)

    # CLOSED is terminal
    with pytest.raises(InvariantViolationException) as exc_closed:
        validate_project_status_transition(ProjectStatus.CLOSED, ProjectStatus.ACTIVE)
    assert "terminal state" in str(exc_closed.value)

    # CANCELLED is terminal
    with pytest.raises(InvariantViolationException) as exc_cancelled:
        validate_project_status_transition(ProjectStatus.CANCELLED, ProjectStatus.ACTIVE)
    assert "terminal state" in str(exc_cancelled.value)

    # COMPLETED cannot reopen to ACTIVE
    with pytest.raises(InvariantViolationException):
        validate_project_status_transition(ProjectStatus.COMPLETED, ProjectStatus.ACTIVE)
