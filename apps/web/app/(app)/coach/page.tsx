"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Coaching interface — SSE streaming chat.
 *
 * POST /v1/sessions/{id}/messages → streams SSE events:
 *   token | tool_call | followups | safety | done
 *
 * API integration is wired once keys are configured (issues #1 + #2).
 * The UI is fully built and ready to connect.
 */

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  followups?: string[];
  safety?: { category: string; redirect?: string; resources?: { name: string; contact?: string }[] };
};

export default function CoachPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi! I'm your AI Life Coach. I've reviewed your life profile and I'm ready to help you make progress on what matters most. What would you like to work on today?",
      followups: [
        "Help me think through my biggest goal",
        "I'm feeling stuck — where do I start?",
        "Review my current projects with me",
      ],
    },
  ]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage(content: string) {
    if (!content.trim() || streaming) return;

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content };
    const assistantId = crypto.randomUUID();
    const assistantMsg: Message = { id: assistantId, role: "assistant", content: "" };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput("");
    setStreaming(true);

    try {
      // TODO: replace with real SSE stream via @repo/api-client
      // const token = await getToken();
      // const resp = await fetch(`${API_BASE}/v1/sessions/${sessionId}/messages`, {
      //   method: "POST",
      //   headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      //   body: JSON.stringify({ content }),
      // });
      // Stream SSE events…

      // Simulated stream for UI development
      const words = [
        "That's a great focus.",
        " Let's break this down.",
        " Based on your profile,",
        " I can see you have",
        " some momentum already.",
        " Here's what I'd suggest:",
        " start with the one thing",
        " that would move the needle most.",
      ];
      for (const word of words) {
        await new Promise((r) => setTimeout(r, 100));
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + word } : m
          )
        );
      }

      // Simulated followups
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                followups: [
                  "Tell me more about the obstacles",
                  "What does success look like?",
                  "Let's set a deadline for this",
                ],
              }
            : m
        )
      );
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: "Sorry, I couldn't connect to the coaching service. Please try again." }
            : m
        )
      );
    } finally {
      setStreaming(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 57px)",
      }}
    >
      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "var(--space-xl)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-lg)",
          maxWidth: 760,
          margin: "0 auto",
          width: "100%",
        }}
      >
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} onFollowup={sendMessage} />
        ))}
        {streaming && (
          <div style={{ display: "flex", gap: 4, alignItems: "center", paddingLeft: 4 }}>
            <span className="text-muted text-sm">Coach is thinking</span>
            <ThinkingDots />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div
        style={{
          borderTop: "1px solid var(--color-border)",
          padding: "var(--space-md) var(--space-xl)",
          background: "var(--color-surface)",
        }}
      >
        <div
          style={{
            maxWidth: 760,
            margin: "0 auto",
            display: "flex",
            gap: "var(--space-sm)",
            alignItems: "flex-end",
          }}
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Talk to your coach… (Enter to send, Shift+Enter for new line)"
            rows={1}
            disabled={streaming}
            style={{
              flex: 1,
              background: "var(--color-bg)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--color-text)",
              fontSize: 15,
              padding: "10px 14px",
              resize: "none",
              fontFamily: "inherit",
              outline: "none",
              minHeight: 42,
              maxHeight: 160,
              overflowY: "auto",
            }}
            onFocus={(e) => (e.target.style.borderColor = "var(--color-accent)")}
            onBlur={(e) => (e.target.style.borderColor = "var(--color-border)")}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || streaming}
            className="btn btn-primary"
            style={{ height: 42, opacity: !input.trim() || streaming ? 0.5 : 1 }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  onFollowup,
}: {
  message: Message;
  onFollowup: (text: string) => void;
}) {
  const isUser = message.role === "user";

  if (message.safety) {
    return <SafetyCard safety={message.safety} />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div
        style={{
          display: "flex",
          justifyContent: isUser ? "flex-end" : "flex-start",
        }}
      >
        {!isUser && (
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: "50%",
              background: "var(--color-accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 14,
              marginRight: 8,
              flexShrink: 0,
              marginTop: 2,
            }}
          >
            🤖
          </div>
        )}
        <div
          style={{
            maxWidth: "80%",
            padding: "12px 16px",
            borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
            background: isUser ? "var(--color-accent)" : "var(--color-surface-raised)",
            color: "var(--color-text)",
            fontSize: 15,
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
          }}
        >
          {message.content || <ThinkingDots />}
        </div>
      </div>

      {/* Suggested follow-ups */}
      {message.followups && message.followups.length > 0 && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 6,
            paddingLeft: 36,
          }}
        >
          {message.followups.map((f) => (
            <button
              key={f}
              onClick={() => onFollowup(f)}
              style={{
                background: "transparent",
                border: "1px solid var(--color-border)",
                borderRadius: "999px",
                color: "var(--color-muted)",
                fontSize: 13,
                padding: "4px 12px",
                cursor: "pointer",
                fontFamily: "inherit",
                transition: "border-color 0.1s, color 0.1s",
              }}
              onMouseEnter={(e) => {
                (e.target as HTMLElement).style.borderColor = "var(--color-accent)";
                (e.target as HTMLElement).style.color = "var(--color-text)";
              }}
              onMouseLeave={(e) => {
                (e.target as HTMLElement).style.borderColor = "var(--color-border)";
                (e.target as HTMLElement).style.color = "var(--color-muted)";
              }}
            >
              {f}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SafetyCard({
  safety,
}: {
  safety: { category: string; redirect?: string; resources?: { name: string; contact?: string }[] };
}) {
  const isCrisis = safety.category === "crisis";

  return (
    <div
      className="card"
      style={{
        borderColor: isCrisis ? "var(--color-danger)" : "var(--color-warning)",
        background: isCrisis ? "rgba(220,38,38,0.05)" : "rgba(217,119,6,0.05)",
      }}
    >
      {isCrisis ? (
        <>
          <p style={{ fontWeight: 600, marginBottom: 8 }}>
            You mentioned something serious.
          </p>
          <p className="text-sm text-muted" style={{ marginBottom: 16 }}>
            I&apos;m not a therapist, but I want to make sure you&apos;re okay.
            Please reach out to a crisis resource right now:
          </p>
          {safety.resources?.map((r) => (
            <div key={r.name} style={{ marginBottom: 8 }}>
              <strong className="text-sm">{r.name}</strong>
              {r.contact && (
                <p className="text-sm text-muted" style={{ marginTop: 2 }}>
                  {r.contact}
                </p>
              )}
            </div>
          ))}
        </>
      ) : (
        <>
          <p style={{ fontWeight: 600, marginBottom: 8 }}>Outside my scope</p>
          <p className="text-sm text-muted">{safety.redirect}</p>
        </>
      )}
    </div>
  );
}

function ThinkingDots() {
  return (
    <span
      style={{
        display: "inline-flex",
        gap: 3,
        alignItems: "center",
      }}
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: "var(--color-muted)",
            animation: `pulse 1.2s ${i * 0.2}s infinite`,
          }}
        />
      ))}
      <style>{`
        @keyframes pulse {
          0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </span>
  );
}
