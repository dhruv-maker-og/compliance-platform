import {
  Card,
  CardHeader,
  Text,
  Title2,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import { ClipboardTextLtrRegular } from "@fluentui/react-icons";

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
});

export default function Reports() {
  const styles = useStyles();

  return (
    <div className={styles.page}>
      <Title2>Compliance Reports</Title2>
      <Text>
        View, download, and share compliance assessment reports and policy
        enforcement results.
      </Text>

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
    </div>
  );
}
