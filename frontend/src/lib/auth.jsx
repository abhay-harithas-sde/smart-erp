import React, { createContext, useContext, useState, useEffect } from "react";
import api from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [tenant, setTenant] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Skip /auth/me check if returning from OAuth callback — AuthCallback handles it
    if (window.location.hash?.includes("session_id=")) { setLoading(false); return; }
    const token = localStorage.getItem("ath_token");
    if (!token) { setLoading(false); return; }
    api.get("/auth/me").then((r) => {
      setUser(r.data.user);
      setTenant(r.data.tenant);
    }).catch(() => {
      localStorage.removeItem("ath_token");
    }).finally(() => setLoading(false));
  }, []);

  const refresh = async () => {
    const r = await api.get("/auth/me");
    setUser(r.data.user);
    setTenant(r.data.tenant);
    return r.data;
  };

  const login = async (email, password) => {
    const r = await api.post("/auth/login", { email, password });
    localStorage.setItem("ath_token", r.data.token);
    setUser(r.data.user);
    setTenant(r.data.tenant);
    return r.data;
  };

  const signup = async (payload) => {
    const r = await api.post("/auth/signup", payload);
    localStorage.setItem("ath_token", r.data.token);
    setUser(r.data.user);
    setTenant(r.data.tenant);
    return r.data;
  };

  const logout = () => {
    localStorage.removeItem("ath_token");
    setUser(null); setTenant(null);
    window.location.href = "/login";
  };

  return (
    <AuthCtx.Provider value={{ user, tenant, loading, login, signup, logout, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
