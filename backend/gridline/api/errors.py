"""Map the simulation's typed exceptions to HTTP (spec §10): 409 for transitions, 422 for bad input."""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from gridline.errors import InvalidPayload, InvalidTransition, NotInjectable, UnknownAsset, UnknownScenario

UNPROCESSABLE: tuple[type[Exception], ...] = (NotInjectable, UnknownAsset, UnknownScenario, InvalidPayload)


async def _conflict(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


async def _unprocessable(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


async def _invalid_payload(_: Request, exc: Exception) -> JSONResponse:
    """A payload that fails its event type's model inside the engine (not a FastAPI body error)."""
    assert isinstance(exc, ValidationError)
    errors = exc.errors(include_url=False, include_context=False, include_input=False)
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(InvalidTransition, _conflict)
    for exc_type in UNPROCESSABLE:
        app.add_exception_handler(exc_type, _unprocessable)
    app.add_exception_handler(ValidationError, _invalid_payload)
