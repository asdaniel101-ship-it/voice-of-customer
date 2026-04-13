from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import AsyncClient


COMPANY_PAYLOAD = {
    "name": "Acme Corp",
    "slug": "acme-corp",
    "search_terms": ["acme", "acme corp"],
}


@pytest.mark.asyncio
async def test_create_company(client: AsyncClient):
    response = await client.post("/api/companies", json=COMPANY_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Corp"
    assert data["slug"] == "acme-corp"
    assert data["active"] is True
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_list_companies(client: AsyncClient):
    await client.post("/api/companies", json=COMPANY_PAYLOAD)
    await client.post(
        "/api/companies",
        json={"name": "Beta Inc", "slug": "beta-inc", "search_terms": ["beta"]},
    )
    response = await client.get("/api/companies")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_update_company(client: AsyncClient):
    create_resp = await client.post("/api/companies", json=COMPANY_PAYLOAD)
    company_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/companies/{company_id}", json={"name": "Acme Corporation"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Acme Corporation"


@pytest.mark.asyncio
async def test_delete_company(client: AsyncClient):
    create_resp = await client.post("/api/companies", json=COMPANY_PAYLOAD)
    company_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/companies/{company_id}")
    assert delete_resp.status_code == 204

    # Hard delete — company no longer in list
    list_resp = await client.get("/api/companies")
    companies = list_resp.json()
    assert len(companies) == 0


@pytest.mark.asyncio
async def test_create_duplicate_slug_fails(client: AsyncClient):
    await client.post("/api/companies", json=COMPANY_PAYLOAD)
    response = await client.post("/api/companies", json=COMPANY_PAYLOAD)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_trigger_pipeline_run(client: AsyncClient):
    create_resp = await client.post("/api/companies", json=COMPANY_PAYLOAD)
    assert create_resp.status_code == 201
    company_id = create_resp.json()["id"]

    fake_run_id = uuid.uuid4()
    with patch(
        "signalgraph.api.companies.run_pipeline",
        new=AsyncMock(return_value=fake_run_id),
    ):
        response = await client.post(f"/api/companies/{company_id}/run")

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "started"
    assert data["run_id"] == str(fake_run_id)
