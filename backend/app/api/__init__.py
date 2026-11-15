from fastapi import APIRouter

from app.api import (
    auth,
    dashboard,
    entries,
    exports,
    imports,
    locations,
    providers,
    rc,
    settings_routes,
    users,
    vehicles,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(locations.router)
api_router.include_router(entries.router)
api_router.include_router(vehicles.router)
api_router.include_router(dashboard.router)
api_router.include_router(imports.router)
api_router.include_router(providers.router)
api_router.include_router(settings_routes.router)
api_router.include_router(exports.router)
api_router.include_router(rc.router)
