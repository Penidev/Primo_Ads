"use client";

import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/lib/admin-api";

const SEVERITY_STYLE: Record<string, string> = {
  critical: "bg-red-500/20 text-red-300",
  warning: "bg-amber-500/20 text-amber-300",
  info: "bg-neutral-700/50 text-neutral-300",
};

export default function AdminSecurityPage() {
  const alerts = useQuery({
    queryKey: ["admin-alerts"],
    queryFn: () => adminApi.alerts(),
    refetchInterval: 60_000,
  });
  const events = useQuery({
    queryKey: ["admin-security-events"],
    queryFn: () => adminApi.securityEvents(),
  });
  const audit = useQuery({
    queryKey: ["admin-audit"],
    queryFn: () => adminApi.auditLog(),
  });

  return (
    <div className="max-w-5xl space-y-10">
      <div>
        <h1 className="text-2xl font-semibold">Security</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Active alerts, anomaly signals, and the immutable record of
          administrative actions.
        </p>
      </div>

      <section>
        <h2 className="font-medium">Active alerts</h2>
        <div className="mt-3 space-y-2">
          {alerts.data?.length === 0 && (
            <p className="rounded-md border border-neutral-800 p-4 text-sm text-neutral-500">
              No thresholds currently breached.
            </p>
          )}
          {alerts.data?.map((alert) => (
            <div
              key={alert.event_type}
              className="rounded-md border border-red-900/60 bg-red-500/10 p-3 text-sm text-red-300"
            >
              <strong>{alert.label}</strong> — {alert.count} in the last{" "}
              {alert.window_minutes} minutes (threshold {alert.threshold}).
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-medium">Recent security events</h2>
        <div className="mt-3 overflow-x-auto rounded-lg border border-neutral-800">
          <table className="w-full text-sm">
            <thead className="bg-neutral-900/60 text-left text-xs text-neutral-500">
              <tr>
                <th className="p-3">When</th>
                <th className="p-3">Event</th>
                <th className="p-3">Severity</th>
                <th className="p-3">Source IP</th>
                <th className="p-3">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {events.data?.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-4 text-neutral-500">
                    Nothing recorded yet.
                  </td>
                </tr>
              )}
              {events.data?.map((event) => (
                <tr key={event.id}>
                  <td className="p-3 text-neutral-500">
                    {new Date(event.created_at).toLocaleString()}
                  </td>
                  <td className="p-3 text-neutral-200">{event.event_type}</td>
                  <td className="p-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] ${
                        SEVERITY_STYLE[event.severity] ?? SEVERITY_STYLE.info
                      }`}
                    >
                      {event.severity}
                    </span>
                  </td>
                  <td className="p-3 text-neutral-500">{event.ip_address ?? "—"}</td>
                  <td className="p-3 text-neutral-400">{event.description ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="font-medium">Audit log</h2>
        <p className="mt-1 text-xs text-neutral-500">
          Append-only. Records who changed pricing, granted credits, or altered
          accounts.
        </p>
        <div className="mt-3 overflow-x-auto rounded-lg border border-neutral-800">
          <table className="w-full text-sm">
            <thead className="bg-neutral-900/60 text-left text-xs text-neutral-500">
              <tr>
                <th className="p-3">When</th>
                <th className="p-3">Actor</th>
                <th className="p-3">Action</th>
                <th className="p-3">Target</th>
                <th className="p-3">Change</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {audit.data?.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-4 text-neutral-500">
                    No administrative actions recorded yet.
                  </td>
                </tr>
              )}
              {audit.data?.map((entry) => (
                <tr key={entry.id}>
                  <td className="p-3 text-neutral-500">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="p-3 text-neutral-300">{entry.actor_email ?? "—"}</td>
                  <td className="p-3 text-neutral-200">{entry.action}</td>
                  <td className="p-3 text-neutral-500">
                    {entry.target_type
                      ? `${entry.target_type}${
                          entry.target_id ? `: ${entry.target_id.slice(0, 20)}` : ""
                        }`
                      : "—"}
                  </td>
                  <td className="p-3 text-xs text-neutral-400">
                    {entry.detail ? JSON.stringify(entry.detail).slice(0, 90) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
