import { Route, Routes } from "react-router-dom"
import { LoginPage } from "@/pages/auth/LoginPage"
import { RegisterPage } from "@/pages/auth/RegisterPage"
import { CheckoutPage } from "@/pages/checkout/CheckoutPage"
import { EventDetailPage } from "@/pages/events/EventDetailPage"
import { EventListPage } from "@/pages/events/EventListPage"
import { GatePage } from "@/pages/gate/GatePage"
import { EventFormPage } from "@/pages/organizer/EventFormPage"
import { OrganizerDashboardPage } from "@/pages/organizer/OrganizerDashboardPage"
import { MyTicketsPage } from "@/pages/tickets/MyTicketsPage"
import { PublicTicketPage } from "@/pages/tickets/PublicTicketPage"

function App() {
  return (
    <Routes>
      <Route path="/" element={<EventListPage />} />
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
    </Routes>
  )
}

export default App
