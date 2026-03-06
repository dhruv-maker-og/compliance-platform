import { useState } from "react";
import {
  Button,
  Card,
  CardHeader,
  Field,
  Input,
  Select,
  Text,
  Title2,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import { PlayRegular, StopRegular } from "@fluentui/react-icons";
import { api } from "../api/client";
import { useSSE } from "../hooks/useSSE";
import AgentTimeline from "../components/AgentTimeline";
import type { EvidenceCollectionRequest } from "../types";

const useStyles = makeStyles({
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "24px",
  },
  form: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "16px",
    padding: "16px",
  },
  fullWidth: {
    gridColumn: "1 / -1",
  },
  actions: {
    display: "flex",
    gap: "8px",
    marginTop: "8px",
    gridColumn: "1 / -1",
  },
  results: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "24px",
  },
  timeline: {
    maxHeight: "600px",
    overflow: "auto",
  },
  error: {
    color: tokens.colorPaletteRedForeground1,
    padding: "12px",
    backgroundColor: tokens.colorPaletteRedBackground1,
    borderRadius: tokens.borderRadiusMedium,
  },
});

export default function EvidenceCollection() {
  const styles = useStyles();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [formData, setFormData] = useState<EvidenceCollectionRequest>({
    framework: "PCI-DSS v4.0",
    scope: "",
    azure_subscription_id: "",
    github_org: "",
    github_repo: "",
  });

  const { steps, isStreaming, error, startStream, stopStream } = useSSE({
    onComplete: (data) => {
      console.log("Evidence collection complete:", data);
    },
  });

  const handleStart = async () => {
    try {
      const response = await api.evidence.collect(formData);
      setSessionId(response.session_id);
      startStream(response.stream_url);
    } catch (err) {
      console.error("Failed to start evidence collection:", err);
    }
  };

  const handleStop = async () => {
    stopStream();
    if (sessionId) {
      try {
        await api.evidence.cancel(sessionId);
      } catch {
        // Ignore cancel errors
      }
    }
  };

  return (
    <div className={styles.page}>
      <Title2>Evidence Collection</Title2>
      <Text>
        Collect compliance evidence from Azure, GitHub, Entra ID, and Purview
        using AI-powered workflows.
      </Text>

      <Card>
        <CardHeader
          header={<Text weight="semibold">Collection Parameters</Text>}
        />
        <div className={styles.form}>
          <Field label="Compliance Framework">
            <Select
              value={formData.framework}
              onChange={(_, data) =>
                setFormData((prev) => ({ ...prev, framework: data.value }))
              }
            >
              <option value="PCI-DSS v4.0">PCI-DSS v4.0</option>
              <option value="SOC2">SOC 2</option>
              <option value="ISO 27001">ISO 27001</option>
              <option value="HIPAA">HIPAA</option>
            </Select>
          </Field>

          <Field label="Assessment Scope">
            <Input
              placeholder="e.g., Production Azure Subscription"
              value={formData.scope}
              onChange={(_, data) =>
                setFormData((prev) => ({ ...prev, scope: data.value }))
              }
            />
          </Field>

          <Field label="Azure Subscription ID">
            <Input
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              value={formData.azure_subscription_id}
              onChange={(_, data) =>
                setFormData((prev) => ({
                  ...prev,
                  azure_subscription_id: data.value,
                }))
              }
            />
          </Field>

          <Field label="GitHub Organization">
            <Input
              placeholder="e.g., my-org"
              value={formData.github_org}
              onChange={(_, data) =>
                setFormData((prev) => ({ ...prev, github_org: data.value }))
              }
            />
          </Field>

          <Field label="GitHub Repository">
            <Input
              placeholder="e.g., my-org/my-repo"
              value={formData.github_repo}
              onChange={(_, data) =>
                setFormData((prev) => ({ ...prev, github_repo: data.value }))
              }
            />
          </Field>

          <div className={styles.actions}>
            <Button
              appearance="primary"
              icon={<PlayRegular />}
              onClick={handleStart}
              disabled={isStreaming || !formData.scope}
            >
              Start Collection
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
          <div className={styles.timeline} style={{ padding: 16 }}>
            <AgentTimeline steps={steps} isStreaming={isStreaming} />
          </div>
        </Card>
      )}
    </div>
  );
}
