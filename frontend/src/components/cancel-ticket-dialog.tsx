import { useQueryClient } from "@tanstack/react-query"
import { Ban } from "lucide-react"
import { useState } from "react"
import { cancelTicket } from "@/api/tickets"
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
import type { Ticket } from "@/types"

interface CancelTicketDialogProps {
  ticket: Ticket
}

export function CancelTicketDialog({ ticket }: CancelTicketDialogProps) {
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
      await cancelTicket(ticket.id)
      await queryClient.invalidateQueries({ queryKey: ["my-tickets"] })
      setOpen(false)
    } catch (err) {
      setError(getApiErrorMessage(err, "Não foi possível cancelar o ingresso."))
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
          size="sm"
          className="shrink-0 text-destructive hover:bg-destructive/10 hover:text-destructive"
        >
          <Ban />
          Cancelar ingresso
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Cancelar ingresso?</DialogTitle>
          <DialogDescription>
            O ingresso <strong>{ticket.public_code}</strong> pra <strong>{ticket.event.title}</strong>{" "}
            será cancelado e a vaga volta pro estoque do evento. Essa ação não pode ser desfeita.
          </DialogDescription>
        </DialogHeader>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
            Voltar
          </Button>
          <Button type="button" variant="destructive" onClick={handleConfirm} disabled={isSubmitting}>
            {isSubmitting ? "Cancelando..." : "Cancelar ingresso"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
