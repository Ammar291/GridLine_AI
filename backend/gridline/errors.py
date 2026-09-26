"""Typed exceptions raised by the simulation and mapped to HTTP codes by the API."""


class SimulationError(Exception):
    """Base class for simulation errors."""


class InvalidTransition(SimulationError):
    """The runner cannot perform this transition from its current state (HTTP 409)."""


class NotInjectable(SimulationError):
    """The event type is an observation or system event and cannot be injected (HTTP 422)."""


class UnknownAsset(SimulationError):
    """An id in a payload or location does not exist in the city (HTTP 422)."""


class UnknownScenario(SimulationError):
    """No scenario is registered under this name (HTTP 422)."""


class InvalidPayload(SimulationError, ValueError):
    """A well-formed payload contradicts the city, e.g. more occupied beds than exist (HTTP 422)."""
