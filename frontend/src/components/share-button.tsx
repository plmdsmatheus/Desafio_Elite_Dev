import { Check, Share2 } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"

interface ShareButtonProps {
  title: string
  /** Defaults to the current page's URL — pass one explicitly when sharing
   * something other than "this page" (e.g. one ticket card among many). */
  url?: string
  size?: "default" | "sm"
}

export function ShareButton({ title, url, size = "sm" }: ShareButtonProps) {
  const [copied, setCopied] = useState(false)

  async function handleShare() {
    const shareUrl = url ?? window.location.href
    try {
      if (navigator.share) {
        await navigator.share({ title, url: shareUrl })
        return
      }
      await navigator.clipboard.writeText(shareUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // User canceled the native share sheet, or the clipboard write was
      // denied by the browser — neither is worth surfacing as an error.
    }
  }

  return (
    <Button type="button" variant="outline" size={size} onClick={handleShare} className="shrink-0">
      {copied ? <Check /> : <Share2 />}
      {copied ? "Link copiado!" : "Compartilhar"}
    </Button>
  )
}
