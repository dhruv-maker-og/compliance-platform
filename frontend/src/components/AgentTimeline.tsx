import {
  Badge,
  Card,
  CardHeader,
  Text,
  makeStyles,
  tokens,
  Spinner,
} from "@fluentui/react-components";
import type { AgentStep } from "../types";
import {
  CheckmarkCircleRegular,
  ErrorCircleRegular,
  ArrowSyncCircleRegular,
  CircleRegular,
} from "@fluentui/react-icons";

const useStyles = makeStyles({
  timeline: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  stepCard: {
    borderLeft: `3px solid ${tokens.colorNeutralStroke1}`,
    paddingLeft: "12px",
  },
  stepRunning: {
    borderLeftColor: tokens.colorBrandForeground1,
  },
  stepCompleted: {
    borderLeftColor: tokens.colorPaletteGreenForeground1,
  },
  stepFailed: {
    borderLeftColor: tokens.colorPaletteRedForeground1,
  },
  stepDetail: {
    marginTop: "4px",
    padding: "8px 12px",
    backgroundColor: tokens.colorNeutralBackground3,
    borderRadius: tokens.borderRadiusMedium,
    fontFamily: "monospace",
    fontSize: "12px",
    whiteSpace: "pre-wrap",
    maxHeight: "200px",
    overflow: "auto",
  },
  toolBadge: {
    marginTop: "4px",
  },
});

interface AgentTimelineProps {
  steps: AgentStep[];
  isStreaming: boolean;
}

export default function AgentTimeline({ steps, isStreaming }: AgentTimelineProps) {
  const styles = useStyles();

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckmarkCircleRegular color={tokens.colorPaletteGreenForeground1} />;
      case "failed":
        return <ErrorCircleRegular color={tokens.colorPaletteRedForeground1} />;
      case "running":
        return <ArrowSyncCircleRegular color={tokens.colorBrandForeground1} />;
      default:
        return <CircleRegular />;
    }
  };

  const getCardClass = (status: string) => {
    switch (status) {
      case "completed":
        return `${styles.stepCard} ${styles.stepCompleted}`;
      case "failed":
        return `${styles.stepCard} ${styles.stepFailed}`;
      case "running":
        return `${styles.stepCard} ${styles.stepRunning}`;
      default:
        return styles.stepCard;
    }
  };

  return (
    <div className={styles.timeline}>
      {steps.map((step, index) => (
        <Card key={index} className={getCardClass(step.status)} size="small">
          <CardHeader
            image={getStatusIcon(step.status)}
            header={
              <Text weight="semibold" size={300}>
                Step {step.step_number}: {step.action}
              </Text>
            }
            description={
              <Text size={200}>
                {new Date(step.timestamp).toLocaleTimeString()}
              </Text>
            }
          />
          {step.tool_name && (
            <div className={styles.toolBadge}>
              <Badge appearance="outline" size="small">
                Tool: {step.tool_name}
              </Badge>
            </div>
          )}
          {step.detail && (
            <div className={styles.stepDetail}>{step.detail}</div>
          )}
        </Card>
      ))}
      {isStreaming && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 8 }}>
          <Spinner size="tiny" />
          <Text size={200}>Agent is working...</Text>
        </div>
      )}
    </div>
  );
}
