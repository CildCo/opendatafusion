# Embedding dashboards and applications

OpenDataFusion can expose a published dashboard or application as a
read-only embed. Embedding reuses the share token and the published-version
pipeline; it is not a separate permission model.

## Create an embed

1. Open a published dashboard or application and choose **Share**.
2. Select **Embed**, choose a validity between 1 and 30 days, and generate the
   link.
3. Copy the generated snippet or the `#/embed/<token>` URL.

The token is shown once. Revoking the share or letting it expire disables the
embed immediately. Embed content never includes forms, SQL or write actions.

## SDK

```html
<div id="odf-embed"></div>
<script src="https://your-host/ui/odf-embed.js"></script>
<script>
  ODFEmbed.mount({
    target: "#odf-embed",
    token: "<share-token>",
    height: 720,
    params: { region: "east" }
  });
</script>
```

`mount` returns `{ element, url, unmount }`. The iframe starts at the supplied
height and grows to the content height reported by the embed page. `params`
are appended to the embed URL and become normal dashboard/application
parameters.

`ODFEmbed.url(token, params)` returns the embed URL without mounting an
iframe.

## Security

- Share and embed tokens are bearer credentials; anyone holding one can view
  the published content until it expires or is revoked.
- Tokens are stored as SHA-256 hashes and are never returned by list
  endpoints.
- The embed page is read-only and strips forms and SQL from the public
  payload.
- Host the SDK from the same origin as the console; do not proxy tokens
  through third-party scripts.
