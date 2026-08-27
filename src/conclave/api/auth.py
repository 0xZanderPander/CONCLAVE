import hmac
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Protocol

from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict

ALL_CALLER_SCOPES = frozenset(
    {
        "reviews:submit",
        "reviews:read",
        "events:read",
        "feedback:submit",
        "feedback:read",
        "evaluations:read",
        "operations:manage",
    }
)


@dataclass(frozen=True, slots=True)
class CallerPrincipal:
    caller_id: str | None
    scopes: frozenset[str]


class CallerAuthenticator(Protocol):
    def authenticate(
        self,
        authorization: str | None,
        required_scope: str,
    ) -> CallerPrincipal:
        """Authenticate one caller without persisting or logging its secret."""


class LocalFixtureAuthenticator:
    def authenticate(
        self,
        authorization: str | None,
        required_scope: str,
    ) -> CallerPrincipal:
        del authorization, required_scope
        return CallerPrincipal(caller_id=None, scopes=ALL_CALLER_SCOPES)


class StaticCallerCredential(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    token: str
    scopes: frozenset[str]


class StaticBearerAuthenticator:
    def __init__(self, credentials: Mapping[str, StaticCallerCredential]) -> None:
        if not credentials:
            raise ValueError("static bearer authentication requires caller credentials")
        self._credentials = dict(credentials)

    @classmethod
    def from_json(cls, document: str) -> "StaticBearerAuthenticator":
        parsed = json.loads(document)
        if not isinstance(parsed, dict):
            raise ValueError("caller credential configuration must be an object")
        credentials = {
            str(caller_id): StaticCallerCredential.model_validate(value)
            for caller_id, value in parsed.items()
        }
        return cls(credentials)

    def authenticate(
        self,
        authorization: str | None,
        required_scope: str,
    ) -> CallerPrincipal:
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="bearer authentication required")
        supplied = authorization.removeprefix("Bearer ").strip()
        match: tuple[str, StaticCallerCredential] | None = None
        for caller_id, credential in self._credentials.items():
            if hmac.compare_digest(supplied, credential.token):
                match = (caller_id, credential)
        if match is None:
            raise HTTPException(status_code=401, detail="invalid bearer credential")
        caller_id, credential = match
        if required_scope not in credential.scopes:
            raise HTTPException(status_code=403, detail="caller scope is not authorized")
        return CallerPrincipal(caller_id=caller_id, scopes=credential.scopes)


def scope_dependency(
    authenticator: CallerAuthenticator,
    required_scope: str,
) -> Callable[..., CallerPrincipal]:
    def authenticate(
        authorization: Annotated[str | None, Header()] = None,
    ) -> CallerPrincipal:
        return authenticator.authenticate(authorization, required_scope)

    return authenticate
