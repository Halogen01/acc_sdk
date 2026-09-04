# ACC SDK Repository Audit and Compatibility Record

**Date:** 3 September 2026

**Repository:** `Halogen01/acc_sdk`

**Local version at review:** `0.5.15`

**Local commit at review:** `219b423a7d4bdb89cf6cbe721a99822f2513e3e5`

## Purpose

This document records the discussion and findings from a review of this fork of
`acc_sdk`. The intended use is as a shared package for integrations that access,
retrieve, and save documents across multiple Autodesk Forma/Autodesk Construction
Cloud projects.

The review covered:

- The current local `acc_sdk` source.
- The latest `realdanielbyrne/acc_sdk` upstream repository state.
- Current Autodesk Platform Services authentication, Data Management, Object
  Storage Service, regional-data, and Revit Cloud Model guidance.
- Existing usage by `Halogen01/ACC-Bulk-Manager`.
- Existing usage by `PeritasAus/Peritas-Portal`.

This fork is intentionally maintained independently and must not be pushed back
to `realdanielbyrne/acc_sdk`.

## Questions considered

1. Is the current repository suitable as the package foundation for multiple
   document integrations?
2. What has changed in Autodesk authentication and document-retrieval workflows?
3. Can the repository be cleaned up without breaking ACC-Bulk-Manager or
   Peritas-Portal?

## Executive conclusion

The current package should **not be used unchanged** as the foundation for new
production document integrations.

It can, however, be developed into a suitable internal package while preserving
the public interface used by ACC-Bulk-Manager and Peritas-Portal. The existing
applications use a relatively small administration-focused subset of the SDK and
do not currently depend on the incomplete Data Management document-transfer
implementation. This makes a compatibility-preserving cleanup practical.

The recommended approach is to retain the existing `Acc` and `Authentication`
interfaces as a legacy compatibility facade while replacing and extending their
internals behind contract tests.

## Upstream comparison

At the time of review:

- The local fork was 17 commits ahead of and one commit behind upstream.
- The newer upstream commit only added ignore-file configuration.
- No newer upstream work corrected authentication or document-management issues.
- The public PyPI release remained `acc-sdk 0.5.14`, published on 9 February
  2026.
- The local fork's additions were primarily packaging and account/project-user
  administration changes rather than document-transfer improvements.

The upstream repository remains useful as historical reference, but should be
configured as fetch-only. Development and releases should remain under the
Halogen/Peritas fork.

## Authentication findings

The package uses Autodesk Authentication v2 endpoints, but several areas require
hardening:

- Confidential-client token requests send the client ID and secret in the form
  body. Autodesk's current specification permits this as a fallback but
  recommends HTTP Basic authentication for traditional web and server-to-server
  applications.
- `Authentication.__init__` deletes expired stored tokens before they can be
  refreshed. This can prevent refresh when an `Authentication` object is rebuilt
  for a later web request.
- `session={}` is a shared mutable default.
- The documented use of a Flask session can expose tokens to client-side cookie
  storage unless the consuming app explicitly uses a server-side session store.
- OAuth `state` generation and callback verification are not provided by default.
- The fallback logout path contains `logoutout` instead of `logout`.
- `AccBase.get_private_token()` always chooses a two-legged token before a
  three-legged token. This makes token context implicit and can select the wrong
  identity for user-context operations.
- Secure Service Account authentication is not implemented.
- Network calls made during authentication construction lack consistent timeout,
  retry, and failure-isolation behaviour.

For new unattended multi-project integrations, Autodesk Secure Service Accounts
should be investigated as the preferred authentication mechanism. SSA became
generally available in September 2025 and supplies a controlled user-context
identity without interactive login or long-lived refresh-token workarounds.

## Document retrieval and storage findings

The current Data Management implementation is not a complete document client:

- At least 22 Data Management URLs contain literal colon placeholders such as
  `hubs/:{hub_id}` and `projects/:{project_id}`. These produce incorrect request
  paths.
- `get_hubs()` uses the invalid header name `Authorization:`.
- Several other methods omit the required `Bearer` prefix.
- `get_version()` extracts the response's `data` object and then attempts to
  extract `data` from it again, normally returning an empty dictionary.
- Some methods construct query parameters but do not pass them to `requests`.
- Pagination behaviour is inconsistent.
- There is no general signed-S3 download operation or streamed file-to-disk
  helper.
- General document uploads do not implement the complete storage creation,
  signed upload, transfer, completion, and item/version creation workflow.
