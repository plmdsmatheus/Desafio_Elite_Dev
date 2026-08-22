import { Html5Qrcode } from "html5-qrcode"
import { Camera } from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"
import { Button } from "@/components/ui/button"

const RESUME_DELAY_MS = 2500

interface QrScannerProps {
  onScan: (text: string) => void
}

type ScannerState = "idle" | "starting" | "running" | "error"

/** Camera-based QR reader, built on the low-level `Html5Qrcode` API instead of
 * `Html5QrcodeScanner` so the "activate camera" affordance can be a real
 * shadcn Button in Portuguese — the library's own high-level widget renders
 * an unstyled English "Request Camera Permissions" button that testers kept
 * mistaking for a broken/denied-permission state instead of something to
 * click. Pauses the feed right after a hit so the same badge held in frame
 * doesn't fire the same scan repeatedly, then auto-resumes a couple seconds
 * later. The manual code input next to it (GatePage) covers the case where
 * camera access truly isn't available, so validation never depends on this
 * working. */
export function QrScanner({ onScan }: QrScannerProps) {
  const containerId = useId().replace(/[^a-zA-Z0-9]/g, "")
  const onScanRef = useRef(onScan)
  const scannerRef = useRef<Html5Qrcode | null>(null)
  const resumeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [state, setState] = useState<ScannerState>("idle")
  const [errorMessage, setErrorMessage] = useState("")

  useEffect(() => {
    onScanRef.current = onScan
  }, [onScan])

  useEffect(() => {
    return () => {
      if (resumeTimerRef.current) clearTimeout(resumeTimerRef.current)
      const scanner = scannerRef.current
      if (!scanner) return
      if (scanner.isScanning) {
        scanner
          .stop()
          .catch(() => {})
          .finally(() => scanner.clear())
      } else {
        scanner.clear()
      }
    }
  }, [])

  async function handleStart() {
    setState("starting")
    setErrorMessage("")
    const scanner = new Html5Qrcode(containerId)
    scannerRef.current = scanner

    try {
      await scanner.start(
        { facingMode: "environment" },
        {
          fps: 10,
          // A fixed 250x250 box overflows a narrow viewfinder (this container
          // is aspect-video: below ~444px wide, the frame is under 250px
          // tall) — html5-qrcode clamps an oversized qrbox's width but not
          // its height, so the box spills past the bottom edge and gets
          // sliced by this container's own overflow-hidden. Sizing it as a
          // fraction of the real viewfinder keeps it inside the frame always.
          qrbox: (viewfinderWidth, viewfinderHeight) => {
            const size = Math.floor(Math.min(viewfinderWidth, viewfinderHeight) * 0.7)
            return { width: size, height: size }
          },
        },
        (decodedText) => {
          onScanRef.current(decodedText)
          scanner.pause(true)
          resumeTimerRef.current = setTimeout(() => {
            try {
              scanner.resume()
            } catch {
              // Component may have unmounted (event switch) between the pause
              // and this timer firing — nothing to resume in that case.
            }
          }, RESUME_DELAY_MS)
        },
        () => {
          // Fires continuously while no QR is in frame — expected, not an error.
        },
      )
      setState("running")
    } catch {
      setState("error")
      setErrorMessage(
        "Não foi possível acessar a câmera. Verifique se o navegador tem permissão pra usar a câmera nesse site, ou use o código manual ao lado.",
      )
    }
  }

  async function handleStop() {
    const scanner = scannerRef.current
    try {
      if (scanner?.isScanning) await scanner.stop()
    } finally {
      scanner?.clear()
      setState("idle")
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Fixed-aspect box so the container has real (non-zero) dimensions the
       * moment `start()` measures it — Html5Qrcode sizes the video off the
       * container's rect at start time and never re-measures later, so if
       * this were display:none (or zero-height) while idle, the video would
       * stream successfully but render at 0x0 forever. The idle/error state
       * sits on top as an overlay instead of replacing this element. */}
      <div className="relative aspect-video overflow-hidden rounded-lg border bg-muted/30">
        <div id={containerId} className="absolute inset-0 [&_video]:size-full [&_video]:object-cover" />
        {state !== "running" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-background p-6 text-center">
            <Camera className="size-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              {state === "error" ? errorMessage : "Ative a câmera do aparelho pra ler o QR code do ingresso."}
            </p>
            <Button type="button" onClick={handleStart} disabled={state === "starting"}>
              {state === "starting" ? "Solicitando acesso..." : "Ativar câmera"}
            </Button>
          </div>
        )}
      </div>
      {state === "running" && (
        <Button type="button" variant="outline" onClick={handleStop}>
          Parar câmera
        </Button>
      )}
    </div>
  )
}
