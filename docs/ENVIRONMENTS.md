# Environments and asset bundles

Projects carry an environment label (`dev`, `staging` or `prod`) and assets
move between projects as JSON bundles. This keeps promotion explicit and
reviewable without introducing a second asset model.

## Bundle contents

`GET /api/v1/projects/{id}/bundle` returns:

- project code, name and environment
- datasource names and kinds (never DSNs or secrets)
- domains and glossary terms
- published assets: type, key, name, owner, schedule, domain, contract and
  published content

Draft assets are not exported. Export is available to platform administrators
and project administrators.

## Import

`POST /api/v1/projects/{id}/bundle/validate` previews the result:

- how many assets will be created or updated
- keys whose type conflicts with an existing asset
- datasources present in the bundle but missing in the target project

`POST /api/v1/projects/{id}/bundle/import` applies the bundle:

- datasources are mapped by `(name, kind)`. Create the same datasource names in
  the target project first.
- domains and terms are created or updated by name.
- assets are always imported as **drafts**. Review and publish them through the
  normal approval flow.
- asset references (`dataset_id`, `metric_id`, `dashboard_id`, and so on) are
  remapped to the target project's asset IDs.
- keys that already exist in another project receive a `_<project-code>` suffix
  so the global key remains unique.
- archived or missing datasource references are reported; fix them before
  publishing the imported drafts.

## Promotion workflow

1. Export the source project bundle.
2. Validate it against the target project.
3. Create any missing datasources in the target with the same name and kind.
4. Import the bundle.
5. Review drafts, run previews/tests, then publish through approval.

Because the bundle is plain JSON it can be committed to a Git repository or
attached to a release; the platform does not write to Git itself.

## Environment labels

Set or change a project environment in Administration → Projects. The label is
informational for routing and review; it does not change API permissions or
data placement.
