"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Camera, CameraOff, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { ClientApiError } from "@/lib/client-api";
import { useScanCard } from "../hooks/use-member-card";
import type { ScanResult } from "../services/member-card-api";

const QR_REGION_ID = "member-card-qr-reader";
const ACTIVE_STATUS = "active";

function initialsOf(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return `${first}${last}`.toUpperCase();
}

export function ScanPanel() {
  const t = useTranslations();
  const scanMutation = useScanCard();
  const [code, setCode] = useState("");
  const [result, setResult] = useState<ScanResult | null>(null);
  const [errorKind, setErrorKind] = useState<"invalid" | "notFound" | null>(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [cameraError, setCameraError] = useState(false);
  // Holds the Html5Qrcode instance while the camera is active.
  const scannerRef = useRef<{ stop: () => Promise<void>; clear: () => void } | null>(null);

  const verify = useCallback(
    (token: string) => {
      const trimmed = token.trim();
      if (!trimmed) return;
      scanMutation.mutate(trimmed, {
        onSuccess: (data) => {
          setResult(data);
          setErrorKind(null);
        },
        onError: (err) => {
          setResult(null);
          setErrorKind(
            err instanceof ClientApiError && err.status === 404 ? "notFound" : "invalid"
          );
        },
      });
    },
    [scanMutation]
  );

  const stopCamera = useCallback(async () => {
    const scanner = scannerRef.current;
    scannerRef.current = null;
    if (scanner) {
      try {
        await scanner.stop();
        scanner.clear();
      } catch {
        // Already stopped — ignore.
      }
    }
    setCameraOn(false);
  }, []);

  // Start the camera when toggled on; tear down on toggle-off or unmount.
  useEffect(() => {
    if (!cameraOn) return;
    let cancelled = false;
    setCameraError(false);

    (async () => {
      try {
        const { Html5Qrcode } = await import("html5-qrcode");
        if (cancelled) return;
        const scanner = new Html5Qrcode(QR_REGION_ID);
        scannerRef.current = scanner;
        await scanner.start(
          { facingMode: "environment" },
          { fps: 10, qrbox: 240 },
          (decodedText) => {
            // Decode success: stop the camera and verify the token once.
            void stopCamera();
            setCode(decodedText);
            verify(decodedText);
          },
          undefined
        );
      } catch {
        if (!cancelled) {
          setCameraError(true);
          setCameraOn(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      void stopCamera();
    };
  }, [cameraOn, stopCamera, verify]);

  function reset() {
    setResult(null);
    setErrorKind(null);
    setCode("");
  }

  function onManualSubmit(e: React.FormEvent) {
    e.preventDefault();
    verify(code);
  }

  const isActive = result?.status === ACTIVE_STATUS;

  return (
    <div className="max-w-md space-y-4">
      {/* Manual entry — the primary, camera-free path */}
      <form onSubmit={onManualSubmit} className="flex gap-2">
        <Input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder={t("scan.manualPlaceholder")}
          aria-label={t("scan.manualLabel")}
        />
        <Button type="submit" disabled={!code.trim() || scanMutation.isPending}>
          {scanMutation.isPending ? t("common.loading") : t("scan.verify")}
        </Button>
      </form>

      {/* Camera scanner (optional) */}
      <div className="space-y-2">
        <Button
          type="button"
          variant="outline"
          className="w-full"
          onClick={() => (cameraOn ? void stopCamera() : setCameraOn(true))}
        >
          {cameraOn ? (
            <>
              <CameraOff className="mr-2 h-4 w-4" />
              {t("scan.stopCamera")}
            </>
          ) : (
            <>
              <Camera className="mr-2 h-4 w-4" />
              {t("scan.startCamera")}
            </>
          )}
        </Button>
        <div id={QR_REGION_ID} className={cn("overflow-hidden rounded-lg", !cameraOn && "hidden")} />
        {cameraError && (
          <p className="text-sm text-destructive">{t("scan.cameraError")}</p>
        )}
      </div>

      {/* Result verdict */}
      {result && (
        <Card className={cn("border-2", isActive ? "border-green-600" : "border-red-600")}>
          <CardContent className="space-y-3 p-5">
            <div
              className={cn(
                "flex items-center gap-2 text-lg font-bold",
                isActive ? "text-green-600" : "text-red-600"
              )}
            >
              {isActive ? (
                <CheckCircle2 className="h-6 w-6" />
              ) : (
                <XCircle className="h-6 w-6" />
              )}
              {t(`memberCard.status.${result.status}`)}
            </div>
            <div className="flex items-center gap-4">
              <Avatar className="h-14 w-14">
                {result.photo_url ? (
                  <AvatarImage
                    src={`/api/uploads${result.photo_url.replace("/uploads", "")}`}
                    alt={result.full_name}
                  />
                ) : null}
                <AvatarFallback className="text-base font-semibold">
                  {initialsOf(result.full_name)}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0">
                <p className="truncate text-lg font-bold">{result.full_name}</p>
                <p className="font-mono text-sm text-muted-foreground">
                  {t("scan.resultNumber")} {result.member_number}
                </p>
              </div>
            </div>
            <Button type="button" variant="outline" className="w-full" onClick={reset}>
              {t("scan.scanAnother")}
            </Button>
          </CardContent>
        </Card>
      )}

      {errorKind && (
        <Card className="border-2 border-red-600">
          <CardContent className="flex items-center gap-2 p-5 text-lg font-bold text-red-600">
            <XCircle className="h-6 w-6" />
            {t(`scan.${errorKind}`)}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
