import { useState } from "react";
import {
  Button,
  Card,
  CardHeader,
  Dialog,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Text,
  Textarea,
  Title2,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import {
  ClipboardTextLtrRegular,
  LightbulbRegular,
  BeakerRegular,
  DocumentTextRegular,
} from "@fluentui/react-icons";
import ChatPanel from "../components/ChatPanel";
import { api } from "../api/client";

const useStyles = makeStyles({
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "24px",
  },
  emptyState: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "16px",
    padding: "48px",
    textAlign: "center",
    color: tokens.colorNeutralForeground3,
  },
  whatIfSection: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    padding: "16px",
  },
  chatDialog: {
    width: "700px",
    maxWidth: "90vw",
    height: "600px",
  },
  actions: {
    display: "flex",
    gap: "8px",
    marginTop: "8px",
  },
});

export default function Reports() {
  const styles = useStyles();
  const [chatMessage, setChatMessage] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [whatIfPlan, setWhatIfPlan] = useState("");
  const [narrative, setNarrative] = useState("");
  const [narrateBusy, setNarrateBusy] = useState(false);

  const handleExplainGap = (controlId: string, requirement: string) => {
    setChatMessage(
      `Explain why control ${controlId} ("${requirement}") failed and provide step-by-step remediation guidance with specific Azure/Entra ID settings to change.`
    );
    setChatOpen(true);
  };

  const handleWhatIf = () => {
    if (!whatIfPlan.trim()) return;
    setChatMessage(
      `Run a what-if policy simulation. Evaluate ALL active Rego policies against the following Terraform plan and summarise which resources comply and which violate policies. Group results by severity.\n\n\`\`\`json\n${whatIfPlan}\n\`\`\``
    );
    setChatOpen(true);
  };

  const handleNarrateEvidence = async () => {
    setNarrateBusy(true);
    try {
      const result = await api.insights.narrateEvidence({
        control_id: "1.2",
        requirement: "Network security controls are configured and maintained",
        assessment_status: "gap",
        evidence_items_json: JSON.stringify([
          {
            source: "azure:nsg_rules",
            data_type: "config",
            data: { denied_ports: ["22"] },
            collected_at: new Date().toISOString(),
          },
        ]),
      });
      setNarrative(result.narrative);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to generate narrative";
      setNarrative(message);
    } finally {
      setNarrateBusy(false);
    }
  };

  // Sample failed controls (in production these come from the latest report)
  const sampleGaps = [
    { id: "1.2", requirement: "Network security controls are configured and maintained" },
    { id: "8.3", requirement: "Strong authentication is established and managed" },
    { id: "3.5", requirement: "PAN is secured wherever it is stored" },
  ];

  return (
    <div className={styles.page}>
      <Title2>Compliance Reports</Title2>
      <Text>
        View, download, and share compliance assessment reports and policy
        enforcement results.
      </Text>

      {/* Explain Gap section */}
      <Card>
        <CardHeader
          image={<LightbulbRegular fontSize={24} />}
          header={<Text weight="semibold">Explain Gaps</Text>}
          description={
            <Text size={200}>
              Click &quot;Explain&quot; on any failed control to get AI-powered
              remediation guidance
            </Text>
          }
        />
        <div style={{ padding: "0 16px 16px" }}>
          {sampleGaps.map((gap) => (
            <div
              key={gap.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "8px 0",
                borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
              }}
            >
              <div>
                <Text weight="semibold">Control {gap.id}</Text>
                <Text size={200} style={{ display: "block" }}>
                  {gap.requirement}
                </Text>
              </div>
              <Button
                appearance="outline"
                icon={<LightbulbRegular />}
                size="small"
                onClick={() => handleExplainGap(gap.id, gap.requirement)}
              >
                Explain
              </Button>
            </div>
          ))}
        </div>
      </Card>

      {/* What-If Simulation */}
      <Card>
        <CardHeader
          image={<BeakerRegular fontSize={24} />}
          header={<Text weight="semibold">What-If Simulation</Text>}
          description={
            <Text size={200}>
              Paste a Terraform plan JSON to check it against all active policies
              before deploying
            </Text>
          }
        />
        <div className={styles.whatIfSection}>
          <Field label="Terraform Plan JSON">
            <Textarea
              placeholder='Paste output of "terraform show -json tfplan" here...'
              value={whatIfPlan}
              onChange={(_, data) => setWhatIfPlan(data.value)}
              resize="vertical"
              rows={6}
            />
          </Field>
          <div className={styles.actions}>
            <Button
              appearance="primary"
              icon={<BeakerRegular />}
              disabled={!whatIfPlan.trim()}
              onClick={handleWhatIf}
            >
              Run Simulation
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader
          image={<DocumentTextRegular fontSize={24} />}
          header={<Text weight="semibold">Evidence Narration</Text>}
          description={
            <Text size={200}>
              Generate auditor-ready prose from structured evidence for report sections
            </Text>
          }
        />
        <div className={styles.whatIfSection}>
          <div className={styles.actions}>
            <Button
              appearance="primary"
              icon={<DocumentTextRegular />}
              onClick={handleNarrateEvidence}
              disabled={narrateBusy}
            >
              {narrateBusy ? "Generating..." : "Generate Narrative"}
            </Button>
          </div>
          {narrative && (
            <div
              style={{
                whiteSpace: "pre-wrap",
                padding: "10px",
                border: `1px solid ${tokens.colorNeutralStroke1}`,
                borderRadius: tokens.borderRadiusMedium,
                background: tokens.colorNeutralBackground3,
              }}
            >
              <Text>{narrative}</Text>
            </div>
          )}
        </div>
      </Card>

      {/* Report History */}
      <Card>
        <CardHeader
          header={<Text weight="semibold">Report History</Text>}
        />
        <div className={styles.emptyState}>
          <ClipboardTextLtrRegular fontSize={48} />
          <Text size={400} weight="semibold">
            No reports yet
          </Text>
          <Text size={300}>
            Complete an evidence collection or policy enforcement session to
            generate your first report.
          </Text>
        </div>
      </Card>

      {/* Chat Dialog */}
      <Dialog open={chatOpen} onOpenChange={(_, data) => setChatOpen(data.open)}>
        <DialogSurface className={styles.chatDialog}>
          <DialogBody style={{ height: "100%" }}>
            <DialogTitle>Compliance Assistant</DialogTitle>
            <DialogContent style={{ flex: 1, minHeight: 0 }}>
              {chatOpen && chatMessage && (
                <ChatPanel
                  key={chatMessage}
                  initialMessage={chatMessage}
                />
              )}
            </DialogContent>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
}
