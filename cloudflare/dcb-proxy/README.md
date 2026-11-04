# e-Panchayat DCB proxy

This Cloudflare Worker fetches the DCB workbook live from `https://epanchayat.telangana.gov.in/epmis/allgpdata.jsp` and streams it to the Render app. It also relays Playwright requests for the allowlisted e-Panchayat hosts so the Render server can use the India-region route for department login and reports. Both routes require the bearer secret and disable caching; portal requests are restricted to the official e-Panchayat hosts. Cloudflare service placement uses the Hyderabad region.

## Deploy with Wrangler

1. Install Wrangler and sign in with `wrangler login`.
2. From this folder, run `wrangler deploy`.
3. Set the Worker secret with `wrangler secret put DCB_PROXY_TOKEN` and deploy the resulting version.
4. Set Render service variables `DCB_PORTAL_PROXY_URL` to the Worker URL and `DCB_PORTAL_PROXY_TOKEN` to the same secret. Never commit the secret.
5. Verify `/health`, `/v1/dcb/raw`, and `/v1/portal` with the bearer token. The portal relay requires `X-Portal-Target` set to an HTTPS URL on an allowlisted host.

When `DCB_PORTAL_PROXY_URL` is set, the Render app uses the authenticated Worker. With the variable unset, local development fetches the live portal directly. If the Worker cannot reach e-Panchayat, the app reports that failure; it never falls back to an offline Excel file.
