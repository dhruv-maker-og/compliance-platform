/** Custom hook for consuming Server-Sent Events streams. */

import { useCallback, useRef, useState } from "react";
import type { AgentStep } from "../types";

interface UseSSEOptions {
  onStep?: (step: AgentStep) => void;
  onComplete?: (data: Record<string, unknown>) => void;
  onError?: (error: string) => void;
}

interface UseSSEReturn {
  steps: AgentStep[];
  isStreaming: boolean;
  error: string | null;
  startStream: (url: string) => void;
  stopStream: () => void;
}

export function useSSE(options: UseSSEOptions = {}): UseSSEReturn {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const stopStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const startStream = useCallback(
    (url: string) => {
      // Clean up any existing stream
      stopStream();
      setSteps([]);
      setError(null);
      setIsStreaming(true);

      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;

      eventSource.addEventListener("step", (event) => {
        try {
          const step: AgentStep = JSON.parse(event.data);
          setSteps((prev) => [...prev, step]);
          options.onStep?.(step);
        } catch (e) {
          console.error("Failed to parse step event:", e);
        }
      });

      eventSource.addEventListener("complete", (event) => {
        try {
          const data = JSON.parse(event.data);
          options.onComplete?.(data);
        } catch (e) {
          console.error("Failed to parse complete event:", e);
        }
        stopStream();
      });

      eventSource.addEventListener("error", (event) => {
        // EventSource "error" can be a reconnect or a true error
        if (eventSource.readyState === EventSource.CLOSED) {
          const errorMsg =
            event instanceof MessageEvent ? event.data : "Stream connection lost";
          setError(errorMsg);
          options.onError?.(errorMsg);
          stopStream();
        }
      });

      // Generic onerror
      eventSource.onerror = () => {
        if (eventSource.readyState === EventSource.CLOSED) {
          setError("Stream connection closed");
          stopStream();
        }
      };
    },
    [stopStream, options]
  );

  return { steps, isStreaming, error, startStream, stopStream };
}
