import { Route, Routes } from "react-router-dom"
import { Layout } from "@/components/layout"
import { useAuth } from "@/hooks/use-auth"
import { LoginPage } from "@/pages/auth/LoginPage"
import { RegisterPage } from "@/pages/auth/RegisterPage"
import { CheckoutPage } from "@/pages/checkout/CheckoutPage"
import { EventDetailPage } from "@/pages/events/EventDetailPage"
import { EventListPage } from "@/pages/events/EventListPage"
import { HomePage } from "@/pages/events/HomePage"
import { GatePage } from "@/pages/gate/GatePage"
import { EventFormPage } from "@/pages/organizer/EventFormPage"
import { OrganizerDashboardPage } from "@/pages/organizer/OrganizerDashboardPage"
import { MyTicketsPage } from "@/pages/tickets/MyTicketsPage"
import { PublicTicketPage } from "@/pages/tickets/PublicTicketPage"

function App() {
  const { isLoading } = useAuth()

  // Avoids flashing "logged out" UI for a returning user while /auth/me resolves.
  if (isLoading) {
    return <div className="flex min-h-svh items-center justify-center text-muted-foreground">Carregando...</div>
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/eventos" element={<EventListPage />} />
        <Route path="/eventos/:eventId" element={<EventDetailPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/cadastro" element={<RegisterPage />} />
        <Route path="/checkout/:eventId" element={<CheckoutPage />} />
        <Route path="/meus-ingressos" element={<MyTicketsPage />} />
        <Route path="/t/:shareSlug" element={<PublicTicketPage />} />
        <Route path="/organizador" element={<OrganizerDashboardPage />} />
        <Route path="/organizador/eventos/novo" element={<EventFormPage />} />
        <Route path="/organizador/eventos/:eventId/editar" element={<EventFormPage />} />
        <Route path="/portaria" element={<GatePage />} />
      </Route>
    </Routes>
  )
}

export default App
