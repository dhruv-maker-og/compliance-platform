import { useState } from "react";
import {
  Button,
  Card,
  CardHeader,
  Field,
  Input,
  Select,
  Switch,
  Tab,
  TabList,
  Text,
  Textarea,
  Title2,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import { PlayRegular, StopRegular } from "@fluentui/react-icons";
import { api } from "../api/client";
import { useSSE } from "../hooks/useSSE";
import AgentTimeline from "../components/AgentTimeline";

const useStyles = makeStyles({
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "24px",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    padding: "16px",
  },
  actions: {
    display: "flex",
    gap: "8px",
    marginTop: "8px",
  },
  timeline: {
    maxHeight: "600px",
    overflow: "auto",
    padding: "16px",
  },
  error: {
    color: tokens.colorPaletteRedForeground1,
    padding: "12px",
    backgroundColor: tokens.colorPaletteRedBackground1,
    borderRadius: tokens.borderRadiusMedium,
  },
});

type Mode = "generate" | "enforce";

export default function PolicyEnforcer() {
  const styles = useStyles();
  const [mode, setMode] = useState<Mode>("generate");
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Generate form
  const [intent, setIntent] = useState("");
  const [targetResources, setTargetResources] = useState("");
  const [severity, setSeverity] = useState("high");

  // Enforce form
  const [policyPath, setPolicyPath] = useState("");
  const [terraformPlanPath, setTerraformPlanPath] = useState("");
  const [autoFix, setAutoFix] = useState(false);

  const { steps, isStreaming, error, startStream, stopStream } = useSSE({
    onComplete: (data) => {
      console.log("Policy workflow complete:", data);
    },
  });

  const handleGenerate = async () => {
    try {
      const response = await api.policy.generate({
        intent,
        target_resources: targetResources
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        severity: severity as "critical" | "high" | "medium" | "low" | "info",
      });
      setSessionId(response.session_id);
      startStream(response.stream_url);
    } catch (err) {
      console.error("Failed to start policy generation:", err);
    }
  };

  const handleEnforce = async () => {
    try {
      const response = await api.policy.enforce({
        policy_path: policyPath,
        terraform_plan_path: terraformPlanPath,
        auto_fix: autoFix,
      });
      setSessionId(response.session_id);
      startStream(response.stream_url);
    } catch (err) {
      console.error("Failed to start policy enforcement:", err);
    }
  };

  const handleStop = async () => {
    stopStream();
    if (sessionId) {
      try {
        await api.policy.cancel(sessionId);
      } catch {
        // Ignore
      }
    }
  };

  return (
    <div className={styles.page}>
      <Title2>Policy Enforcer</Title2>
      <Text>
        Generate OPA Rego policies from natural language or enforce existing
        policies against Terraform plans.
      </Text>

      <TabList
        selectedValue={mode}
        onTabSelect={(_, data) => setMode(data.value as Mode)}
      >
        <Tab value="generate">Generate Policy</Tab>
        <Tab value="enforce">Enforce Policy</Tab>
      </TabList>

      <Card>
        <CardHeader
          header={
            <Text weight="semibold">
              {mode === "generate" ? "Policy Generation" : "Policy Enforcement"}
            </Text>
          }
        />

        {mode === "generate" ? (
          <div className={styles.form}>
            <Field label="Policy Intent (Natural Language)">
              <Textarea
                placeholder="e.g., All storage accounts must have encryption enabled and HTTPS-only traffic"
                value={intent}
                onChange={(_, data) => setIntent(data.value)}
                rows={3}
              />
            </Field>

            <Field label="Target Resources (comma-separated)">
              <Input
                placeholder="e.g., azurerm_storage_account, azurerm_sql_server"
                value={targetResources}
                onChange={(_, data) => setTargetResources(data.value)}
              />
            </Field>

            <Field label="Severity">
              <Select
                value={severity}
                onChange={(_, data) => setSeverity(data.value)}
              >
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </Select>
            </Field>

            <div className={styles.actions}>
              <Button
                appearance="primary"
                icon={<PlayRegular />}
                onClick={handleGenerate}
                disabled={isStreaming || !intent}
              >
                Generate Policy
              </Button>
              {isStreaming && (
                <Button
                  appearance="secondary"
                  icon={<StopRegular />}
                  onClick={handleStop}
                >
                  Stop
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div className={styles.form}>
            <Field label="Rego Policy Path">
              <Input
                placeholder="e.g., policies/require_encryption.rego"
                value={policyPath}
                onChange={(_, data) => setPolicyPath(data.value)}
              />
            </Field>

            <Field label="Terraform Plan JSON Path">
              <Input
                placeholder="e.g., tfplan.json"
                value={terraformPlanPath}
                onChange={(_, data) => setTerraformPlanPath(data.value)}
              />
            </Field>

            <Field label="Auto-Fix Violations">
              <Switch
                checked={autoFix}
                onChange={(_, data) => setAutoFix(data.checked)}
                label={autoFix ? "Enabled — agent will suggest fixes" : "Disabled"}
              />
            </Field>

            <div className={styles.actions}>
              <Button
                appearance="primary"
                icon={<PlayRegular />}
                onClick={handleEnforce}
                disabled={isStreaming || !policyPath || !terraformPlanPath}
              >
                Enforce Policy
              </Button>
              {isStreaming && (
                <Button
                  appearance="secondary"
                  icon={<StopRegular />}
                  onClick={handleStop}
                >
                  Stop
                </Button>
              )}
            </div>
          </div>
        )}
      </Card>

      {error && (
        <div className={styles.error}>
          <Text weight="semibold">Error:</Text> {error}
        </div>
      )}

      {(steps.length > 0 || isStreaming) && (
        <Card>
          <CardHeader
            header={
              <Text weight="semibold">
                Agent Progress {sessionId ? `(${sessionId.slice(0, 8)}...)` : ""}
              </Text>
            }
          />
          <div className={styles.timeline}>
            <AgentTimeline steps={steps} isStreaming={isStreaming} />
          </div>
        </Card>
      )}
    </div>
  );
}
