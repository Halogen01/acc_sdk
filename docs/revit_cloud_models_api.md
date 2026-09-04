# Revit Cloud Model linked files

Autodesk changed Revit Cloud Model downloads so that unpublished linked models
are no longer bundled into the normal download for affected published versions.
The additive `acc.revit_cloud_models` service exposes the ACC RCM linked-files
endpoint without changing the legacy Data Management interface.

## Authentication

RCM linked-file retrieval requires a three-legged access token for a user who
can access the project and published model. The SDK deliberately does not fall
back to its two-legged token, even when both token types exist.

Configure credentials through the existing `Authentication` object and its
server-side token store. Never include access tokens or returned signed URLs in
source code, browser storage, or application logs.

## Retrieve one page

Use the complete Data Management version URN and retain the Data Management
project ID as returned, including its `b.` prefix:

```python
linked_files = acc.revit_cloud_models.get_linked_files(
    project_id="b.project-guid",
    version_id="urn:adsk.wipprod:fs.file:vf.file-id?version=12",
)

results = linked_files.get("results") or []
pagination = linked_files.get("pagination") or {}
```

By default, `include_host=False` requests linked models only. Set it to `True`
when the host model should also appear in the results.

Each result can contain `modelName`, `signedUrl`, `itemId`, `versionId`, and
`publishStatus`. Autodesk documents these fields as nullable, so integrations
must check a value before using it.

## Retrieve every page safely

```python
results = acc.revit_cloud_models.get_all_linked_files(
    project_id="b.project-guid",
    version_id="urn:adsk.wipprod:fs.file:vf.file-id?version=12",
    max_pages=20,
    max_results=2_000,
)
```

The all-page method follows Autodesk's returned `nextUrl` only when it remains
on the HTTPS Autodesk API origin and the same project/version endpoint. It also
detects pagination cycles and enforces configurable hard limits. Library-wide
ceilings are 100 pages and 100,000 results; defaults are 100 pages and 10,000
results.

## Download a returned file

Treat `signedUrl` as a short-lived secret and stream it directly to a controlled
destination with an application-specific size limit:

```python
linked_file = results[0]
signed_url = linked_file.get("signedUrl")
if signed_url:
    acc.data_management.download_from_signed_url(
        signed_url,
        destination_path="C:/downloads/Structure.rvt",
        max_bytes=4 * 1024 * 1024 * 1024,
    )
```

The streaming helper uses bounded chunks, enforces `max_bytes` both before and
during transfer, writes to a temporary file, and atomically replaces the final
destination only after success.

The implementation follows Autodesk's current
[official linked-files sample](https://github.com/autodesk-platform-services/aps-dotnet-blazor-samples/blob/aae7e5c359373466b9765b0a661c8fd6cf491cbb/Services/AccLinkedFilesService.cs)
and the
[RCM download change notice](https://aps.autodesk.com/blog/changes-are-coming-revit-cloud-model-downloads-autodeskbim-360-docs-starting-february-15-2026).
