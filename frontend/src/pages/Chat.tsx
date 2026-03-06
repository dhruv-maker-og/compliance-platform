import { Title2, Text, makeStyles } from "@fluentui/react-components";
import ChatPanel from "../components/ChatPanel";

const useStyles = makeStyles({
  page: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    height: "calc(100vh - 160px)",
  },
  chatArea: {
    flex: 1,
    minHeight: 0,
  },
});

export default function Chat() {
  const styles = useStyles();

  return (
    <div className={styles.page}>
      <div>
        <Title2>Compliance Assistant</Title2>
        <Text style={{ display: "block", marginTop: 4 }}>
          Chat with the AI compliance agent. Ask about your posture, explain
          gaps, generate policies, or run what-if simulations.
        </Text>
      </div>
      <div className={styles.chatArea}>
        <ChatPanel />
      </div>
    </div>
  );
}
