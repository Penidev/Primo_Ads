"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MfaSetup } from "@/components/security/MfaSetup";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useCurrentUser } from "@/hooks/useAuth";

interface TosState {
  current_version: string;
  accepted_version: string | null;
  accepted_at: string | null;
  acceptance_required: boolean;
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data: user } = useCurrentUser();

  const tos = useQuery({
    queryKey: ["tos"],
    queryFn: () => api.get<TosState>("/legal/tos"),
  });

  const acceptTos = useMutation({
    mutationFn: (version: string) => api.post("/legal/tos/accept", { version }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tos"] }),
  });

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Account details, security, and legal agreements.
        </p>
      </div>

      <section className="rounded-lg border border-neutral-800 p-5">
        <h2 className="font-medium">Account</h2>
        <dl className="mt-3 space-y-2 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-neutral-500">Name</dt>
            <dd className="text-neutral-200">{user?.full_name ?? "—"}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-neutral-500">Email</dt>
            <dd className="text-neutral-200">{user?.email ?? "—"}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-neutral-500">Role</dt>
            <dd className="text-neutral-200">
              {user?.is_admin ? "Administrator" : "Member"}
            </dd>
          </div>
        </dl>
      </section>

      <MfaSetup />

      <section className="rounded-lg border border-neutral-800 p-5">
        <h2 className="font-medium">Terms of service</h2>
        {tos.data && (
          <>
            <p className="mt-1 text-sm text-neutral-400">
              Current version: {tos.data.current_version}
              {tos.data.accepted_at && (
                <>
                  {" · accepted "}
                  {new Date(tos.data.accepted_at).toLocaleDateString()}
                </>
              )}
            </p>
            {tos.data.acceptance_required ? (
              <>
                <p className="mt-3 text-sm text-amber-400">
                  You have not accepted the current terms. Accepting confirms you
                  hold the rights to any brand assets, characters, or likenesses
                  you upload.
                </p>
                <Button
                  className="mt-3"
                  onClick={() => acceptTos.mutate(tos.data!.current_version)}
                  disabled={acceptTos.isPending}
                >
                  {acceptTos.isPending ? "Recording…" : "Accept terms"}
                </Button>
              </>
            ) : (
              <p className="mt-3 text-sm text-emerald-400">
                You have accepted the current terms.
              </p>
            )}
          </>
        )}
      </section>
    </div>
  );
}
