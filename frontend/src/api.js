const API_BASE = "/api/v1";

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseResponse(res) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function signup({ name, email, password, geminiApiKey, pineconeApiKey }) {
  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      email,
      password,
      gemini_api_key: geminiApiKey || undefined,
      pinecone_api_key: pineconeApiKey || undefined,
    }),
  });
  return parseResponse(res);
}

export async function login({ email, password }) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return parseResponse(res);
}

export async function getMe(token) {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

export async function updateKeys({ token, geminiApiKey, pineconeApiKey }) {
  const res = await fetch(`${API_BASE}/auth/keys`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({
      gemini_api_key: geminiApiKey || undefined,
      pinecone_api_key: pineconeApiKey || undefined,
    }),
  });
  return parseResponse(res);
}

export async function addConnection({ name, connectionString, dbDialect, token }) {
  const res = await fetch(`${API_BASE}/connections`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({
      name,
      connection_string: connectionString,
      db_dialect: dbDialect,
    }),
  });
  return parseResponse(res);
}

export async function listConnections(token) {
  const res = await fetch(`${API_BASE}/connections`, {
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

export async function switchConnection({ name, token }) {
  const res = await fetch(`${API_BASE}/connections/switch`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ name, session_id: "authenticated" }),
  });
  return parseResponse(res);
}

export async function removeConnection({ name, token }) {
  const res = await fetch(`${API_BASE}/connections`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ name, session_id: "authenticated" }),
  });
  return parseResponse(res);
}

export async function sendChat({ message, sessionId, responseMode, token }) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({
      user_message: message,
      session_id: sessionId || undefined,
      response_mode: responseMode || "both",
    }),
  });
  return parseResponse(res);
}

export async function getChatHistory(token) {
  const res = await fetch(`${API_BASE}/chat/history`, {
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

export async function getConnectorStatus(token) {
  const res = await fetch(`${API_BASE}/connector/status`, {
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

