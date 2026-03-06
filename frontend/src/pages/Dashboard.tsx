import { useEffect, useState } from "react";
import {
  Card,
  CardHeader,
  Text,
  Title1,
  Badge,
  makeStyles,
  tokens,
  Spinner,
} from "@fluentui/react-components";
import {
  ShieldCheckmarkRegular,
  DocumentSearchRegular,
  ShieldTaskRegular,
  HeartPulseRegular,
} from "@fluentui/react-icons";
import { api } from "../api/client";
import type { HealthResponse } from "../types";

const useStyles = makeStyles({
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "24px",
  },
  hero: {
    padding: "32px",
    background: `linear-gradient(135deg, ${tokens.colorBrandBackground} 0%, ${tokens.colorBrandBackground2} 100%)`,
    borderRadius: tokens.borderRadiusXLarge,
    color: tokens.colorNeutralForegroundOnBrand,
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "16px",
  },
  statCard: {
    padding: "20px",
    cursor: "pointer",
    ":hover": {
      boxShadow: tokens.shadow8,
    },
  },
  statValue: {
    fontSize: "36px",
    fontWeight: "bold",
    marginTop: "8px",
  },
  statusRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginTop: "12px",
  },
});

export default function Dashboard() {
  const styles = useStyles();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <Spinner label="Loading platform status..." />;
  }

  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <Title1>ComplianceRewind &amp; Policy Enforcer</Title1>
        <Text size={400} style={{ marginTop: 8, display: "block" }}>
          Continuous compliance evidence collection and policy-as-code
          enforcement powered by GitHub Copilot CLI SDK.
        </Text>
        <div className={styles.statusRow}>
          <HeartPulseRegular fontSize={20} />
          <Badge
            appearance="filled"
            color={health?.status === "healthy" ? "success" : "danger"}
          >
            {health?.status === "healthy" ? "Platform Healthy" : "Platform Unavailable"}
          </Badge>
          <Text size={200}>v{health?.version ?? "—"}</Text>
        </div>
      </div>

      <div className={styles.grid}>
        <Card className={styles.statCard}>
          <CardHeader
            image={<ShieldCheckmarkRegular fontSize={24} />}
            header={<Text weight="semibold">Compliance Score</Text>}
            description={<Text size={200}>Latest assessment</Text>}
          />
          <div className={styles.statValue}>—</div>
          <Text size={200}>Run an evidence collection to see your score</Text>
        </Card>

        <Card className={styles.statCard}>
          <CardHeader
            image={<DocumentSearchRegular fontSize={24} />}
            header={<Text weight="semibold">Skills Loaded</Text>}
            description={<Text size={200}>Compliance frameworks</Text>}
          />
          <div className={styles.statValue}>
            {health?.components.skills_loaded ?? 0}
          </div>
          <Text size={200}>PCI-DSS, Policy Enforcement</Text>
        </Card>

        <Card className={styles.statCard}>
          <CardHeader
            image={<ShieldTaskRegular fontSize={24} />}
            header={<Text weight="semibold">Active Sessions</Text>}
            description={<Text size={200}>Running agent workflows</Text>}
          />
          <div className={styles.statValue}>
            {health?.components.active_sessions ?? 0}
          </div>
          <Text size={200}>Evidence &amp; policy sessions</Text>
        </Card>
      </div>

      <Card>
        <CardHeader
          header={<Text weight="semibold" size={400}>Quick Actions</Text>}
        />
        <div style={{ padding: 16, display: "flex", gap: 16, flexWrap: "wrap" }}>
          <Badge appearance="tint" size="large" color="brand">
            Start Evidence Collection →
          </Badge>
          <Badge appearance="tint" size="large" color="brand">
            Generate Policy →
          </Badge>
          <Badge appearance="tint" size="large" color="brand">
            Enforce Policy →
          </Badge>
        </div>
      </Card>
    </div>
  );
}
