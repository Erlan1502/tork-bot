import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from app.routers.auth_router import router as auth_router
from app.routers.orders_router import router as orders_router
from app.routers.analytics_router import router as analytics_router
from app.routers.products_admin_router import router as products_admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Tork Kazakhstan B2B Management API",
    description="Control panel REST API for Vendor (Essity KZ) and Regional Distributors with strict RBAC data isolation, vendor analytics, and catalog management.",
    version="1.0.0",
    docs_url=None,
    openapi_url=None,
)

# Enable CORS for frontend applications (MiniApp, Admin Dashboard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth_router)
app.include_router(orders_router)
app.include_router(analytics_router)
app.include_router(products_admin_router)

# Healthcheck
@app.get("/health", tags=["System"])
@app.get("/api/admin/health", tags=["System"])
def healthcheck():
    return {"status": "ok", "service": "tork_dashboard_api"}

# Swagger UI and OpenAPI schemas accessible via /docs, /api/admin/docs, /openapi.json, and /api/admin/openapi.json
@app.get("/docs", include_in_schema=False)
@app.get("/api/admin/docs", include_in_schema=False)
def get_swagger_documentation():
    return get_swagger_ui_html(
        openapi_url="/api/admin/openapi.json",
        title="Tork B2B Dashboard API - Swagger UI",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )

@app.get("/openapi.json", include_in_schema=False)
@app.get("/api/admin/openapi.json", include_in_schema=False)
def get_openapi_spec():
    return JSONResponse(app.openapi())
