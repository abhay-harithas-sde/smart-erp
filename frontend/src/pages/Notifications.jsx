import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../lib/api";
import { fmtDateTime } from "../lib/fmt";
import { toast } from "sonner";
import { MessageCircle, Send, Phone, AlertTriangle, BarChart3, Loader2, Gauge } from "lucide-react";

// Auto-format to E.164: strip spaces/dashes, add +91 if bare 10-digit Indian number
function toE164(raw) {
  let n = raw.trim().replace(/[\s\-().]/g, "");
  if (!n) return n;
  if (!n.startsWith("+")) {
    // bare 10-digit → assume India +91
    if (/^\d{10}$/.test(n)) n = "+91" + n;
    // bare number with country code digits but no + → add +
    else if (/^\d{11,15}$/.test(n)) n = "+" + n;
  }
  return n;
}

export default function Notifications() {
  const qc = useQueryClient();
  const [phone, setPhone] = useState("");
  const [body, setBody] = useState("");

  // Display raw input, format on send
  const formattedPhone = toE164(phone);
  const phoneValid = /^\+\d{8,15}$/.test(formattedPhone);

  React.useEffect(() => { document.title = "Notifications — Smart Ledger"; }, []);

  const { data: quota } = useQuery({
    queryKey: ["notify-quota"],
    queryFn: async () => (await api.get("/notify/quota")).data,
    refetchInterval: 60_000, // refresh every minute
  });

  const { data: history = [], isLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => (await api.get("/notify/history")).data,
  });

  const onSuccess = (d) => {
    toast.success(`Sent (${d.sid?.slice(-8) || "ok"})`);
    qc.invalidateQueries({ queryKey: ["notifications"] });
    qc.invalidateQueries({ queryKey: ["notify-quota"] });
  };

  // Extract a clean message from 429 or other Twilio errors
  const onError = (e) => {
    const detail = e?.response?.data?.detail;
    if (e?.response?.status === 429) {
      const msg = typeof detail === "object" ? detail.message : detail;
      toast.error(msg || "Daily message limit reached. Try again tomorrow.");
      qc.invalidateQueries({ queryKey: ["notify-quota"] });
      return;
    }
    toast.error(typeof detail === "string" ? detail : detail?.message || "Failed to send");
  };

  const quotaExhausted = quota?.exhausted === true;

  const smsMut = useMutation({
    mutationFn: async () => (await api.post("/notify/sms", { to: formattedPhone, body })).data,
    onSuccess, onError,
  });
  const waMut = useMutation({
    mutationFn: async () => (await api.post("/notify/whatsapp/freeform", { to: formattedPhone, body })).data,
    onSuccess, onError,
  });
  const lowMut = useMutation({
    mutationFn: async () => (await api.post("/notify/low-stock-alert", { to: formattedPhone })).data,
    onSuccess, onError,
  });
  const pnlMut = useMutation({
    mutationFn: async () => (await api.post("/notify/daily-summary", { to: formattedPhone })).data,
    onSuccess, onError,
  });

  const anyPending = smsMut.isPending || waMut.isPending || lowMut.isPending || pnlMut.isPending;

  return (
    <div className="p-6 space-y-4" data-testid="notifications-page">
      <div>
        <div className="text-[10px] uppercase tracking-[0.25em] text-zinc-500 mb-1">Outbound</div>
        <h1 className="font-display text-3xl font-semibold tracking-tight">Notifications</h1>
        <p className="text-sm text-zinc-500 mt-1">SMS & WhatsApp via Twilio · Business alerts on demand</p>
      </div>

      {/* Daily quota banner */}
      {quota && (
        <div className={`flex items-center gap-3 px-4 py-3 rounded-md border text-[13px] ${
          quotaExhausted
            ? "bg-red-500/10 border-red-500/30 text-red-400"
            : quota.remaining <= 5
            ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
            : "bg-[#18181B] border-[#27272A] text-zinc-400"
        }`}>
          <Gauge className="w-4 h-4 shrink-0" />
          <div className="flex-1">
            {quotaExhausted
              ? <>Daily limit reached ({quota.sent_today}/{quota.limit} messages). Resets at midnight UTC. <a href="https://console.twilio.com" target="_blank" rel="noreferrer" className="underline">Upgrade Twilio</a> to remove the cap.</>
              : <><span className="font-medium">{quota.remaining}</span> of {quota.limit} messages remaining today (Twilio free trial limit).</>
            }
          </div>
          {/* Mini progress bar */}
          <div className="w-24 h-1.5 rounded-full bg-zinc-700 overflow-hidden shrink-0">
            <div
              className={`h-full rounded-full transition-all ${quotaExhausted ? "bg-red-500" : quota.remaining <= 5 ? "bg-amber-400" : "bg-blue-500"}`}
              style={{ width: `${Math.min(100, (quota.sent_today / quota.limit) * 100)}%` }}
            />
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Composer */}
        <div className="surface rounded-md p-5 space-y-4">
          <div>
            <label className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1.5 block">Recipient phone number</label>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="9876543210  or  +919876543210"
              data-testid="notify-phone"
              className={`w-full h-10 px-3 rounded-md bg-[#18181B] border focus:outline-none text-sm font-mono transition ${
                phone && !phoneValid ? "border-red-500/50 focus:border-red-500" : "border-[#27272A] focus:border-blue-500"
              }`}
            />
            <div className="flex items-center justify-between mt-1">
              <div className="text-[10px] text-zinc-600">10-digit numbers auto-get +91. WhatsApp requires joining sandbox first.</div>
              {phone && (
                <div className={`text-[10px] font-mono ${phoneValid ? "text-emerald-400" : "text-red-400"}`}>
                  {phoneValid ? `✓ ${formattedPhone}` : "Invalid format"}
                </div>
              )}
            </div>
          </div>

          <div>
            <label className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1.5 block">Message body</label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Type your message…"
              rows={5}
              data-testid="notify-body"
              className="w-full px-3 py-2 rounded-md bg-[#18181B] border border-[#27272A] focus:border-blue-500 focus:outline-none text-[13px]"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => smsMut.mutate()}
              disabled={!phoneValid || !body || anyPending || quotaExhausted}
              data-testid="send-sms-btn"
              className="h-10 rounded-md bg-[#18181B] border border-[#27272A] hover:border-blue-500/40 disabled:opacity-50 flex items-center justify-center gap-2 text-[13px] font-medium"
            >
              {smsMut.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Phone className="w-3.5 h-3.5" />}
              Send SMS
            </button>
            <button
              onClick={() => waMut.mutate()}
              disabled={!phoneValid || !body || anyPending || quotaExhausted}
              data-testid="send-wa-btn"
              className="h-10 rounded-md bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white flex items-center justify-center gap-2 text-[13px] font-medium"
            >
              {waMut.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <MessageCircle className="w-3.5 h-3.5" />}
              Send WhatsApp
            </button>
          </div>
        </div>

        {/* Quick actions */}
        <div className="surface rounded-md p-5 space-y-3">
          <div className="text-[10px] uppercase tracking-widest text-zinc-500">Quick alerts</div>

          <button
            onClick={() => lowMut.mutate()}
            disabled={!phoneValid || anyPending || quotaExhausted}
            data-testid="wa-lowstock-btn"
            className="w-full h-11 rounded-md bg-[#18181B] border border-[#27272A] hover:border-amber-500/40 disabled:opacity-50 flex items-center gap-3 px-4 text-left transition"
          >
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <div className="flex-1">
              <div className="text-[13px] font-medium">Low-stock digest via SMS</div>
              <div className="text-[11px] text-zinc-500">Auto-composes list of products below reorder level</div>
            </div>
            {lowMut.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
          </button>

          <button
            onClick={() => pnlMut.mutate()}
            disabled={!phoneValid || anyPending || quotaExhausted}
            data-testid="wa-pnl-btn"
            className="w-full h-11 rounded-md bg-[#18181B] border border-[#27272A] hover:border-blue-500/40 disabled:opacity-50 flex items-center gap-3 px-4 text-left transition"
          >
            <BarChart3 className="w-4 h-4 text-blue-400 shrink-0" />
            <div className="flex-1">
              <div className="text-[13px] font-medium">Today's P&L summary via SMS</div>
              <div className="text-[11px] text-zinc-500">Orders, revenue, and tax collected so far today</div>
            </div>
            {pnlMut.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
          </button>

          <div className="pt-3 mt-2 border-t border-[#27272A] text-[11px] text-zinc-500 leading-relaxed">
            <div className="font-medium text-zinc-400 mb-1">WhatsApp sandbox</div>
            To receive WhatsApp messages during testing, the recipient must first join Twilio's sandbox by sending the join code from console.twilio.com to <span className="font-mono text-zinc-400">+14155238886</span>.
          </div>
        </div>
      </div>

      {/* History */}
      <div className="surface rounded-md overflow-hidden">
        <div className="px-4 py-3 border-b border-[#27272A] font-display text-sm font-medium">Recent messages</div>
        <table className="w-full text-[12px]">
          <thead className="bg-[#18181B] text-zinc-500 uppercase tracking-wider text-[10px]">
            <tr>
              <th className="text-left px-3 py-2.5 font-medium">Sent</th>
              <th className="text-left px-3 py-2.5 font-medium">Channel</th>
              <th className="text-left px-3 py-2.5 font-medium">To</th>
              <th className="text-left px-3 py-2.5 font-medium">Body</th>
              <th className="text-left px-3 py-2.5 font-medium">SID</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#27272A]">
            {isLoading ? <tr><td colSpan={5} className="text-center py-6 text-zinc-500">Loading…</td></tr>
            : history.length === 0 ? <tr><td colSpan={5} className="text-center py-8 text-zinc-500">No messages sent yet.</td></tr>
            : history.map((n, i) => (
              <tr key={n.provider_sid || i} data-testid={`notif-row-${i}`}>
                <td className="px-3 py-2 text-zinc-400">{fmtDateTime(n.sent_at)}</td>
                <td className="px-3 py-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] uppercase tracking-wider ${n.channel === "whatsapp" ? "bg-emerald-500/10 text-emerald-400" : "bg-blue-500/10 text-blue-400"}`}>
                    {n.channel}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono text-zinc-400">{n.to}</td>
                <td className="px-3 py-2 text-zinc-400 truncate max-w-md">{n.body}</td>
                <td className="px-3 py-2 font-mono text-zinc-600 text-[10px]">{n.provider_sid?.slice(-10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
