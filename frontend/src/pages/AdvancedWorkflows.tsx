import { useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Text,
  Textarea,
  Title2,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import {
  BeakerRegular,
  BranchRequestRegular,
  CodeRegular,
  DocumentTextRegular,
} from "@fluentui/react-icons";
import { api } from "../api/client";
import type {
  DriftDetectionResponse,
  DriftScheduleStatus,
  FrameworkComparisonResponse,
  RegoDebugResponse,
} from "../types";

const useStyles = makeStyles({
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  section: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    padding: "16px",
  },
  row: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap",
  },
  output: {
    whiteSpace: "pre-wrap",
    backgroundColor: tokens.colorNeutralBackground3,
    borderRadius: tokens.borderRadiusMedium,
    padding: "10px",
    border: `1px solid ${tokens.colorNeutralStroke1}`,
  },
  smallText: {
    color: tokens.colorNeutralForeground3,
  },
});

const SAMPLE_EVIDENCE = JSON.stringify(
  [
    {
      source: "azure:nsg_rules",
      data_type: "config",
      data: { rule_count: 6, denied_ports: ["22"] },
      collected_at: new Date().toISOString(),
    },
  ],
  null,
  2
);

const SAMPLE_BASELINE = JSON.stringify(
  [
    { control_id: "1.2", status: "passed" },
    { control_id: "8.3", status: "passed" },
    { control_id: "3.5", status: "gap" },
  ],
  null,
  2
);

const SAMPLE_CURRENT = JSON.stringify(
  [
    { control_id: "1.2", status: "gap" },
    { control_id: "8.3", status: "passed" },
    { control_id: "3.5", status: "passed" },
  ],
  null,
  2
);

const SAMPLE_REGO = `package policy

deny[msg] {
  some i
  rc := input.resource_changes[i]
  rc.type == "azurerm_storage_account"
  not rc.change.after.enable_https_traffic_only
  msg := {
    "msg": "Storage account must enforce HTTPS-only traffic",
    "resource": rc.address,
    "severity": "high"
  }
}`;

const SAMPLE_PLAN = JSON.stringify(
  {
    resource_changes: [
      {
        address: "azurerm_storage_account.bad",
        type: "azurerm_storage_account",
        change: { after: { enable_https_traffic_only: false } },
      },
    ],
  },
  null,
  2
);

