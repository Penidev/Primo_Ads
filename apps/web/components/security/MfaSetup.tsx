"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { mfaApi, type MfaSetup as MfaSetupData } from "@/lib/mfa-api";

type Stage = "idle" | "scanning" | "saved";

export function MfaSetup() {
  const qc = useQueryClient();
  const [stage, setStage] = useState<Stage>("idle");
  const [setup, setSetup] = useState<MfaSetupData | null>(null);
  // Stored alongside the URI it was rendered from, so a QR image can never be
  // shown against a different secret than the one it encodes.
  const [qr, setQr] = useState<{ uri: string; dataUrl: string } | null>(null);
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const status = useQuery({ queryKey: ["mfa-status"], queryFn: () => mfaApi.status() });

  // Render the otpauth URI to a QR image once enrolment starts.
  const provisioningUri = setup?.provisioning_uri;
  useEffect(() => {
    if (!provisioningUri) return;
    let cancelled = false;
    QRCode.toDataURL(provisioningUri, { width: 220, margin: 1 })
      .then((dataUrl) => {
        if (!cancelled) setQr({ uri: provisioningUri, dataUrl });
      })
      .catch(() => {
        // Not fatal: the secret is still shown for manual entry. Leaving the
        // previous value in place is safe because the guard below discards any
        // image whose URI no longer matches.
      });
    return () => {
      cancelled = true;
    };
  }, [provisioningUri]);

  // Deriving this rather than clearing it in an effect means there is no render
  // in which a stale QR code is visible.
  // `qr &&` first: optional chaining alone would compare undefined === undefined
  // when there is no QR and no URI, then dereference a null.
  const qrDataUrl = qr && qr.uri === provisioningUri ? qr.dataUrl : null;

  const begin = useMutation({
    mutationFn: () => mfaApi.beginSetup(),
    onSuccess: (data) => {
      setSetup(data);
      setStage("scanning");
      setError(null);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not start setup."),
  });

  const activate = useMutation({
    mutationFn: () => mfaApi.activate(code),
    onSuccess: (data) => {
      setRecoveryCodes(data.recovery_codes);
      setStage("saved");
      setCode("");
      setError(null);
      qc.invalidateQueries({ queryKey: ["mfa-status"] });
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "That code was not accepted."),
  });

  const copyRecoveryCodes = async () => {
    try {
      await navigator.clipboard.writeText(recoveryCodes.join("\n"));
    } catch {
      setError("Could not copy. Select the codes and copy them manually.");
    }
  };

  // --- already enabled -------------------------------------------------------
  if (status.data?.mfa_enabled && stage !== "saved") {
    return (
      <div className="rounded-lg border border-neutral-800 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="font-medium">Two-factor authentication</h2>
            <p className="mt-1 text-sm text-emerald-400">Enabled</p>
            <p className="mt-2 text-xs text-neutral-500">
              {status.data.recovery_codes_remaining} recovery code
              {status.data.recovery_codes_remaining === 1 ? "" : "s"} remaining.
              {status.data.mfa_required &&
                " Admin accounts must keep this enabled."}
            </p>
          </div>
          <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[11px] text-emerald-300">
            Protected
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-800 p-5">
      <h2 className="font-medium">Two-factor authentication</h2>

      {stage === "idle" && (
        <>
          <p className="mt-1 text-sm text-neutral-400">
            Add a code from an authenticator app to your sign-in.
            {status.data?.mfa_required && (
              <span className="text-amber-400">
                {" "}
                Required for admin accounts.
              </span>
            )}
          </p>
          {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
          <Button
            className="mt-4"
            onClick={() => begin.mutate()}
            disabled={begin.isPending}
          >
            {begin.isPending ? "Preparing…" : "Set up two-factor"}
          </Button>
        </>
      )}

      {stage === "scanning" && setup && (
        <>
          <ol className="mt-3 space-y-4 text-sm text-neutral-300">
            <li>
              <p className="font-medium text-neutral-200">
                1. Scan this with your authenticator app
              </p>
              <div className="mt-2 flex flex-wrap items-start gap-4">
                {qrDataUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={qrDataUrl}
                    alt="Two-factor setup QR code"
                    className="rounded bg-white p-2"
                    width={220}
                    height={220}
                  />
                ) : (
                  <div className="flex h-[220px] w-[220px] items-center justify-center rounded border border-neutral-700 text-xs text-neutral-500">
                    Use the key below instead
                  </div>
                )}
                <div className="min-w-0">
                  <p className="text-xs text-neutral-500">
                    Or enter this key manually:
                  </p>
                  <code className="mt-1 block break-all rounded bg-neutral-900 p-2 text-xs text-neutral-200">
                    {setup.secret}
                  </code>
                  <p className="mt-2 text-xs text-neutral-500">
                    Works with Google Authenticator, 1Password, Authy, and any
                    TOTP app.
                  </p>
                </div>
              </div>
            </li>
            <li>
              <p className="font-medium text-neutral-200">
                2. Enter the 6-digit code it shows
              </p>
              <div className="mt-2 flex items-center gap-3">
                <Input
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="000000"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  className="w-32 text-center tracking-widest"
                />
                <Button
                  onClick={() => activate.mutate()}
                  disabled={code.length !== 6 || activate.isPending}
                >
                  {activate.isPending ? "Verifying…" : "Confirm"}
                </Button>
              </div>
            </li>
          </ol>
          {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
        </>
      )}

      {stage === "saved" && (
        <>
          <p className="mt-1 text-sm text-emerald-400">
            Two-factor authentication is now enabled.
          </p>
          <div className="mt-4 rounded-md border border-amber-900/60 bg-amber-500/10 p-4">
            <p className="text-sm font-medium text-amber-300">
              Save your recovery codes now
            </p>
            <p className="mt-1 text-xs text-amber-200/80">
              These are shown once. Each one works a single time if you lose your
              authenticator.
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {recoveryCodes.map((rc) => (
                <code
                  key={rc}
                  className="rounded bg-neutral-950/60 px-2 py-1 text-center text-xs text-neutral-200"
                >
                  {rc}
                </code>
              ))}
            </div>
            <Button variant="outline" className="mt-3" onClick={copyRecoveryCodes}>
              Copy codes
            </Button>
          </div>
          {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
        </>
      )}
    </div>
  );
}
