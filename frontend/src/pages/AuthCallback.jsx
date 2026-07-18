import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

/**
 * Handles the return from Emergent Google Auth.
 * URL will be: /#session_id=xxxxx
 * REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
 */
export default function AuthCallback() {
  const nav = useNavigate();
  const { refresh } = useAuth();
  const hasProcessed = useRef(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = window.location.hash;
    const match = hash.match(/session_id=([^&]+)/);
    if (!match) {
      setError("Missing session_id");
      return;
    }
    const sessionId = decodeURIComponent(match[1]);

    (async () => {
      try {
        const r = await api.post("/auth/google/session", null, { headers: { "X-Session-ID": sessionId } });
        localStorage.setItem("ath_token", r.data.token);
        // Clear hash and let AuthProvider re-hydrate
        window.history.replaceState(null, "", window.location.pathname);
        await refresh();
        const displayName = r.data?.user?.name || r.data?.user?.email || "there";
        toast.success(`Welcome, ${displayName}`);
        nav("/", { replace: true });
      } catch (e) {
        setError(e?.response?.data?.detail || e.message);
      }
    })();
  }, [nav, refresh]);

  return (
    <div className="min-h-screen grid place-items-center bg-[#09090B] text-zinc-400" data-testid="auth-callback">
      {error ? (
        <div className="text-center">
          <div className="text-red-400 text-sm mb-2">{error}</div>
          <button onClick={() => nav("/login")} className="text-blue-400 text-sm">Back to login</button>
        </div>
      ) : (
        <div className="flex items-center gap-3 text-sm">
          <Loader2 className="w-4 h-4 animate-spin" />
          Signing you in with Google…
        </div>
      )}
    </div>
  );
}
