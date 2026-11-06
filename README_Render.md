# Render Deployment

The production webserver is named **ept-automation** and is available at **https://ept-automation.onrender.com**. It deploys automatically from **https://github.com/DPMKMM/panchayat-automation**, branch `main`, using the repository Dockerfile.

## Deployment behavior

- The service runs in Singapore on Render Free.
- The repository Blueprint is `render.yaml`.
- The service is configured to auto-deploy commits from `main`.
- `/health` is the liveness endpoint.
- Container base: `mcr.microsoft.com/playwright/python:v1.50.0-noble` with full Playwright & Chromium support.

## Endpoints

- Live URL: https://ept-automation.onrender.com
- Health Check: https://ept-automation.onrender.com/health
