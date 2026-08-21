import { Html5QrcodeScanner } from "html5-qrcode"
import { useEffect, useId, useRef } from "react"

const RESUME_DELAY_MS = 2500

interface QrScannerProps {
  onScan: (text: string) => void
}

/** Camera-based QR reader. Self-contained: pauses the feed right after a hit
 * so the same badge held in frame doesn't fire the same scan repeatedly, then
 * auto-resumes a couple seconds later, ready for the next ticket. Renders its
 * own camera-permission/selection UI — degrades to an error message inside
 * its own box if no camera is available; the manual code input next to it
 * (GatePage) covers that case, so validation never depends on this working. */
export function QrScanner({ onScan }: QrScannerProps) {
  const containerId = useId().replace(/[^a-zA-Z0-9]/g, "")
  const onScanRef = useRef(onScan)

  useEffect(() => {
    onScanRef.current = onScan
  }, [onScan])

  useEffect(() => {
    const scanner = new Html5QrcodeScanner(
      containerId,
      { fps: 10, qrbox: { width: 250, height: 250 }, rememberLastUsedCamera: true },
      false,
    )
    let resumeTimer: ReturnType<typeof setTimeout> | undefined

    scanner.render(
      (decodedText) => {
        onScanRef.current(decodedText)
        scanner.pause(true)
        resumeTimer = setTimeout(() => {
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

    return () => {
      clearTimeout(resumeTimer)
      scanner.clear().catch(() => {})
    }
  }, [containerId])

  return <div id={containerId} className="[&_select]:rounded-md [&_button]:rounded-md" />
}
