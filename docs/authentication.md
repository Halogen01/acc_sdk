# Authentication API

The `Authentication` class provides methods to manage authentication with the
Autodesk Construction Cloud (ACC) API. It supports two-legged, interactive
three-legged, and Secure Service Account (SSA) flows.

## Initialize Authentication

Create a new instance of the Authentication client with your credentials.

```python
auth_client = Authentication(
    client_id="your_client_id",
    client_secret="your_client_secret",
    admin_email="admin@example.com",  # Optional, for 2-legged user impersonation
    session={},  # Flask session or dictionary to store tokens
    callback_url="http://your-app/callback",  # Required for 3-legged flow
    logout_url="http://your-app/logout"  # Optional, for logout redirect
)
```

## 2-Legged Authentication

Obtain a client credentials token for server-to-server operations.

```python
scopes = [
    "data:read",
    "data:write",
    "account:read",
    "account:write"
]
token = auth_client.request_2legged_token(scopes=scopes)
```

## 3-Legged Authentication

The 3-legged authentication process involves multiple steps:

1. First, generate the authorization URL that the user will visit:

```python
# Define the scopes needed for your application
scopes = [
    "user-profile:read",
    "data:read",
    "data:write",
    "account:read",
    "account:write"
]

# Get the authorization URL
auth_url = auth_client.get_authorization_url(scopes=scopes)
```

2. The user visits the authorization URL and authenticates with Autodesk. Upon successful authentication, Autodesk redirects the user to your callback URL with an authorization code.

3. In your callback handler, exchange the authorization code for access and refresh tokens:

```python
# Exchange the authorization code for tokens
token_data = auth_client.request_authcode_access_token(
    code=request.args.get("code"),  # The code from the callback
    scopes=scopes
)
```

4. When the access token expires, use the refresh token to obtain a new access token:

```python
# Refresh the token with optional subset of scopes
new_token = auth_client.request_private_refresh_token(
    scopes=["data:read", "data:write"]  # Optional subset of original scopes
)
```

For a complete example of implementing 3-legged authentication in a web application, see the Flask example in the main README.

## Secure Service Account Authentication

Use an SSA for unattended integrations that need a user-context token. The SSA
must already be linked to the APS server-to-server application, and its email
must have the required membership and permissions in each target ACC project.

Keep the client secret and RSA private key in a server-side secret store. This
example uses environment variables and a base64-encoded PEM value so no key is
committed to source control:

```python
import base64
import os

from acc_sdk import Acc, Authentication

auth_client = Authentication.for_service_account(
    client_id=os.environ["APS_CLIENT_ID"],
    client_secret=os.environ["APS_CLIENT_SECRET"],
    service_account_id=os.environ["APS_SSA_ID"],
    key_id=os.environ["APS_SSA_KEY_ID"],
    private_key=base64.b64decode(os.environ["APS_SSA_KEY_BASE64"]),
    scopes=["data:read", "data:write", "data:create"],
    session={},
)

acc = Acc(auth_client=auth_client, account_id=os.environ["APS_ACCOUNT_ID"])
```

Construction is lazy: it does not exchange an assertion immediately. The first
call that requests a three-legged token creates a five-minute RS256 assertion
and exchanges it for an SSA user-context token. The token is cached in the
session and reissued when it has no more than 60 seconds remaining. The client
secret, private key, and signed assertion are never written to the token session.

The legacy constructor and its token-selection order are unchanged. On an
object returned by `for_service_account`, `get_3legged_token()` explicitly uses
the configured SSA provider. `request_service_account_token()` is public for
callers that need to force an immediate exchange.

SSA does not take an Autodesk data-region parameter. A US hub therefore uses
the same authentication flow; pass or detect region values in the relevant
Data Management and OSS operations.

The implementation follows Autodesk's
[canonical SSA OpenAPI specification](https://github.com/autodesk-platform-services/aps-sdk-openapi/blob/main/secureserviceaccount/secureServiceAccount.yaml)
and [official Python SSA sample](https://github.com/autodesk-platform-services/aps-mcp-server-python/tree/main/mcp_server_ssa).

## Token Management

Manage and validate your authentication tokens.

```python
# Check if a token is valid
is_valid = auth_client.is_authorized("accapi_3legged")

# Get remaining time until token expiration
expires_in = auth_client.expires_in("accapi_3legged")

# Revoke a token
auth_client.revoke_private_token("accapi_3legged")

# Clear all tokens from session
auth_client.clear_all_tokens()
```

## User Profile Information

Retrieve information about the authenticated user.

```python
# Get user profile information
user_info = auth_client.get_user_info()
print(user_info)
```

## Token Types and Scopes

The Authentication class supports various token types and scopes:

- **2-Legged Tokens**: For server-to-server operations
- **3-Legged Tokens**: For user-specific operations
- **Secure Service Account Tokens**: Non-interactive user-context tokens for an SSA identity
- **Public Tokens**: Without client secret (PKCE flow)
- **Private Tokens**: With client secret

Common scopes include:

- `user-profile:read`: Access user profile information
- `data:read` and `data:write`: Access project data
- `account:read` and `account:write`: Manage account settings
- `viewables:read`: Access viewable files
