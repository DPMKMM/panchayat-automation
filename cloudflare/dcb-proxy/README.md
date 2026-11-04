# e-Panchayat DCB proxy

This Cloudflare Worker fetches the DCB workbook live from `https://epanchayat.telangana.gov.in/epmis/allgpdata.jsp` and streams it to the Render app. It only exposes a fixed DCB route, requires a bearer secret, and never stores or caches workbook contents. Cloudflare service placement uses `epanchayat.telangana.gov.in` as its upstream location hint.

## Deploy with Wrangler

1. Install Wrangler and sign in with `wrangler login`.
2. From this folder, run `wrangler deploy`.
3. Set the Worker secret with `wrangler secret put DCB_PROXY_TOKEN` and deploy the resulting version.
4. Set Render service variables `DCB_PORTAL_PROXY_URL` to the Worker URL and `DCB_PORTAL_PROXY_TOKEN` to the same secret. Never commit the secret.
5. Verify `/health` and request `/v1/dcb/raw` with the bearer token. The data route should return the live workbook with `x-dcb-source: epanchayat.telangana.gov.in`.

When `DCB_PORTAL_PROXY_URL` is set, the Render app uses the authenticated Worker. With the variable unset, local development fetches the live portal directly. If the Worker cannot reach e-Panchayat, the app reports that failure; it never falls back to an offline Excel file.
