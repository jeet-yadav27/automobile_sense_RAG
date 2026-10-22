
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  Bot,
  Send,
  Plus,
  Trash2,
  LogOut,
  FileText,
} from "lucide-react";

import {
  listConversations,
  getMessages,
  sendMessage,
  deleteConversation,
  type Conversation,
  type ChatMessage,
  type User,
} from "../api";

interface Props {
  user: User;
  onLogout: () => Promise<void>;
}

export default function Chat({ user, onLogout }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const busy = useRef(false);

  async function refreshConversations() {
    const items = await listConversations();
    setConversations(items);
  }

  useEffect(() => {
    refreshConversations().catch(() => {
      setError("Could not load conversations");
    });
  }, []);

  async function openConversation(id: string) {
    if (busy.current) return;

    setError("");

    try {
      const items = await getMessages(id);
      setActiveId(id);
      setMessages(items);
    } catch {
      setError("Unable to load conversation");
    }
  }

  function newChat() {
    if (busy.current) return;

    setActiveId(null);
    setMessages([]);
    setQuestion("");
    setError("");
  }

  async function removeConversation(id: string) {
    if (busy.current) return;

    setError("");

    try {
      await deleteConversation(id);

      if (activeId === id) {
        setActiveId(null);
        setMessages([]);
      }

      await refreshConversations();
    } catch {
      setError("Could not delete conversation");
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const text = question.trim();

    if (!text || busy.current) return;

    busy.current = true;
    setLoading(true);
    setError("");
    setQuestion("");

    // Generate one unique ID for this logical request.
    const idempotencyKey = crypto.randomUUID();

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      sources: [],
    };

    setMessages((old) => [...old, userMessage]);

    try {
      const result = await sendMessage(
        activeId,
        text,
        idempotencyKey
      );

      setActiveId(result.conversation_id);

      setMessages((old) => [
        ...old,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: result.answer,
          sources: result.sources ?? [],
        },
      ]);

      await refreshConversations();
    } catch (err) {
      console.error("Chat request failed:", err);

      setError(
        "Request failed. Reopen the conversation before retrying."
      );

      // Reconcile messages if the backend saved the response
      // but the frontend did not receive it.
      if (activeId) {
        try {
          const savedMessages = await getMessages(activeId);
          setMessages(savedMessages);
        } catch {
          // Keep the error visible.
        }
      }
    } finally {
      busy.current = false;
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h2>S-Presso AI</h2>

        <button
          type="button"
          onClick={newChat}
          disabled={loading}
        >
          <Plus size={16} />
          New chat
        </button>

        <h3>Conversations</h3>

        {conversations.map((c) => (
          <div key={c.id} className="conversation-item">
            <button
              type="button"
              className={activeId === c.id ? "active" : ""}
              disabled={loading}
              onClick={() => openConversation(c.id)}
            >
              {c.title}
            </button>

            <button
              type="button"
              aria-label="Delete conversation"
              disabled={loading}
              onClick={() => removeConversation(c.id)}
            >
              <Trash2 size={15} />
            </button>
          </div>
        ))}

        <div className="sidebar-footer">
          <small>{user.email}</small>

          <button
            type="button"
            disabled={loading}
            onClick={() => void onLogout()}
          >
            <LogOut size={16} />
            Logout
          </button>
        </div>
      </aside>

      <section className="chat-layout">
        <header className="chat-header">
          <Bot size={25} />

          <div>
            <h1>S-Presso AI Assistant</h1>
            <p>Authenticated warranty RAG</p>
          </div>
        </header>

        <main className="chat-messages">
          {messages.length === 0 && (
            <div className="welcome">
              <Bot size={40} />
              <h2>Ask about your S-Presso</h2>
              <p>Warranty, components and maintenance</p>
            </div>
          )}

          {messages.map((m) => (
            <div
              key={m.id}
              className={`message ${m.role}`}
            >
              <div className="message-body">
                <div className="message-content">
                  {m.content}
                </div>

                {m.sources && m.sources.length > 0 && (
                  <div className="sources">
                    <strong>Retrieved sources</strong>

                    <div className="source-list">
                      {m.sources.map((s, i) => (
                        <span
                          key={i}
                          className="source-chip"
                        >
                          <FileText size={14} />
                          Page {s.page ?? "?"}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="loading">
              Searching the manual...
            </div>
          )}

          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
        </main>

        <form
          className="chat-input"
          onSubmit={submit}
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question..."
            maxLength={2000}
            disabled={loading}
          />

          <button
            type="submit"
            disabled={loading || !question.trim()}
          >
            <Send size={18} />
          </button>
        </form>
      </section>
    </div>
  );
}
