import { useQueryClient } from "@tanstack/react-query"
import { Rocket } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { publishEvent } from "@/api/events"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { getApiErrorMessage } from "@/lib/api-error"
import type { Event } from "@/types"

interface PublishEventDialogProps {
  event: Event
}

/** Publishing is a deliberate, confirmed action — not just picking a value
 * off a status dropdown — because it's mostly one-way: once published, only
 * date/time and location stay editable (see EventFormPage). */
export function PublishEventDialog({ event }: PublishEventDialogProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen)
    if (!nextOpen) setError("")
  }

  async function handleConfirm() {
    setError("")
    setIsSubmitting(true)
    try {
      await publishEvent(event.id)
      await queryClient.invalidateQueries({ queryKey: ["organizer-events"] })
      await queryClient.invalidateQueries({ queryKey: ["event", String(event.id)] })
      await queryClient.invalidateQueries({ queryKey: ["events"] })
      navigate("/organizador")
    } catch (err) {
      setError(getApiErrorMessage(err, "Não foi possível publicar o evento."))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button type="button">
          <Rocket />
          Publicar evento
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Publicar "{event.title}"?</DialogTitle>
          <DialogDescription>
            O evento passa a ficar visível e disponível pra compra. Depois de publicado, só vai
            dar pra alterar data/hora e local, ou cancelar o evento — os outros campos ficam
            travados.
          </DialogDescription>
        </DialogHeader>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
            Voltar
          </Button>
          <Button type="button" onClick={handleConfirm} disabled={isSubmitting}>
            {isSubmitting ? "Publicando..." : "Publicar evento"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