- The Sheets upload helpers are PDF-specific and do not provide a robust
  multipart implementation.
- Object keys are not consistently URL encoded.
- There are approximately 130 direct `requests` calls, but only one explicit
  timeout was found.
- No Data Management tests were found.

Current Autodesk OSS document transfer uses direct-to-S3 operations:

### Download

1. Navigate hubs, projects, folders, items, and versions using Data Management.
2. Resolve the version's OSS storage URN.
3. Extract and URL encode the bucket key and object key.
4. Request an OSS v2 `signeds3download` URL.
5. Stream the binary directly from S3.

### Upload

1. Create a Data Management storage location.
2. Request one or more OSS v2 signed-S3 upload URLs.
3. Upload the file or its multipart chunks to S3.
4. Complete the upload using the returned upload key and validation data.
5. Create a new item or version referencing the completed storage object.

Legacy OSS v1 upload and download endpoints stopped being a valid foundation
after 31 October 2025.

## Other Autodesk changes relevant to this fork

### Australia region

The supported region value is `AUS`; `APAC` is deprecated. New Data Management,
OSS, Model Derivative, and related code should accept and propagate current
region values without assuming US storage.

### Revit Cloud Models

For Revit Cloud Models published on or after 15 February 2026, the normal
download no longer includes unpublished linked models in a ZIP archive. An
integration needing linked files must support:

```text
GET /construction/rcm/v1/projects/{projectId}/published-versions/{versionId}/linked-files
```

The current package does not expose this workflow.

## Existing application compatibility contract

### Shared imports and construction

Both applications rely on:

```python
from acc_sdk import Acc, Authentication

auth_client = Authentication(
    client_id=client_id,
    client_secret=client_secret,
    admin_email=user_email,
    session={},
    callback_url=callback_url,
)
auth_client.request_2legged_token(scopes=scopes)
acc = Acc(auth_client=auth_client, account_id=account_id)
```

The following public objects, signatures, keyword arguments, dictionary/list
return shapes, and exception behaviour must remain compatible during cleanup.

### Projects

- `acc.projects.get_projects(...)`
- `acc.projects.get_all_active_projects(...)`
- `acc.projects.get_project(...)`

### Account users

- `acc.account_users.get_users(...)`
- `acc.account_users.get_users_search(...)`
- `acc.account_users.get_user(...)`
- `acc.account_users.get_user_by_email(...)`
- `acc.account_users.get_userid_projects(...)`
- `acc.account_users.get_userid_products(...)`

### Project users

- `acc.project_users.get_users(...)`
- `acc.project_users.post_user(...)`
- `acc.project_users.delete_user(...)`
- `acc.project_users.patch_project_users(...)`
- `acc.project_users.productmember`
- `acc.project_users.productadmin`
- The `suppressAdministrativeEmails` request property.

Peritas-Portal also interprets HTTP 409 or error text containing `already` as an
existing project membership. Compatible exception objects must therefore retain
an accessible response/status code or equivalent legacy behaviour.

Neither reviewed application currently calls `acc.data_management`, so that
module can be corrected and extended with relatively low compatibility risk.

## Dependency-resolution risk

The most immediate compatibility risk is inconsistent dependency pinning rather
than the proposed cleanup.

At review time, Peritas-Portal referenced:

- A floating Halogen Git dependency in `pyproject.toml`.
- Commit `c0487a7` in `uv.lock`.
- Commit `219b423` in its deployment `requirements.txt`.

ACC-Bulk-Manager referenced:

- A floating Halogen Git dependency in `pyproject.toml`.
- Commit `b3e6f64` in `uv.lock`.
- PyPI version `0.5.10` in `requirements.txt`.

Different installation paths can therefore deploy different SDK behaviour.
Both applications should first be aligned to one immutable Halogen tag or commit.

## Compatibility-preserving cleanup plan

### Phase 1: Establish a baseline

1. Tag the current known-working fork, for example
   `halogen-compat-0.5.15`.
2. Pin both consuming applications to that immutable tag or commit.
3. Record the supported Python versions and deployment installation method.

### Phase 2: Add consumer contract tests

Before refactoring, add mocked tests for:

- Two-legged token acquisition and renewal.
- `Acc` construction with `admin_email` and `account_id`.
- Project listing, filtering, lookup, and pagination.
- Account-user listing, lookup, and expected snake-case fields.
- Project-user listing, creation, updating, and deletion.
- `suppressAdministrativeEmails`.
- The `productmember` and `productadmin` values.
- HTTP 409 existing-member behaviour.
- Existing dictionary/list response shapes.

