
// const API_URL =
//   import.meta.env.VITE_API_URL ??
//   "http://localhost:8000";


const API_URL =
  import.meta.env.VITE_API_URL ??
  "http://127.0.0.1:8000";

export interface User {
  id: string;
  email: string;
}

export interface Source {
  page: number | null;
  chunk_id: string | null;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
}

export interface ChatResponse {
  conversation_id: string;
  question: string;
  search_question: string;
  answer: string;
  sources: Source[];
}

let csrfToken: string | null = null;

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const method = (
    options.method ?? "GET"
  ).toUpperCase();

  const headers = new Headers(options.headers);

  if (options.body) {
    headers.set("Content-Type", "application/json");
  }

  if (!["GET", "HEAD"].includes(method)) {
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  // if (!response.ok) {
  //   throw new Error(
  //     `Request failed: ${response.status}`
  //   );
  // }

  if (!response.ok) {
    const errorBody = await response.text();
  
    console.error("FastAPI validation error:", {
      status: response.status,
      body: errorBody,
    });
  
    throw new Error(
      `Request failed: ${response.status} - ${errorBody}`
    );
  }

  return response.json() as Promise<T>;
}

export async function register(
  email: string,
  password: string
) {
  return apiFetch<User>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function login(
  email: string,
  password: string
) {
  const result = await apiFetch<{
    user: User;
    csrf_token: string;
  }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  csrfToken = result.csrf_token;
  return result.user;
}

export async function currentUser() {
  return apiFetch<User>("/api/v1/auth/me");
}

export async function refreshCsrf() {
  const result = await apiFetch<{
    csrf_token: string;
  }>("/api/v1/auth/csrf");

  csrfToken = result.csrf_token;
}

export async function logout() {
  await apiFetch("/api/v1/auth/logout", {
    method: "POST",
  });
  csrfToken = null;
}

export async function listConversations() {
  return apiFetch<Conversation[]>(
    "/api/v1/conversations"
  );
}

export async function getMessages(
  conversationId: string
) {
  return apiFetch<ChatMessage[]>(
    `/api/v1/conversations/${encodeURIComponent(
      conversationId
    )}/messages`
  );
}


export async function sendMessage(
  conversationId: string | null,
  question: string,
  idempotencyKey: string,
  signal?: AbortSignal
) {
  return apiFetch<ChatResponse>(
    "/api/v1/chat",
    {
      method: "POST",
      headers: {
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify({
        conversation_id: conversationId,
        question,
      }),
      signal,
    }
  );
}


export async function deleteConversation(
  conversationId: string
) {
  return apiFetch(
    `/api/v1/conversations/${encodeURIComponent(
      conversationId
    )}`,
    { method: "DELETE" }
  );
}
