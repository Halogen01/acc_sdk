# Phase 5 Explicit Authentication Design

**Status:** Agreed 7 September 2026

## Purpose

Complete the SDK authentication construction surface before migrating
ACC-Bulk-Manager or Peritas-Portal. New integrations should be able to select an
authentication provider explicitly, while the legacy `Authentication(...)`
constructor and its token-selection behavior remain compatible.

The SDK will continue to expose `Authentication` as its public compatibility
facade. This phase adds thin, keyword-only construction APIs rather than a new
provider class hierarchy.

## Public API

### Client credentials

```python
Authentication.for_client_credentials(
    client_id=...,
    client_secret=...,
    scopes=[...],
    session=None,
    admin_email="",
    token_name="accapi_2legged",
)
```

The factory stores an immutable copy of the requested scopes and configures a
lazy two-legged provider. The first call to `get_2legged_token()` obtains and
caches the token under the configured name. Existing renewal behavior is reused.
`request_2legged_token()` remains available when immediate acquisition is
required.

### Authorization code

```python
Authentication.for_authorization_code(
    client_id=...,
    callback_url=...,
    client_secret="",
    session=None,
    admin_email="",
    logout_url="",
)
```

The factory validates the authorization-code configuration and then exposes the
existing authorization URL, confidential-client exchange, public PKCE, private
PKCE, and refresh operations. The client secret remains optional so public PKCE
clients are supported.

### Secure Service Account

The existing `Authentication.for_service_account(...)` factory remains the
explicit provider for unattended user-context workflows. Its lazy assertion
exchange and renewal behavior are unchanged.

## Compatibility and token selection

Factory-created clients select their configured provider explicitly. A
client-credentials client reads only its configured token name when
`get_2legged_token()` is called. An authorization-code client continues to use
the existing three-legged token operations.

Objects created through the legacy constructor retain the current token
discovery order. In particular, `AccBase.get_private_token()` continues to
prefer an available two-legged token before a three-legged token. Existing
constructor parameters, public methods, session token shapes, and consumer
return values remain unchanged.

## Validation and errors

Factory validation occurs before token acquisition:

- Required identifiers, credentials, callback URLs, scopes, and token names
  must be non-empty.
- A scope collection must be an iterable of non-empty strings; a single string
  is rejected.
- Scope inputs are copied and are not mutated by the factory or renewal path.
- `session=None` creates a new object-owned dictionary, avoiding shared state.

HTTP authentication failures must preserve the underlying `requests` response
and status code. Token calls continue to use the shared five-second connection
and thirty-second read timeout. Automatic retries are not added to token POST
requests.

## OAuth security responsibilities

New authorization-code integrations must generate a cryptographically random
OAuth `state`, store it in a server-side session, and compare it before
exchanging the callback code. PKCE clients must likewise keep the verifier
server-side until the callback.

The SDK will continue to forward `state`, `code_challenge`, and related
authorization parameters. It will not silently choose a Flask session storage
model or take ownership of application request state. Documentation must warn
against storing OAuth tokens or verifiers in client-side cookie sessions.

Client secrets remain server-side and are sent to Autodesk only through HTTP
Basic authentication. Secrets must not be copied into token dictionaries,
logs, examples, or browser-delivered data.

## Verification

Mocked contracts will cover:

- Lazy client-credentials acquisition and expiry renewal.
- Custom token names and caller scope immutability.
- Confidential and public-PKCE authorization-code construction.
- Required-field and invalid-scope failures before token requests.
- Isolation between separately constructed default sessions.
- Unchanged legacy construction, session shapes, and token precedence.
- Unchanged Secure Service Account behavior.

The full offline SDK suite, consumer compatibility contracts, compilation,
package metadata, whitespace checks, and credential-pattern checks must pass.
A credential-backed non-production ACC smoke test remains a release-promotion
requirement and is not replaced by mocked tests.

## Release and consumer migration

After the explicit factories are merged, the package will be versioned as
`0.6.0` and assigned an immutable Halogen-controlled release tag. Peritas-Portal
will then be migrated and verified against that exact tag. ACC-Bulk-Manager will
follow after its active repository and deployment path are confirmed.

The original `realdanielbyrne/acc_sdk` repository remains reference-only and
must not receive branches, tags, or releases from this work.

## Out of scope

- Removing or changing the legacy constructor.
- Changing `AccBase` token precedence for legacy clients.
- Replacing the existing token session abstraction.
- Provisioning SSA identities or rotating SSA keys.
- Migrating either consumer before the `0.6.0` SDK baseline is verified.