A small credential-backed suite should also run against a non-production ACC
project before a release is promoted.

### Phase 3: Refactor behind the existing facade

Introduce internal components for:

- Shared HTTP transport and connection pooling.
- Default connection and read timeouts.
- Rate-limit and transient-error handling with `Retry-After` support.
- Safe retry rules that do not duplicate non-idempotent mutations.
- Consistent authentication headers.
- URL/path/query encoding.
- Token storage and explicit token-provider selection.
- Region handling.
- Structured logging with token and signed-URL redaction.

The existing `Acc`, `Authentication`, service properties, methods, and return
shapes should delegate to these internals unchanged.

### Phase 4: Rebuild document operations additively

1. Correct the existing Data Management paths and response parsing.
2. Implement tested folder/item/version navigation.
3. Add OSS v2 signed-S3 streaming downloads.
4. Add single and multipart signed-S3 uploads.
5. Add complete create-item and create-version workflows.
6. Add `AUS` and other current region values.
7. Add RCM linked-file retrieval.
8. Add SSA as a new explicit token provider.

These capabilities should initially be new methods. Existing methods should not
silently change return shapes or token-selection behaviour.

**Progress recorded 4 September 2026:** Items 1 through 7 are complete in the
Halogen fork. The legacy Data Management methods remain available, while tested
additive methods now provide corrected navigation, OSS v2 streamed downloads,
single/multipart signed-S3 uploads, storage creation, and complete new-item and
new-version upload workflows. Current Autodesk region values and non-mutating
hub-region detection are also available, with `US` remaining the default. The
RCM service retrieves linked files for published Revit Cloud Model versions with
bounded, same-origin pagination. Item 8 remains planned.

### Phase 5: Deliberate migration

New explicit construction APIs may be introduced, for example:

```python
Authentication.for_client_credentials(...)
Authentication.for_service_account(...)
Authentication.for_authorization_code(...)
```

The current constructor should remain available until both consumers have been
migrated and verified. Any removal or semantic change should occur only in a
clearly versioned breaking release.

## Fork governance

- Keep `origin` pointing to `Halogen01/acc_sdk`.
- Keep the original upstream remote fetch-only, with an invalid or disabled push
  URL.
- Optionally rename it to `reference-upstream` to clarify its role.
- Add a maintained-fork notice to the README and package metadata.
- Preserve the original MIT licence and copyright notice.
- Release only using Halogen/Peritas-controlled immutable tags or a private
  package registry.
- Require the SDK tests and both consumer contract suites before creating a
  release tag.

## Final recommendation

Retain and clean up the Halogen fork. Do not replace the SDK inside the existing
applications as part of the first cleanup pass.

The safe sequence is:

1. Align and pin dependencies.
2. Freeze the consumer-facing contract in tests.
3. Refactor authentication and HTTP internals behind the existing facade.
4. Repair and extend Data Management and OSS document workflows additively.
5. Introduce SSA and explicit token-provider selection.
6. Migrate existing applications deliberately before retiring legacy behaviour.

## References

- [Halogen01/acc_sdk](https://github.com/Halogen01/acc_sdk)
- [realdanielbyrne/acc_sdk](https://github.com/realdanielbyrne/acc_sdk)
- [Halogen01/ACC-Bulk-Manager](https://github.com/Halogen01/ACC-Bulk-Manager)
- [PeritasAus/Peritas-Portal](https://github.com/PeritasAus/Peritas-Portal)
- [Autodesk APS OpenAPI specifications](https://github.com/autodesk-platform-services/aps-sdk-openapi)
- [Secure Service Accounts general availability](https://aps.autodesk.com/blog/update-secure-service-accounts-ssa-goes-ga)
- [OSS v1 endpoint deprecation](https://aps.autodesk.com/blog/object-storage-service-oss-api-deprecating-v1-endpoints)
- [Australia region changes](https://aps.autodesk.com/blog/changes-are-coming-autodesk-platform-services-aps-australia-region)
- [Revit Cloud Model download changes](https://aps.autodesk.com/blog/changes-are-coming-revit-cloud-model-downloads-autodeskbim-360-docs-starting-february-15-2026)
- [acc-sdk on PyPI](https://pypi.org/project/acc-sdk/)

## Verification notes

The local package compiled successfully during the review. No live Autodesk API
requests were made with project credentials. The review environment did not have
pytest installed for this repository, and the repository contained no dedicated
Data Management test module.
