import { useCallback, useEffect, useRef, useState } from "react";
import {
  Button,
  Card,
  Spinner,
  Text,
  Textarea,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import {
  SendRegular,
  BotRegular,
  PersonRegular,
  WrenchRegular,
} from "@fluentui/react-icons";
import { api } from "../api/client";
import type { ChatMessage } from "../types";

const useStyles = makeStyles({
  root: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    minHeight: "500px",
    borderRadius: tokens.borderRadiusLarge,
    overflow: "hidden",
    border: `1px solid ${tokens.colorNeutralStroke1}`,
  },
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  messageBubble: {
    maxWidth: "80%",
    padding: "10px 14px",
    borderRadius: tokens.borderRadiusMedium,
    whiteSpace: "pre-wrap",
    lineHeight: "1.5",
    fontSize: "14px",
  },
  userBubble: {
    alignSelf: "flex-end",
    backgroundColor: tokens.colorBrandBackground,
    color: tokens.colorNeutralForegroundOnBrand,
  },
  assistantBubble: {
    alignSelf: "flex-start",
    backgroundColor: tokens.colorNeutralBackground3,
    color: tokens.colorNeutralForeground1,
  },
  toolBubble: {
    alignSelf: "flex-start",
    backgroundColor: tokens.colorPaletteYellowBackground1,
    color: tokens.colorNeutralForeground1,
    fontFamily: "monospace",
    fontSize: "12px",
  },
  messageHeader: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    marginBottom: "4px",
  },
  inputArea: {
    display: "flex",
    gap: "8px",
    padding: "12px 16px",
    borderTop: `1px solid ${tokens.colorNeutralStroke1}`,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  inputBox: {
    flex: 1,
  },
  emptyState: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "12px",
    flex: 1,
    color: tokens.colorNeutralForeground3,
    textAlign: "center",
    padding: "24px",
  },
  suggestionsGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "8px",
    marginTop: "8px",
    width: "100%",
    maxWidth: "500px",
  },
  suggestionCard: {
    cursor: "pointer",
    padding: "10px",
    textAlign: "left",
    ":hover": {
      boxShadow: tokens.shadow4,
    },
  },
  streaming: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    alignSelf: "flex-start",
    padding: "8px 14px",
  },
});

const SUGGESTION_PROMPTS = [
  {
    title: "Compliance posture",
    prompt: "What is my current compliance posture for PCI-DSS v4.0?",
  },
  {
    title: "Explain a gap",
    prompt: "Why might MFA enforcement (control 8.3) fail, and how do I fix it?",
  },
  {
    title: "Generate policy",
    prompt: "Generate an OPA policy that requires all storage accounts to enforce HTTPS-only traffic.",
  },
  {
    title: "What-if analysis",
    prompt: "What policies would a new unencrypted storage account violate?",
  },
];

interface ChatPanelProps {
  /** Pre-set an initial message to send on mount (e.g. from "Explain" button). */
  initialMessage?: string;
  /** External session ID to continue a conversation. */
  sessionId?: string;
}

