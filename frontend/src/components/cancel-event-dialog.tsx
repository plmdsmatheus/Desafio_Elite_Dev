import { useQueryClient } from "@tanstack/react-query"
import { Ban } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { cancelEvent } from "@/api/events"
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

interface CancelEventDialogProps {
  event: Event
}

/** Terminal action — once canceled, an event can't be edited again at all
 * (see EventFormPage / EventWriteSerializer). */
export function CancelEventDialog({ event }: CancelEventDialogProps) {
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
      await cancelEvent(event.id)
      await queryClient.invalidateQueries({ queryKey: ["organizer-events"] })
      await queryClient.invalidateQueries({ queryKey: ["event", String(event.id)] })
      await queryClient.invalidateQueries({ queryKey: ["events"] })
      navigate("/organizador")
    } catch (err) {
      setError(getApiErrorMessage(err, "Não foi possível cancelar o evento."))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="outline"
          className="text-destructive hover:bg-destructive/10 hover:text-destructive"
        >
          <Ban />
          Cancelar evento
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Cancelar "{event.title}"?</DialogTitle>
          <DialogDescription>
            Todos os ingressos válidos desse evento serão invalidados (ingressos já usados não são
            afetados). O evento não poderá mais ser alterado depois de cancelado. Essa ação não
            pode ser desfeita.
          </DialogDescription>
        </DialogHeader>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
            Voltar
          </Button>
          <Button type="button" variant="destructive" onClick={handleConfirm} disabled={isSubmitting}>
            {isSubmitting ? "Cancelando..." : "Cancelar evento"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
