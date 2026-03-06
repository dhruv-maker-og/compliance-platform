"""Purview MCP Server — provides data governance & classification evidence.

Connects to Microsoft Purview REST API to retrieve:
- Data classifications and sensitivity labels
- Data catalog assets
- Scan results and scan configs
- Data policies / policy compliance
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from azure.identity.aio import DefaultAzureCredential

from app.config import get_settings

logger = structlog.get_logger(__name__)


class PurviewMCPServer:
    """Custom MCP server wrapping Microsoft Purview REST APIs."""

    def __init__(self) -> None:
        self._credential: DefaultAzureCredential | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._base_url: str = ""
        self._scan_base_url: str = ""

    async def initialize(self) -> None:
        """Initialize HTTP client with Azure credentials."""
        settings = get_settings()
        account_name = settings.purview_account_name

        if not account_name:
            logger.warning("purview_account_not_configured")
            return

        self._base_url = f"https://{account_name}.purview.azure.com"
        self._scan_base_url = f"https://{account_name}.scan.purview.azure.com"
        self._credential = DefaultAzureCredential()
        self._http_client = httpx.AsyncClient(timeout=30.0)

        logger.info("purview_mcp_initialized", account=account_name)

    async def close(self) -> None:
        """Clean up resources."""
        if self._http_client:
            await self._http_client.aclose()
        if self._credential:
            await self._credential.close()

    async def _get_token(self) -> str:
        """Get Bearer token for Purview API."""
        if self._credential is None:
            raise RuntimeError("PurviewMCPServer not initialized")
        token = await self._credential.get_token(
            "https://purview.azure.net/.default"
        )
        return token.token

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Make an authenticated request to Purview API."""
        if self._http_client is None:
            raise RuntimeError("PurviewMCPServer not initialized")

        token = await self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        response = await self._http_client.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
        )
        response.raise_for_status()
        return response.json()

    # ── Tools ───────────────────────────────────────────────────────────

    async def get_classifications(self) -> list[dict[str, Any]]:
        """List all classification definitions in the catalog."""
        logger.info("fetching_classifications")
        try:
            url = f"{self._base_url}/catalog/api/atlas/v2/types/typedefs"
            result = await self._request("GET", url, params={"type": "classification"})

            classifications = []
            if isinstance(result, dict):
                type_defs = result.get("classificationDefs", [])
                for td in type_defs:
                    classifications.append({
                        "name": td.get("name"),
                        "description": td.get("description"),
                        "category": td.get("category"),
                        "created_by": td.get("createdBy"),
                        "update_time": td.get("updateTime"),
                    })

            logger.info("classifications_fetched", count=len(classifications))
            return classifications
        except Exception as e:
            logger.error("classifications_error", error=str(e))
            return [{"error": str(e)}]

    async def search_catalog(
        self,
        *,
        keywords: str = "*",
        limit: int = 25,
        filter_obj: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search the data catalog for assets."""
        logger.info("searching_catalog", keywords=keywords, limit=limit)
        try:
            url = f"{self._base_url}/catalog/api/search/query"
            body: dict[str, Any] = {
                "keywords": keywords,
                "limit": limit,
            }
            if filter_obj:
                body["filter"] = filter_obj

            result = await self._request("POST", url, json_body=body)

            assets = []
            if isinstance(result, dict):
                for item in result.get("value", []):
                    assets.append({
                        "name": item.get("name"),
                        "qualified_name": item.get("qualifiedName"),
                        "entity_type": item.get("entityType"),
                        "classification": item.get("classification", []),
                        "owner": item.get("owner"),
                        "description": item.get("description"),
                        "id": item.get("id"),
                    })

            logger.info("catalog_search_complete", results=len(assets))
            return assets
        except Exception as e:
            logger.error("catalog_search_error", error=str(e))
            return [{"error": str(e)}]

    async def get_data_sources(self) -> list[dict[str, Any]]:
        """List registered data sources."""
        logger.info("fetching_data_sources")
        try:
            url = f"{self._scan_base_url}/datasources"
            result = await self._request(
                "GET", url, params={"api-version": "2022-07-01-preview"}
            )

            sources = []
            if isinstance(result, dict):
                for item in result.get("value", []):
                    props = item.get("properties", {})
                    sources.append({
                        "name": item.get("name"),
                        "kind": item.get("kind"),
                        "endpoint": props.get("endpoint"),
                        "resource_group": props.get("resourceGroup"),
                        "subscription_id": props.get("subscriptionId"),
                        "location": props.get("location"),
                    })

            logger.info("data_sources_fetched", count=len(sources))
            return sources
        except Exception as e:
            logger.error("data_sources_error", error=str(e))
            return [{"error": str(e)}]

    async def get_scans(self, data_source_name: str) -> list[dict[str, Any]]:
        """List scans for a given data source."""
        logger.info("fetching_scans", data_source=data_source_name)
        try:
            url = (
                f"{self._scan_base_url}/datasources/{data_source_name}/scans"
            )
            result = await self._request(
                "GET", url, params={"api-version": "2022-07-01-preview"}
            )

            scans = []
            if isinstance(result, dict):
                for item in result.get("value", []):
                    props = item.get("properties", {})
                    scans.append({
                        "name": item.get("name"),
                        "kind": item.get("kind"),
                        "scan_ruleset": props.get("scanRulesetName"),
                        "created_at": props.get("createdAt"),
                        "last_modified": props.get("lastModifiedAt"),
                    })

            logger.info("scans_fetched", count=len(scans))
            return scans
        except Exception as e:
            logger.error("scans_error", error=str(e))
            return [{"error": str(e)}]

    async def get_scan_history(
        self,
        data_source_name: str,
        scan_name: str,
    ) -> list[dict[str, Any]]:
        """Get scan run history for a specific scan."""
        logger.info("fetching_scan_history", data_source=data_source_name, scan=scan_name)
        try:
            url = (
                f"{self._scan_base_url}/datasources/{data_source_name}"
                f"/scans/{scan_name}/runs"
            )
            result = await self._request(
                "GET", url, params={"api-version": "2022-07-01-preview"}
            )

            runs = []
            if isinstance(result, dict):
                for item in result.get("value", []):
                    props = item.get("properties", {})
                    runs.append({
                        "run_id": item.get("name"),
                        "status": props.get("status"),
                        "started_at": props.get("startTime"),
                        "ended_at": props.get("endTime"),
                        "scan_level": props.get("scanLevel"),
                        "assets_discovered": props.get("assetsDiscovered", 0),
                        "assets_classified": props.get("assetsClassified", 0),
                    })

            logger.info("scan_history_fetched", count=len(runs))
            return runs
        except Exception as e:
            logger.error("scan_history_error", error=str(e))
            return [{"error": str(e)}]

    async def get_sensitivity_labels(self) -> list[dict[str, Any]]:
        """List sensitivity labels from Purview Information Protection."""
        logger.info("fetching_sensitivity_labels")
        try:
            url = f"{self._base_url}/catalog/api/atlas/v2/types/typedefs"
            result = await self._request("GET", url)

            labels = []
            if isinstance(result, dict):
                for td in result.get("classificationDefs", []):
                    name = td.get("name", "")
                    if "sensitivity" in name.lower() or "label" in name.lower():
                        labels.append({
                            "name": name,
                            "description": td.get("description"),
                            "category": td.get("category"),
                        })

            logger.info("sensitivity_labels_fetched", count=len(labels))
            return labels
        except Exception as e:
            logger.error("sensitivity_labels_error", error=str(e))
            return [{"error": str(e)}]

    async def get_glossary_terms(self, *, limit: int = 25) -> list[dict[str, Any]]:
        """List glossary terms (business data classification)."""
        logger.info("fetching_glossary_terms", limit=limit)
        try:
            url = f"{self._base_url}/catalog/api/atlas/v2/glossary/terms"
            result = await self._request(
                "GET", url, params={"limit": limit, "offset": 0}
            )

            terms = []
            if isinstance(result, list):
                for item in result:
                    terms.append({
                        "name": item.get("name"),
                        "short_description": item.get("shortDescription"),
                        "long_description": item.get("longDescription"),
                        "status": item.get("status"),
                        "guid": item.get("guid"),
                    })

            logger.info("glossary_terms_fetched", count=len(terms))
            return terms
        except Exception as e:
            logger.error("glossary_terms_error", error=str(e))
            return [{"error": str(e)}]

    # ── MCP Tool Definitions ────────────────────────────────────────────

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return MCP-compatible tool definitions."""
        return [
            {
                "name": "purview_get_classifications",
                "description": "List all classification definitions in Microsoft Purview",
                "parameters": {},
                "handler": self.get_classifications,
            },
            {
                "name": "purview_search_catalog",
                "description": "Search the Purview data catalog for assets",
                "parameters": {
                    "keywords": {"type": "string", "default": "*"},
                    "limit": {"type": "integer", "default": 25},
                },
                "handler": self.search_catalog,
            },
            {
                "name": "purview_get_data_sources",
                "description": "List registered data sources in Purview",
                "parameters": {},
                "handler": self.get_data_sources,
            },
            {
                "name": "purview_get_scans",
                "description": "List scans for a given data source",
                "parameters": {
                    "data_source_name": {"type": "string", "required": True},
                },
                "handler": self.get_scans,
            },
            {
                "name": "purview_get_scan_history",
                "description": "Get scan run history for a specific scan",
                "parameters": {
                    "data_source_name": {"type": "string", "required": True},
                    "scan_name": {"type": "string", "required": True},
                },
                "handler": self.get_scan_history,
            },
            {
                "name": "purview_get_sensitivity_labels",
                "description": "List sensitivity labels from Purview",
                "parameters": {},
                "handler": self.get_sensitivity_labels,
            },
            {
                "name": "purview_get_glossary_terms",
                "description": "List business glossary terms",
                "parameters": {
                    "limit": {"type": "integer", "default": 25},
                },
                "handler": self.get_glossary_terms,
            },
        ]
