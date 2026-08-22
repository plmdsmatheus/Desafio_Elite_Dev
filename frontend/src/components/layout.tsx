import { CalendarDays, LayoutDashboard, LogIn, LogOut, ScanLine, Ticket, UserPlus } from "lucide-react"
import { type ComponentType, type SVGProps } from "react"
import { NavLink, Outlet, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/hooks/use-auth"
import { cn } from "@/lib/utils"
import type { UserRole } from "@/types"

const ROLE_LINK: Record<UserRole, { to: string; label: string; icon: ComponentType<SVGProps<SVGSVGElement>> }> = {
  organizer: { to: "/organizador", label: "Meus eventos", icon: LayoutDashboard },
  customer: { to: "/meus-ingressos", label: "Meus ingressos", icon: Ticket },
  gate: { to: "/portaria", label: "Portaria", icon: ScanLine },
}

const navLinkClassName = ({ isActive }: { isActive: boolean }) =>
  cn(
    "flex items-center gap-1.5 transition-colors hover:text-primary",
    isActive ? "font-medium text-foreground" : "text-muted-foreground",
  )

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate("/")
  }

  const RoleIcon = user ? ROLE_LINK[user.role].icon : null

  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3">
          <NavLink to="/" className="flex shrink-0 items-center gap-1.5 font-semibold">
            <Ticket className="size-4.5 text-primary" />
            Plataforma de Eventos
          </NavLink>

          <nav className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <NavLink to="/eventos" className={navLinkClassName}>
              <CalendarDays className="size-4" />
              Eventos
            </NavLink>
            {user ? (
              <>
                <NavLink to={ROLE_LINK[user.role].to} className={navLinkClassName}>
                  {RoleIcon && <RoleIcon className="size-4" />}
                  {ROLE_LINK[user.role].label}
                </NavLink>
                <span className="hidden text-muted-foreground sm:inline">{user.email}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLogout}
                  className="hover:bg-background hover:text-primary"
                >
                  <LogOut />
                  Sair
                </Button>
              </>
            ) : (
              <>
                <NavLink to="/login" className={navLinkClassName}>
                  <LogIn className="size-4" />
                  Entrar
                </NavLink>
                <Button
                  asChild
                  size="sm"
                  variant="outline"
                  className="border-white text-white hover:bg-background hover:text-primary"
                >
                  <NavLink to="/cadastro">
                    <UserPlus />
                    Criar conta
                  </NavLink>
                </Button>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
