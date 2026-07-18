from fastapi import APIRouter

from app.connectors.registry import datasource_catalog

router = APIRouter(prefix="/api/datasources", tags=["datasources"])


@router.get("")
def list_datasources():
    return datasource_catalog()
