# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Built-in OIDC login: authorization code flow with PKCE and ID token validation, using Authlib (ADR-026)."""

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests
from authlib.common.errors import AuthlibBaseError
from authlib.common.security import generate_token
from authlib.integrations.requests_client import OAuth2Session
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry

from chronowarden.config import OidcConfig

logger = logging.getLogger("uvicorn.error")

_TIMEOUT = 10
_LEEWAY = 60
# Discovery and keys are re-read after this long, so key rotation at the IdP needs no restart
_CACHE_SECONDS = 3600


class OidcError(Exception):
    """The login could not be completed or the ID token is not valid."""


@dataclass(frozen=True)
class LoginStart:
    """Where to send the browser, and what the callback must check."""

    url: str
    state: str
    code_verifier: str
    nonce: str


@dataclass(frozen=True)
class OidcUser:
    """The user an ID token names."""

    name: str
    email: Optional[str]
    groups: list[str]


class OidcClient:
    """Talks to one OIDC provider; discovery and its keys are cached."""

    def __init__(self, config: OidcConfig) -> None:
        """
        Args:
            config: The `auth.oidc` settings.
        """
        self.config = config
        self._metadata: Optional[dict[str, Any]] = None
        self._keys: Optional[KeySet] = None
        self._fetched_at = 0.0

    def _get_json(self, url: str) -> dict[str, Any]:
        """GET a JSON document from the provider."""
        try:
            response = requests.get(url, timeout=_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise OidcError(f"Cannot read {url}: {exc}") from exc

    def _session(self) -> OAuth2Session:
        """An OAuth 2 client for one login."""
        secret = self.config.resolve_client_secret()
        return OAuth2Session(
            client_id=self.config.client_id,
            client_secret=secret,
            token_endpoint_auth_method="client_secret_basic" if secret else "none",
            scope=" ".join(self.config.scopes),
            redirect_uri=self.config.redirect_uri,
            code_challenge_method="S256",
            default_timeout=_TIMEOUT,
        )

    def metadata(self, refresh: bool = False) -> dict[str, Any]:
        """The provider's discovery document, checked against the configured issuer."""
        if refresh or self._metadata is None or time.monotonic() - self._fetched_at > _CACHE_SECONDS:
            metadata = self._get_json(self.config.issuer.rstrip("/") + "/.well-known/openid-configuration")
            if metadata.get("issuer") != self.config.issuer:
                raise OidcError(f"Discovery names issuer {metadata.get('issuer')!r}, not {self.config.issuer!r}")
            self._metadata, self._keys, self._fetched_at = metadata, None, time.monotonic()
        return self._metadata

    def _key_set(self, refresh: bool = False) -> KeySet:
        """The provider's signing keys."""
        if refresh or self._keys is None:
            self._keys = KeySet.import_key_set(self._get_json(self.metadata()["jwks_uri"]))
        return self._keys

    def start_login(self) -> LoginStart:
        """
        Build the authorization URL for a new login.

        Returns:
            The URL plus the state, PKCE verifier and nonce to keep until the callback.
        """
        state, verifier, nonce = generate_token(32), generate_token(64), generate_token(32)
        url, _ = self._session().create_authorization_url(
            self.metadata()["authorization_endpoint"], state=state, code_verifier=verifier, nonce=nonce
        )
        return LoginStart(url=url, state=state, code_verifier=verifier, nonce=nonce)

    def finish_login(self, code: str, code_verifier: str, nonce: str) -> OidcUser:
        """
        Exchange the code for tokens and validate the ID token.

        Raises:
            OidcError: If the exchange fails or the ID token is invalid (signature, issuer, audience, expiry, nonce).
        """
        try:
            token = self._session().fetch_token(
                self.metadata()["token_endpoint"],
                grant_type="authorization_code",
                code=code,
                code_verifier=code_verifier,
            )
        except (requests.RequestException, ValueError, AuthlibBaseError) as exc:
            raise OidcError(f"Token exchange failed: {exc}") from exc
        id_token = token.get("id_token")
        if not id_token:
            raise OidcError("The provider returned no ID token")
        return self._user(self.validate_id_token(id_token, nonce))

    def validate_id_token(self, id_token: str, nonce: str) -> dict[str, Any]:
        """
        Check the ID token's signature and claims.

        Returns:
            Its claims.

        Raises:
            OidcError: If anything doesn't match.
        """
        algorithms = [a for a in self.metadata().get("id_token_signing_alg_values_supported", ["RS256"]) if a != "none"]
        try:
            try:
                decoded = jwt.decode(id_token, self._key_set(), algorithms=algorithms)
            except JoseError:
                # The provider may have rotated its keys since we fetched them
                decoded = jwt.decode(id_token, self._key_set(refresh=True), algorithms=algorithms)
            claims = decoded.claims
            JWTClaimsRegistry(
                leeway=_LEEWAY,
                iss={"essential": True, "value": self.config.issuer},
                sub={"essential": True},
                exp={"essential": True},
                nonce={"essential": True, "value": nonce},
            ).validate(claims)
        except (JoseError, ValueError) as exc:
            raise OidcError(f"Invalid ID token: {exc}") from exc
        audience = claims.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]
        if self.config.client_id not in audiences:
            raise OidcError("The ID token is not meant for this client")
        if len(audiences) > 1 and claims.get("azp") != self.config.client_id:
            raise OidcError("The ID token was issued to another party")
        return claims

    def _user(self, claims: dict[str, Any]) -> OidcUser:
        """Name, verified email and groups from the claims."""
        email = claims.get("email") if claims.get("email_verified") is not False else None
        groups = claims.get(self.config.groups_claim) or []
        if isinstance(groups, str):
            groups = [groups]
        name = claims.get(self.config.username_claim) or email or claims["sub"]
        return OidcUser(name=str(name), email=email, groups=[str(g) for g in groups])