export default function ChatPanel({ initialMessage, sessionId: externalSessionId }: ChatPanelProps) {
  const styles = useStyles();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(externalSessionId ?? null);
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Send the initial message on mount if provided
  useEffect(() => {
    if (initialMessage) {
      sendMessage(initialMessage);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sendMessage = async (text: string) => {
    if (!text.trim() || isStreaming) return;

    const userMsg: ChatMessage = {
      role: "user",
      content: text.trim(),
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsStreaming(true);

    try {
      const response = await api.chat.send({
        message: text.trim(),
        session_id: sessionId ?? undefined,
      });

      setSessionId(response.session_id);

      // Start SSE stream for the response
      const es = new EventSource(response.stream_url);
      eventSourceRef.current = es;

      let assistantContent = "";

      es.addEventListener("delta", (event) => {
        const data = JSON.parse(event.data);
        assistantContent += data.content || "";
        setMessages((prev) => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg?.role === "assistant") {
            return [
              ...updated.slice(0, -1),
              { ...lastMsg, content: assistantContent },
            ];
          }
          return [
            ...updated,
            {
              role: "assistant" as const,
              content: assistantContent,
              timestamp: new Date().toISOString(),
            },
          ];
        });
      });

      es.addEventListener("tool_call", (event) => {
        const data = JSON.parse(event.data);
        setMessages((prev) => [
          ...prev,
          {
            role: "tool" as const,
            content: `Using tool: ${data.content}`,
            tool_name: data.content,
            timestamp: new Date().toISOString(),
          },
        ]);
      });

      es.addEventListener("message", (event) => {
        const data = JSON.parse(event.data);
        if (data.content) {
          assistantContent = data.content;
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg?.role === "assistant") {
              return [
                ...updated.slice(0, -1),
                { ...lastMsg, content: assistantContent },
              ];
            }
            return [
              ...updated,
              {
                role: "assistant" as const,
                content: assistantContent,
                timestamp: new Date().toISOString(),
              },
            ];
          });
        }
      });

      es.addEventListener("done", () => {
        es.close();
        eventSourceRef.current = null;
        setIsStreaming(false);
      });

      es.addEventListener("error", (event) => {
        const data = (() => {
          try {
            return JSON.parse((event as MessageEvent).data);
          } catch {
            return null;
          }
        })();
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant" as const,
            content: data?.error || "An error occurred. Please try again.",
            timestamp: new Date().toISOString(),
          },
        ]);
        es.close();
        eventSourceRef.current = null;
        setIsStreaming(false);
      });

      es.onerror = () => {
        es.close();
        eventSourceRef.current = null;
        setIsStreaming(false);
      };
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant" as const,
          content: "Failed to connect to the compliance assistant. Please try again.",
          timestamp: new Date().toISOString(),
        },
      ]);
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div className={styles.root}>
      <div className={styles.messages}>
        {messages.length === 0 ? (
          <div className={styles.emptyState}>
            <BotRegular fontSize={48} />
            <Text size={400} weight="semibold">
              Compliance Assistant
            </Text>
            <Text size={300}>
              Ask me anything about your compliance posture, policies, or remediation steps.
            </Text>
            <div className={styles.suggestionsGrid}>
              {SUGGESTION_PROMPTS.map((s) => (
                <Card
                  key={s.title}
                  className={styles.suggestionCard}
                  size="small"
                  onClick={() => sendMessage(s.prompt)}
                >
                  <Text size={200} weight="semibold">
                    {s.title}
                  </Text>
                  <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
                    {s.prompt.slice(0, 60)}...
                  </Text>
                </Card>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i}>
              {msg.role === "user" && (
                <div>
                  <div
                    className={styles.messageHeader}
                    style={{ justifyContent: "flex-end" }}
                  >
                    <Text size={200} weight="semibold">You</Text>
                    <PersonRegular fontSize={14} />
                  </div>
                  <div className={`${styles.messageBubble} ${styles.userBubble}`}>
                    {msg.content}
                  </div>
                </div>
              )}
              {msg.role === "assistant" && (
                <div>
                  <div className={styles.messageHeader}>
                    <BotRegular fontSize={14} />
                    <Text size={200} weight="semibold">Compliance Assistant</Text>
                  </div>
                  <div className={`${styles.messageBubble} ${styles.assistantBubble}`}>
                    {msg.content}
                  </div>
                </div>
              )}
              {msg.role === "tool" && (
                <div>
                  <div className={styles.messageHeader}>
                    <WrenchRegular fontSize={14} />
                    <Text size={200} weight="semibold">Tool Call</Text>
                  </div>
                  <div className={`${styles.messageBubble} ${styles.toolBubble}`}>
                    {msg.content}
                  </div>
                </div>
              )}
            </div>
          ))
        )}
        {isStreaming && messages[messages.length - 1]?.role !== "assistant" && (
          <div className={styles.streaming}>
            <Spinner size="tiny" />
            <Text size={200}>Thinking...</Text>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className={styles.inputArea}>
        <Textarea
          className={styles.inputBox}
          placeholder="Ask about compliance, policies, or remediation..."
          value={input}
          onChange={(_, data) => setInput(data.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          resize="none"
          rows={1}
        />
        <Button
          appearance="primary"
          icon={<SendRegular />}
          disabled={!input.trim() || isStreaming}
          onClick={() => sendMessage(input)}
        >
          Send
        </Button>
      </div>
    </div>
  );
}
