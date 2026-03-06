"""Agent hooks for OpenTelemetry observability.

Re-exports the AgentHooks class from engine.py and provides
the OpenTelemetry instrumentation setup for the agent.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


def setup_telemetry() -> None:
    """Initialize OpenTelemetry tracing and metrics for the agent.

    Configures:
    - TracerProvider with Azure Monitor exporter
    - MeterProvider for custom metrics
    - Logging integration with structlog
    """
    settings = get_settings()

    if not settings.applicationinsights_connection_string:
        logger.warning("otel_skipped", reason="No Application Insights connection string configured")
        return

    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.resources import Resource
        from azure.monitor.opentelemetry.exporter import (
            AzureMonitorTraceExporter,
            AzureMonitorMetricExporter,
        )

        resource = Resource.create({
            "service.name": settings.otel_service_name,
            "service.version": "0.1.0",
            "deployment.environment": settings.environment,
        })

        # Tracing
        trace_exporter = AzureMonitorTraceExporter(
            connection_string=settings.applicationinsights_connection_string,
        )
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
        trace.set_tracer_provider(tracer_provider)

        # Metrics
        metric_exporter = AzureMonitorMetricExporter(
            connection_string=settings.applicationinsights_connection_string,
        )
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[],  # Add PeriodicExportingMetricReader in production
        )
        metrics.set_meter_provider(meter_provider)

        logger.info("otel_initialized", service=settings.otel_service_name)

    except ImportError:
        logger.warning("otel_import_error", msg="OpenTelemetry packages not installed")
    except Exception as e:
        logger.error("otel_setup_error", error=str(e))


# ── Custom Metrics ──────────────────────────────────────────────────────

class AgentMetrics:
    """Custom metrics for agent observability."""

    def __init__(self) -> None:
        try:
            from opentelemetry import metrics
            meter = metrics.get_meter("compliance-platform", "0.1.0")

            self.session_count = meter.create_counter(
                "agent.session.count",
                description="Number of agent sessions created",
                unit="sessions",
            )
            self.session_duration = meter.create_histogram(
                "agent.session.duration",
                description="Duration of agent sessions",
                unit="ms",
            )
            self.tool_invocations = meter.create_counter(
                "agent.tool.invocations",
                description="Number of tool invocations",
                unit="calls",
            )
            self.controls_collected = meter.create_counter(
                "evidence.controls.collected",
                description="Number of controls with evidence collected",
                unit="controls",
            )
            self.gaps_found = meter.create_counter(
                "evidence.gaps.found",
                description="Number of compliance gaps found",
                unit="gaps",
            )
            self.violations_found = meter.create_counter(
                "policy.violations.found",
                description="Number of policy violations found",
                unit="violations",
            )
            self.fixes_applied = meter.create_counter(
                "policy.fixes.applied",
                description="Number of auto-fixes applied",
                unit="fixes",
            )
            self._available = True
        except Exception:
            self._available = False

    def record_session_started(self, mode: str) -> None:
        if self._available:
            self.session_count.add(1, {"agent.mode": mode})

    def record_session_duration(self, duration_ms: float, mode: str) -> None:
        if self._available:
            self.session_duration.record(duration_ms, {"agent.mode": mode})

    def record_tool_call(self, tool_name: str, success: bool) -> None:
        if self._available:
            self.tool_invocations.add(1, {"tool.name": tool_name, "tool.success": str(success)})

    def record_controls_collected(self, count: int, framework: str) -> None:
        if self._available:
            self.controls_collected.add(count, {"framework": framework})

    def record_gaps_found(self, count: int, framework: str) -> None:
        if self._available:
            self.gaps_found.add(count, {"framework": framework})

    def record_violations(self, count: int) -> None:
        if self._available:
            self.violations_found.add(count)

    def record_fixes(self, count: int) -> None:
        if self._available:
            self.fixes_applied.add(count)
