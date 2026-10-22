
import { useState } from "react";
import type { FormEvent } from "react";
import { login, register } from "../api";
import type { User } from "../api";

interface Props {
  onLogin: (user: User) => void;
}

export default function Login({ onLogin }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<
    "login" | "register"
  >("login");

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "register") {
        await register(email, password);
      }

      const user = await login(email, password);
      onLogin(user);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Authentication failed"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <h1>S-Presso AI Assistant</h1>
        <p>Secure warranty knowledge assistant</p>

        <h2>
          {mode === "login"
            ? "Sign in"
            : "Create account"}
        </h2>

        <input
          type="email"
          placeholder="Email address"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <input
          type="password"
          placeholder="Password"
          autoComplete={
            mode === "login"
              ? "current-password"
              : "new-password"
          }
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={mode === "register" ? 12 : undefined}
          required
        />

        {error && <p role="alert" className="error">{error}</p>}

        <button disabled={loading} type="submit">
          {loading
            ? "Please wait..."
            : mode === "login"
            ? "Sign in"
            : "Register"}
        </button>

        <button
          type="button"
          className="text-button"
          onClick={() => {
            setError("");
            setMode(
              mode === "login" ? "register" : "login"
            );
          }}
        >
          {mode === "login"
            ? "Create an account"
            : "Already registered? Sign in"}
        </button>
      </form>
    </div>
  );
}
