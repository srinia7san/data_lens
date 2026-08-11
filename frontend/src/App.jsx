import { useState, useCallback, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import ChatArea from "./components/ChatArea";
import ConnectionModal from "./components/ConnectionModal";
import AccountModal from "./components/AccountModal";
import AuthView from "./components/AuthView";
import { Menu, Trash2 } from "lucide-react";
import {
  addConnection,
  getChatHistory,
  getMe,
  listConnections,
  login,
  removeConnection,
  sendChat,
  signup,
  switchConnection,
  updateKeys,
} from "./api";

let messageIdCounter = 0;
const nextId = () => ++messageIdCounter;
const TOKEN_KEY = "datalens_token";

function hydrateHistory(items = []) {
  return items.map((item) => ({
    id: nextId(),
    role: item.role,
    text: item.content,
    sql: item.generated_sql || null,
    queryResults: item.query_results || null,
    chartConfig: item.chart_config || null,
    mode: item.response_mode || "both",
  }));
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [connections, setConnections] = useState([]);
  const [activeConnection, setActiveConnection] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [responseMode, setResponseMode] = useState("both");
  const [isLoading, setIsLoading] = useState(false);
  const [authLoading, setAuthLoading] = useState(Boolean(token));
  const [showModal, setShowModal] = useState(false);
  const [showAccountModal, setShowAccountModal] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const refreshConnections = useCallback(
    async (authToken = token) => {
      if (!authToken) return;
      const res = await listConnections(authToken);
      setConnections(res.connections || []);
      setActiveConnection(res.active_connection);
    },
    [token]
  );

  const refreshHistory = useCallback(async (authToken = token) => {
    if (!authToken) return;
    const res = await getChatHistory(authToken);
    setMessages(hydrateHistory(res.messages || []));
  }, [token]);

  const applyAuth = useCallback(
    async (authToken, authUser) => {
      localStorage.setItem(TOKEN_KEY, authToken);
      setToken(authToken);
      setUser(authUser);
      setSessionId(authUser.id);
      await refreshConnections(authToken);
      await refreshHistory(authToken);
    },
    [refreshConnections, refreshHistory]
  );

  useEffect(() => {
    if (!token) {
      setAuthLoading(false);
      return;
    }

    let cancelled = false;
    async function restoreSession() {
      try {
        const res = await getMe(token);
        if (cancelled) return;
        await applyAuth(token, res.user);
      } catch {
        if (!cancelled) {
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
          setUser(null);
        }
      } finally {
        if (!cancelled) setAuthLoading(false);
      }
    }

    restoreSession();
    return () => {
      cancelled = true;
    };
  }, [token, applyAuth]);

  const handleLogin = useCallback(
    async (payload) => {
      setAuthLoading(true);
      try {
        const res = await login(payload);
        await applyAuth(res.token, res.user);
      } catch (err) {
        alert(`Login failed: ${err.message}`);
      } finally {
        setAuthLoading(false);
      }
    },
    [applyAuth]
  );

  const handleSignup = useCallback(
    async (payload) => {
      setAuthLoading(true);
      try {
        const res = await signup(payload);
        await applyAuth(res.token, res.user);
      } catch (err) {
        alert(`Signup failed: ${err.message}`);
      } finally {
        setAuthLoading(false);
      }
    },
    [applyAuth]
  );

  const handleLogout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setSessionId(null);
    setConnections([]);
    setActiveConnection(null);
    setMessages([]);
  }, []);

  const handleUpdateKeys = useCallback(
    async ({ geminiApiKey, pineconeApiKey }) => {
      if (!token) return;
      setModalLoading(true);
      try {
        const res = await updateKeys({ token, geminiApiKey, pineconeApiKey });
        setUser(res.user);
        setShowAccountModal(false);
      } catch (err) {
        alert(`Failed to save keys: ${err.message}`);
      } finally {
        setModalLoading(false);
      }
    },
    [token]
  );

  const handleAddConnection = useCallback(
    async ({ name, connectionString, dbDialect }) => {
      if (!token) return;
      setModalLoading(true);
      try {
        const res = await addConnection({ name, connectionString, dbDialect, token });
        setActiveConnection(res.active_connection);
        await refreshConnections(token);
        setShowModal(false);
      } catch (err) {
        alert(`Failed to add connection: ${err.message}`);
      } finally {
        setModalLoading(false);
      }
    },
    [token, refreshConnections]
  );

  const handleSwitchConnection = useCallback(
    async (name) => {
      if (!token || name === activeConnection) return;
      try {
        const res = await switchConnection({ name, token });
        setActiveConnection(res.active_connection);
        await refreshConnections(token);
      } catch (err) {
        alert(`Failed to switch: ${err.message}`);
      }
    },
    [token, activeConnection, refreshConnections]
  );

  const handleRemoveConnection = useCallback(
    async (name) => {
      if (!token) return;
      try {
        const res = await removeConnection({ name, token });
        setActiveConnection(res.active_connection);
        await refreshConnections(token);
      } catch (err) {
        alert(`Failed to remove: ${err.message}`);
      }
    },
    [token, refreshConnections]
  );

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isLoading || !token) return;

    const userMsg = { id: nextId(), role: "user", text };
    const loadingMsg = { id: nextId(), role: "assistant", loading: true };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const res = await sendChat({
        message: text,
        sessionId,
        responseMode,
        token,
      });

      if (res.session_id) setSessionId(res.session_id);
      if (res.active_connection) setActiveConnection(res.active_connection);

      const isError = res.status === "error";
      const assistantMsg = {
        id: loadingMsg.id,
        role: "assistant",
        text: isError ? null : res.reply || null,
        sql: responseMode === "both" ? res.generated_sql || null : null,
        queryResults: responseMode === "both" ? res.query_results || null : null,
        chartConfig: responseMode !== "answer" ? res.chart_config || null : null,
        mode: responseMode,
        error: isError ? res.reply : null,
      };

      setMessages((prev) =>
        prev.map((m) => (m.id === loadingMsg.id ? assistantMsg : m))
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, loading: false, error: `Request failed: ${err.message}` }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, token, sessionId, responseMode]);

  const handleClearChat = useCallback(() => {
    setMessages([]);
  }, []);

  if (!user) {
    return (
      <AuthView
        onLogin={handleLogin}
        onSignup={handleSignup}
        isLoading={authLoading}
      />
    );
  }

  const hasConnection = connections.length > 0;
  const activeConn = connections.find((c) => c.name === activeConnection);

  return (
    <>
      <Sidebar
        connections={connections}
        activeConnection={activeConnection}
        onAddClick={() => setShowModal(true)}
        onSwitch={handleSwitchConnection}
        onRemove={handleRemoveConnection}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((p) => !p)}
        user={user}
        onLogout={handleLogout}
        onOpenAccountModal={() => setShowAccountModal(true)}
      />

      <main className="main-content">
        <header className="topbar">
          {sidebarCollapsed && (
            <button
              className="btn-icon"
              onClick={() => setSidebarCollapsed(false)}
              title="Open sidebar"
            >
              <Menu size={18} />
            </button>
          )}
          <div className="topbar-center">
            <span className={`active-db-badge ${hasConnection ? "connected" : ""}`}>
              <span className="badge-dot" />
              {activeConn
                ? `${activeConn.name} · ${activeConn.db_dialect}`
                : "No database connected"}
            </span>
          </div>
          <button className="btn-icon" onClick={handleClearChat} title="Clear chat">
            <Trash2 size={16} />
          </button>
        </header>

        <ChatArea
          messages={messages}
          input={input}
          onInputChange={setInput}
          onSend={handleSend}
          isLoading={isLoading}
          isDisabled={!hasConnection}
          responseMode={responseMode}
          onResponseModeChange={setResponseMode}
        />
      </main>

      {showModal && (
        <ConnectionModal
          token={token}
          onClose={() => setShowModal(false)}
          onSubmit={handleAddConnection}
          isLoading={modalLoading}
        />
      )}

      {showAccountModal && (
        <AccountModal
          user={user}
          onClose={() => setShowAccountModal(false)}
          onSubmit={handleUpdateKeys}
          isLoading={modalLoading}
        />
      )}
    </>
  );
}
