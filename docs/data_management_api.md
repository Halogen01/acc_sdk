# Data Management file workflows

The Halogen/Peritas fork provides additive Data Management methods for current
Autodesk OSS v2 document transfers. Existing methods remain available with their
previous signatures and return shapes for ACC-Bulk-Manager and Peritas-Portal.

The new write methods use the SDK's private token provider and shared HTTP
transport. Callers must configure authentication with the Autodesk scopes needed
for the operation, including Data Management create/write access.

## Complete uploads

Create a new ACC file item and its first version:

```python
result = acc.data_management.upload_new_file_item(
    project_id="project-guid",
    folder_id="urn:adsk.wipprod:fs.folder:co.folder-id",
    source_path="C:/exports/model.rvt",
    max_bytes=2 * 1024 * 1024 * 1024,
)

item_document = result["item"]
```

Create the next version of an existing item:

```python
result = acc.data_management.upload_new_file_version(
    project_id="b.project-guid",
    item_id="urn:adsk.wipprod:dm.lineage:item-id",
    source_path="C:/exports/model.rvt",
    file_name="model.rvt",
    max_bytes=2 * 1024 * 1024 * 1024,
)

version_document = result["version"]
```

Both workflows return the created storage resource, OSS completion response,
and created item or version document. A project ID without the `b.` prefix is
normalized automatically.

The ACC/BIM 360 extension types are the defaults:

- `items:autodesk.bim360:File`
- `versions:autodesk.bim360:File`

Callers targeting another Autodesk Data Management service can override
`item_extension_type`, `version_extension_type`, and
`extension_schema_version` with values documented for that service.

## Individual write operations

The component operations are public when an integration needs to control the
workflow itself:

- `create_storage_location(...)` creates storage for a folder or item and
  returns its JSON:API resource.
- `upload_file_to_oss(...)` performs a single or multipart signed-S3 upload and
  completes it.
- `create_file_item(...)` creates an item and first version from completed
  storage and returns the complete JSON:API document.
- `create_file_version(...)` creates the server-assigned next version and
  returns the complete JSON:API document.

## Bounds and failure behaviour

- Network calls use finite connect/read timeouts through the shared transport.
- Non-idempotent storage, item, version, and completion POSTs are not retried
  automatically.
- Signed-S3 transfer retries and URL refreshes are bounded and configurable.
- Multipart parts are bounded from 5 MiB through 5 GiB, with at most 10,000
  parts; signed URLs are requested in batches of at most 25.
- `max_bytes` can enforce a caller-specific upload size limit before any remote
  storage is created.
- File paths, names, IDs, upload limits, extension types, and signed-URL options
  are validated before the complete workflow creates storage.

If a remote operation fails after storage creation or upload completion, the
completed Autodesk resource may remain. The SDK deliberately does not delete it
automatically: callers can log the exception and reconcile the partial result
according to their project policy without risking destructive cleanup.

When acting in a three-legged user context, pass `user_id` to include Autodesk's
`x-user-id` header on Data Management mutations. Tokens, signed URLs, and other
credentials must not be logged or committed to source control.

Refer to Autodesk's current
[Data Management API](https://aps.autodesk.com/en/docs/data/v2/developers_guide/overview/)
and [Object Storage Service](https://aps.autodesk.com/en/docs/data/v2/developers_guide/oss-intro/)
documentation when selecting scopes and service-specific extension types.

## Region handling

US is the SDK default and requires no change to the normal Data Management or
signed-S3 workflows. Autodesk routes those requests from the hub identifier and
OSS storage URN; the SDK does not add an unsupported region header to them.

The public region model contains Autodesk's current values:

```python
from acc_sdk import ApsRegion, normalize_aps_region

region = normalize_aps_region()       # ApsRegion.US
region = normalize_aps_region("aus")  # ApsRegion.AUS
```

After retrieving a hub, an integration can read its reported region without
changing the response resource:

```python
hub = acc.data_management.get_hub("account-id")
region = acc.data_management.get_hub_region(hub)  # defaults to US if omitted
```

Supported values are `US`, `EMEA`, `AUS`, `CAN`, `DEU`, `IND`, `JPN`, and
`GBR`. Deprecated or undocumented aliases such as `APAC` and `EU` are rejected
instead of being silently remapped. Pass `str(region)` only to an Autodesk API
operation that explicitly documents a region header, query parameter, or body
field, such as OSS bucket creation or Model Derivative operations.