export default function AdvancedWorkflows() {
  const styles = useStyles();

  const [narrative, setNarrative] = useState("");
  const [evidenceJson, setEvidenceJson] = useState(SAMPLE_EVIDENCE);

  const [baselineJson, setBaselineJson] = useState(SAMPLE_BASELINE);
  const [currentJson, setCurrentJson] = useState(SAMPLE_CURRENT);
  const [driftResult, setDriftResult] = useState<DriftDetectionResponse | null>(null);
  const [driftScope, setDriftScope] = useState("production");
  const [driftInterval, setDriftInterval] = useState("60");
  const [driftStatus, setDriftStatus] = useState<DriftScheduleStatus | null>(null);

  const [frameworks, setFrameworks] = useState("pci-dss,soc2,iso27001");
  const [frameworkResult, setFrameworkResult] = useState<FrameworkComparisonResponse | null>(null);

  const [regoPolicy, setRegoPolicy] = useState(SAMPLE_REGO);
  const [planJson, setPlanJson] = useState(SAMPLE_PLAN);
  const [regoResult, setRegoResult] = useState<RegoDebugResponse | null>(null);

  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const frameworkList = useMemo(
    () => frameworks.split(",").map((f) => f.trim()).filter(Boolean),
    [frameworks]
  );

  const runNarration = async () => {
    setLoading("narrate");
    setError(null);
    try {
      const result = await api.insights.narrateEvidence({
        control_id: "1.2",
        requirement: "Network security controls are configured and maintained",
        assessment_status: "gap",
        evidence_items_json: evidenceJson,
      });
      setNarrative(result.narrative);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to narrate evidence");
    } finally {
      setLoading(null);
    }
  };

  const runDrift = async () => {
    setLoading("drift");
    setError(null);
    try {
      const result = await api.insights.driftDetect({
        baseline_assessments_json: baselineJson,
        current_assessments_json: currentJson,
        scope: driftScope,
      });
      setDriftResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run drift detection");
    } finally {
      setLoading(null);
    }
  };

  const saveBaseline = async () => {
    setLoading("drift-baseline");
    setError(null);
    try {
      await api.insights.setDriftBaseline({
        scope: driftScope,
        assessments_json: baselineJson,
      });
      const status = await api.insights.getDriftScheduleStatus(driftScope);
      setDriftStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save baseline snapshot");
    } finally {
      setLoading(null);
    }
  };

  const saveCurrent = async () => {
    setLoading("drift-current");
    setError(null);
    try {
      await api.insights.setDriftCurrent({
        scope: driftScope,
        assessments_json: currentJson,
      });
      const status = await api.insights.getDriftScheduleStatus(driftScope);
      setDriftStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save current snapshot");
    } finally {
      setLoading(null);
    }
  };

  const startSchedule = async () => {
    setLoading("drift-start");
    setError(null);
    try {
      const interval = Math.max(15, Number.parseInt(driftInterval, 10) || 60);
      const status = await api.insights.startDriftSchedule({
        scope: driftScope,
        interval_seconds: interval,
      });
      setDriftStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start drift schedule");
    } finally {
      setLoading(null);
    }
  };

  const stopSchedule = async () => {
    setLoading("drift-stop");
    setError(null);
    try {
      const status = await api.insights.stopDriftSchedule(driftScope);
      setDriftStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to stop drift schedule");
    } finally {
      setLoading(null);
    }
  };

  const runScheduledNow = async () => {
    setLoading("drift-run-now");
    setError(null);
    try {
      const result = await api.insights.runDriftNow(driftScope);
      setDriftResult(result);
      const status = await api.insights.getDriftScheduleStatus(driftScope);
      setDriftStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run scheduled drift check");
    } finally {
      setLoading(null);
    }
  };

  const refreshScheduleStatus = async () => {
    setLoading("drift-status");
    setError(null);
    try {
      const status = await api.insights.getDriftScheduleStatus(driftScope);
      setDriftStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get drift schedule status");
    } finally {
      setLoading(null);
    }
  };

  const runFrameworkCompare = async () => {
    setLoading("framework");
    setError(null);
    try {
      const result = await api.insights.frameworkCompare({ frameworks: frameworkList });
      setFrameworkResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to compare frameworks");
    } finally {
      setLoading(null);
    }
  };

  const runRegoDebug = async () => {
    setLoading("rego");
    setError(null);
    try {
      const result = await api.insights.regoDebug({
        policy_rego: regoPolicy,
        terraform_plan_json: planJson,
        query: "data.policy.deny",
      });
      setRegoResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run Rego debugger");
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className={styles.page}>
      <Title2>Advanced Workflows</Title2>
      <Text>
        Implemented feature set for evidence narration, continuous compliance drift detection,
        multi-framework comparison, and interactive Rego debugging.
      </Text>

      {error && <Badge color="danger">{error}</Badge>}

      <Card>
        <CardHeader
          image={<DocumentTextRegular fontSize={24} />}
          header={<Text weight="semibold">Evidence Narration for Auditors</Text>}
          description={<Text size={200}>Generate auditor-ready prose from raw evidence.</Text>}
        />
        <div className={styles.section}>
          <Field label="Evidence JSON">
            <Textarea rows={5} value={evidenceJson} onChange={(_, d) => setEvidenceJson(d.value)} />
          </Field>
          <div className={styles.row}>
            <Button appearance="primary" onClick={runNarration} disabled={loading !== null}>
              {loading === "narrate" ? "Generating..." : "Generate Narrative"}
            </Button>
          </div>
          {narrative && <div className={styles.output}>{narrative}</div>}
        </div>
      </Card>

      <Card>
        <CardHeader
          image={<BranchRequestRegular fontSize={24} />}
          header={<Text weight="semibold">Drift Detection / Continuous Compliance</Text>}
          description={<Text size={200}>Compare baseline and current control states.</Text>}
        />
        <div className={styles.section}>
          <Field label="Scope">
            <Textarea rows={1} value={driftScope} onChange={(_, d) => setDriftScope(d.value)} />
          </Field>
          <Field label="Schedule Interval (seconds)">
            <Textarea rows={1} value={driftInterval} onChange={(_, d) => setDriftInterval(d.value)} />
          </Field>
          <Field label="Baseline Assessments JSON">
            <Textarea rows={4} value={baselineJson} onChange={(_, d) => setBaselineJson(d.value)} />
          </Field>
          <Field label="Current Assessments JSON">
            <Textarea rows={4} value={currentJson} onChange={(_, d) => setCurrentJson(d.value)} />
          </Field>
          <div className={styles.row}>
            <Button appearance="primary" onClick={runDrift} disabled={loading !== null}>
              {loading === "drift" ? "Comparing..." : "Detect Drift"}
            </Button>
            <Button appearance="secondary" onClick={saveBaseline} disabled={loading !== null}>
              {loading === "drift-baseline" ? "Saving..." : "Save Baseline"}
            </Button>
            <Button appearance="secondary" onClick={saveCurrent} disabled={loading !== null}>
              {loading === "drift-current" ? "Saving..." : "Save Current"}
            </Button>
          </div>
          <div className={styles.row}>
            <Button appearance="primary" onClick={startSchedule} disabled={loading !== null}>
              {loading === "drift-start" ? "Starting..." : "Start Schedule"}
            </Button>
            <Button appearance="secondary" onClick={stopSchedule} disabled={loading !== null}>
              {loading === "drift-stop" ? "Stopping..." : "Stop Schedule"}
            </Button>
            <Button appearance="secondary" onClick={runScheduledNow} disabled={loading !== null}>
              {loading === "drift-run-now" ? "Running..." : "Run Now"}
            </Button>
            <Button appearance="subtle" onClick={refreshScheduleStatus} disabled={loading !== null}>
              {loading === "drift-status" ? "Refreshing..." : "Refresh Status"}
            </Button>
          </div>
          {driftStatus && (
            <div className={styles.output}>
              <Text weight="semibold">
                Scheduler: {driftStatus.running ? "Running" : "Stopped"} | Scope: {driftStatus.scope}
              </Text>
              <Text className={styles.smallText}>
                Interval: {driftStatus.interval_seconds ?? "N/A"}s | Baseline: {String(driftStatus.has_baseline)} | Current: {String(driftStatus.has_current)}
              </Text>
            </div>
          )}
          {driftResult && (
            <div className={styles.output}>
              <Text weight="semibold">
                Drift: {driftResult.drift_count} | Regressions: {driftResult.regressions} | Improvements: {driftResult.improvements}
              </Text>
              <Text className={styles.smallText}>
                Controls compared: {driftResult.total_controls_compared}
              </Text>
              {driftResult.changed_controls.map((item) => (
                <Text key={`${item.control_id}-${item.change_type}`}>
                  {item.control_id}: {item.baseline_status} {"->"} {item.current_status} ({item.change_type})
                </Text>
              ))}
            </div>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader
          image={<BeakerRegular fontSize={24} />}
          header={<Text weight="semibold">Multi-Framework Comparison</Text>}
          description={<Text size={200}>Compare control overlap and unique coverage.</Text>}
        />
        <div className={styles.section}>
          <Field label="Framework IDs (comma-separated)">
            <Textarea rows={2} value={frameworks} onChange={(_, d) => setFrameworks(d.value)} />
          </Field>
          <div className={styles.row}>
            <Button appearance="primary" onClick={runFrameworkCompare} disabled={loading !== null}>
              {loading === "framework" ? "Comparing..." : "Compare Frameworks"}
            </Button>
          </div>
          {frameworkResult && (
            <div className={styles.output}>
              <Text>Found: {frameworkResult.frameworks_found.join(", ") || "none"}</Text>
              <Text>Common IDs: {frameworkResult.common_control_ids.length}</Text>
              <Text className={styles.smallText}>
                {JSON.stringify(frameworkResult.total_controls_by_framework, null, 2)}
              </Text>
            </div>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader
          image={<CodeRegular fontSize={24} />}
          header={<Text weight="semibold">Interactive Rego Debugger</Text>}
          description={<Text size={200}>Run policy eval with OPA explain trace output.</Text>}
        />
        <div className={styles.section}>
          <Field label="Policy Rego">
            <Textarea rows={8} value={regoPolicy} onChange={(_, d) => setRegoPolicy(d.value)} />
          </Field>
          <Field label="Terraform Plan JSON">
            <Textarea rows={6} value={planJson} onChange={(_, d) => setPlanJson(d.value)} />
          </Field>
          <div className={styles.row}>
            <Button appearance="primary" onClick={runRegoDebug} disabled={loading !== null}>
              {loading === "rego" ? "Debugging..." : "Run Rego Debugger"}
            </Button>
          </div>
          {regoResult && (
            <div className={styles.output}>
              <Text weight="semibold">{regoResult.summary}</Text>
              <Text className={styles.smallText}>
                Violations: {regoResult.violations.length}
              </Text>
              <Text className={styles.smallText}>{regoResult.explain_trace.slice(0, 1800)}</Text>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
