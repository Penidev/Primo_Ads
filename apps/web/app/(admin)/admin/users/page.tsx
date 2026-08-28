"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { adminApi } from "@/lib/admin-api";

export default function AdminUsersPage() {
  const qc = useQueryClient();
  const [grantFor, setGrantFor] = useState<string | null>(null);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => adminApi.listUsers() });

  const refresh = () => qc.invalidateQueries({ queryKey: ["admin-users"] });

  const setStatus = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      adminApi.setUserStatus(id, active),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not update that account."),
  });

  const grant = useMutation({
    mutationFn: () => {
      if (!grantFor) throw new Error("No user selected");
      return adminApi.grantCredits(grantFor, Number(amount), reason);
    },
    onSuccess: (data) => {
      setMessage(`Credits granted. New balance: ${data.balance_credits}.`);
      setError(null);
      setGrantFor(null);
      setAmount("");
      setReason("");
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not grant credits."),
  });

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Users</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Manage accounts and issue manual credits. Every grant is written to the ledger
          with your account attached.
        </p>
      </div>

      {message && <p className="text-sm text-emerald-400">{message}</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}

      {grantFor && (
        <section className="rounded-lg border border-neutral-700 p-4">
          <h2 className="text-sm font-medium">Grant credits</h2>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Input
              type="number"
              min="1"
              placeholder="Amount"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="w-28"
            />
            <Input
              placeholder="Reason (recorded in the ledger)"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="flex-1 min-w-48"
            />
            <Button
              onClick={() => grant.mutate()}
              disabled={!amount || reason.trim().length < 3 || grant.isPending}
            >
              {grant.isPending ? "Granting…" : "Grant"}
            </Button>
            <button
              type="button"
              onClick={() => setGrantFor(null)}
              className="text-sm text-neutral-400 hover:text-white"
            >
              Cancel
            </button>
          </div>
        </section>
      )}

      <div className="overflow-x-auto rounded-lg border border-neutral-800">
        <table className="w-full text-sm">
          <thead className="bg-neutral-900/60 text-left text-xs text-neutral-500">
            <tr>
              <th className="p-3">User</th>
              <th className="p-3">Company</th>
              <th className="p-3">Industry</th>
              <th className="p-3">Joined</th>
              <th className="p-3">State</th>
              <th className="p-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-800">
            {users.data?.map((u) => (
              <tr key={u.id}>
                <td className="p-3">
                  <p className="text-neutral-100">{u.full_name ?? "—"}</p>
                  <p className="text-xs text-neutral-500">{u.email}</p>
                </td>
                <td className="p-3 text-neutral-400">{u.company_name ?? "—"}</td>
                <td className="p-3 text-neutral-400">{u.industry ?? "—"}</td>
                <td className="p-3 text-neutral-500">
                  {new Date(u.created_at).toLocaleDateString()}
                </td>
                <td className="p-3">
                  <div className="flex flex-wrap items-center gap-1">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] ${
                        u.is_active
                          ? "bg-emerald-500/20 text-emerald-300"
                          : "bg-red-500/20 text-red-300"
                      }`}
                    >
                      {u.is_active ? "Active" : "Suspended"}
                    </span>
                    {u.is_admin && (
                      <span className="rounded-full bg-brand/20 px-2 py-0.5 text-[11px] text-brand-highlight">
                        Admin
                      </span>
                    )}
                  </div>
                </td>
                <td className="p-3">
                  <div className="flex justify-end gap-3 text-xs">
                    <button
                      type="button"
                      onClick={() => {
                        setGrantFor(u.id);
                        setMessage(null);
                      }}
                      className="text-brand-highlight hover:underline"
                    >
                      Credits
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setStatus.mutate({ id: u.id, active: !u.is_active })
                      }
                      disabled={setStatus.isPending}
                      className="text-neutral-400 hover:text-white disabled:opacity-50"
                    >
                      {u.is_active ? "Suspend" : "Reactivate"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
