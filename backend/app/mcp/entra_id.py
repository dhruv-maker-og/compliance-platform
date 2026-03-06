"""Entra ID (Azure AD) MCP Server — provides identity & access evidence.

Connects to Microsoft Graph API to retrieve:
- Directory roles and role assignments
- Conditional Access policies
- MFA registration status
- Service principals and app registrations
- Sign-in logs
"""

from __future__ import annotations

from typing import Any

import structlog
from azure.identity.aio import DefaultAzureCredential
from msgraph import GraphServiceClient

from app.config import get_settings

logger = structlog.get_logger(__name__)


class EntraIdMCPServer:
    """Custom MCP server wrapping Microsoft Graph API for identity evidence."""

    def __init__(self) -> None:
        self._credential: DefaultAzureCredential | None = None
        self._client: GraphServiceClient | None = None

    async def initialize(self) -> None:
        """Initialize Graph client with managed identity or env credentials."""
        settings = get_settings()
        self._credential = DefaultAzureCredential()
        self._client = GraphServiceClient(
            self._credential,
            scopes=["https://graph.microsoft.com/.default"],
        )
        logger.info("entra_id_mcp_initialized")

    async def close(self) -> None:
        """Clean up credentials."""
        if self._credential:
            await self._credential.close()

    @property
    def client(self) -> GraphServiceClient:
        if self._client is None:
            raise RuntimeError("EntraIdMCPServer not initialized. Call initialize() first.")
        return self._client

    # ── Tools ───────────────────────────────────────────────────────────

    async def get_directory_roles(self) -> list[dict[str, Any]]:
        """List all directory roles and their assignments."""
        logger.info("fetching_directory_roles")
        try:
            roles_response = await self.client.directory_roles.get()
            roles = []
            if roles_response and roles_response.value:
                for role in roles_response.value:
                    members_response = await (
                        self.client
                        .directory_roles
                        .by_directory_role_id(role.id)
                        .members
                        .get()
                    )
                    member_list = []
                    if members_response and members_response.value:
                        for m in members_response.value:
                            member_list.append({
                                "id": m.id,
                                "display_name": getattr(m, "display_name", None),
                                "type": m.odata_type,
                            })
                    roles.append({
                        "id": role.id,
                        "display_name": role.display_name,
                        "description": role.description,
                        "member_count": len(member_list),
                        "members": member_list,
                    })
            logger.info("directory_roles_fetched", count=len(roles))
            return roles
        except Exception as e:
            logger.error("directory_roles_error", error=str(e))
            return [{"error": str(e)}]

    async def get_conditional_access_policies(self) -> list[dict[str, Any]]:
        """List all Conditional Access policies."""
        logger.info("fetching_conditional_access_policies")
        try:
            response = await (
                self.client
                .identity
                .conditional_access
                .policies
                .get()
            )
            policies = []
            if response and response.value:
                for policy in response.value:
                    conditions = policy.conditions
                    grant_controls = policy.grant_controls

                    policies.append({
                        "id": policy.id,
                        "display_name": policy.display_name,
                        "state": str(policy.state) if policy.state else None,
                        "conditions": {
                            "users": _serialize(conditions.users) if conditions else None,
                            "applications": _serialize(conditions.applications) if conditions else None,
                            "locations": _serialize(conditions.locations) if conditions else None,
                            "platforms": _serialize(conditions.platforms) if conditions else None,
                        },
                        "grant_controls": {
                            "operator": grant_controls.operator if grant_controls else None,
                            "built_in_controls": [
                                str(c) for c in (grant_controls.built_in_controls or [])
                            ] if grant_controls else [],
                        },
                    })
            logger.info("ca_policies_fetched", count=len(policies))
            return policies
        except Exception as e:
            logger.error("ca_policies_error", error=str(e))
            return [{"error": str(e)}]

    async def get_mfa_registration_status(self) -> dict[str, Any]:
        """Get MFA registration details for credentialUserRegistrationDetails."""
        logger.info("fetching_mfa_status")
        try:
            response = await (
                self.client
                .reports
                .credential_user_registration_details
                .get()
            )
            registered = 0
            not_registered = 0
            users = []

            if response and response.value:
                for detail in response.value:
                    is_registered = detail.is_mfa_registered or False
                    if is_registered:
                        registered += 1
                    else:
                        not_registered += 1
                    users.append({
                        "user_principal_name": detail.user_principal_name,
                        "is_mfa_registered": is_registered,
                        "is_sspr_registered": detail.is_registered or False,
                        "auth_methods": [
                            str(m) for m in (detail.auth_methods or [])
                        ],
                    })

            result = {
                "total_users": len(users),
                "mfa_registered": registered,
                "mfa_not_registered": not_registered,
                "mfa_coverage_pct": round(
                    registered / len(users) * 100, 1
                ) if users else 0,
                "users": users,
            }
            logger.info("mfa_status_fetched", registered=registered, total=len(users))
            return result
        except Exception as e:
            logger.error("mfa_status_error", error=str(e))
            return {"error": str(e)}

    async def get_service_principals(self) -> list[dict[str, Any]]:
        """List service principals with key metadata."""
        logger.info("fetching_service_principals")
        try:
            response = await self.client.service_principals.get()
            principals = []
            if response and response.value:
                for sp in response.value:
                    principals.append({
                        "id": sp.id,
                        "app_id": sp.app_id,
                        "display_name": sp.display_name,
                        "service_principal_type": sp.service_principal_type,
                        "account_enabled": sp.account_enabled,
                        "sign_in_audience": sp.sign_in_audience,
                        "key_credentials_count": len(sp.key_credentials or []),
                        "password_credentials_count": len(sp.password_credentials or []),
                    })
            logger.info("service_principals_fetched", count=len(principals))
            return principals
        except Exception as e:
            logger.error("service_principals_error", error=str(e))
            return [{"error": str(e)}]

    async def get_app_registrations(self) -> list[dict[str, Any]]:
        """List application registrations."""
        logger.info("fetching_app_registrations")
        try:
            response = await self.client.applications.get()
            apps = []
            if response and response.value:
                for app in response.value:
                    apps.append({
                        "id": app.id,
                        "app_id": app.app_id,
                        "display_name": app.display_name,
                        "sign_in_audience": app.sign_in_audience,
                        "key_credentials_count": len(app.key_credentials or []),
                        "password_credentials_count": len(app.password_credentials or []),
                        "web_redirect_uris": (
                            app.web.redirect_uris if app.web else []
                        ),
                    })
            logger.info("app_registrations_fetched", count=len(apps))
            return apps
        except Exception as e:
            logger.error("app_registrations_error", error=str(e))
            return [{"error": str(e)}]

    async def get_sign_in_logs(
        self,
        *,
        top: int = 50,
        filter_str: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve recent sign-in logs."""
        logger.info("fetching_sign_in_logs", top=top)
        try:
            from msgraph.generated.audit_logs.sign_ins.sign_ins_request_builder import (
                SignInsRequestBuilder,
            )

            config = SignInsRequestBuilder.SignInsRequestBuilderGetQueryParameters(
                top=top,
                orderby=["createdDateTime desc"],
            )
            if filter_str:
                config.filter = filter_str

            request_config = SignInsRequestBuilder.SignInsRequestBuilderGetRequestConfiguration(
                query_parameters=config,
            )
            response = await self.client.audit_logs.sign_ins.get(
                request_configuration=request_config
            )

            logs = []
            if response and response.value:
                for log in response.value:
                    logs.append({
                        "id": log.id,
                        "user_principal_name": log.user_principal_name,
                        "app_display_name": log.app_display_name,
                        "created_date_time": (
                            log.created_date_time.isoformat()
                            if log.created_date_time else None
                        ),
                        "status": {
                            "error_code": log.status.error_code if log.status else None,
                            "failure_reason": log.status.failure_reason if log.status else None,
                        },
                        "ip_address": log.ip_address,
                        "location": {
                            "city": log.location.city if log.location else None,
                            "country": log.location.country_or_region if log.location else None,
                        },
                        "conditional_access_status": str(log.conditional_access_status) if log.conditional_access_status else None,
                        "is_interactive": log.is_interactive,
                    })
            logger.info("sign_in_logs_fetched", count=len(logs))
            return logs
        except Exception as e:
            logger.error("sign_in_logs_error", error=str(e))
            return [{"error": str(e)}]

    # ── MCP Tool Definitions ────────────────────────────────────────────

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return MCP-compatible tool definitions."""
        return [
            {
                "name": "entra_get_directory_roles",
                "description": "List all Azure AD directory roles and their members",
                "parameters": {},
                "handler": self.get_directory_roles,
            },
            {
                "name": "entra_get_conditional_access",
                "description": "List all Conditional Access policies",
                "parameters": {},
                "handler": self.get_conditional_access_policies,
            },
            {
                "name": "entra_get_mfa_status",
                "description": "Get MFA registration status for all users",
                "parameters": {},
                "handler": self.get_mfa_registration_status,
            },
            {
                "name": "entra_get_service_principals",
                "description": "List all service principals",
                "parameters": {},
                "handler": self.get_service_principals,
            },
            {
                "name": "entra_get_app_registrations",
                "description": "List all application registrations",
                "parameters": {},
                "handler": self.get_app_registrations,
            },
            {
                "name": "entra_get_sign_in_logs",
                "description": "Get recent sign-in logs",
                "parameters": {
                    "top": {"type": "integer", "default": 50},
                    "filter": {"type": "string", "optional": True},
                },
                "handler": self.get_sign_in_logs,
            },
        ]


def _serialize(obj: Any) -> Any:
    """Best-effort serialize Graph SDK objects to dicts."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if hasattr(obj, "__dict__"):
        result = {}
        for key, value in obj.__dict__.items():
            if not key.startswith("_"):
                try:
                    result[key] = _serialize(value)
                except Exception:
                    result[key] = str(value)
        return result
    return str(obj)
