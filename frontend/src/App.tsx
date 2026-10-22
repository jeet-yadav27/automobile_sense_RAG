
import { useEffect, useState } from "react";
import Chat from "./components/Chat";
import Login from "./components/Login";
// import { getCurrentUser, logout } from "./api";
import { currentUser, refreshCsrf, logout } from "./api";
import type { User } from "./api";
import "./App.css";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    let active = true;
  
    async function checkAuth() {
      try {
        const userData = await currentUser();
  
        // Restore CSRF token after browser refresh
        await refreshCsrf();
  
        if (active) {
          setUser(userData);
        }
      } catch (error) {
        console.error("Authentication check failed:", error);
  
        if (active) {
          setUser(null);
        }
      } finally {
        if (active) {
          setCheckingAuth(false);
        }
      }
    }
  
    checkAuth();
  
    return () => {
      active = false;
    };
  }, []);

  async function handleLogout() {
    await logout();
    setUser(null);
  }

  if (checkingAuth) {
    return (
      <div className="login-page">
        <p>Checking your session...</p>
      </div>
    );
  }

  if (!user) {
    return <Login onLogin={setUser} />;
  }

  return <Chat user={user} onLogout={handleLogout} />;
}
