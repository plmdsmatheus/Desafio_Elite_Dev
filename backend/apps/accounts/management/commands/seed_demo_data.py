from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Event
from apps.ticketing.models import Payment, Reservation, Ticket

DEMO_PASSWORD = "demo1234"


class Command(BaseCommand):
    help = (
        "Semeia dados de teste: 1 organizador, 2 clientes, 1 usuário de portaria e "
        "eventos publicados com ingressos disponíveis. Idempotente — pode rodar de novo "
        "a cada `docker compose up` sem duplicar nada."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        organizer = self._seed_user("organizador@demo.com", User.Role.ORGANIZER, "Organizador Demo")
        customer1 = self._seed_user("cliente1@demo.com", User.Role.CUSTOMER, "Cliente Um")
        customer2 = self._seed_user("cliente2@demo.com", User.Role.CUSTOMER, "Cliente Dois")
        gate = self._seed_user("portaria@demo.com", User.Role.GATE, "Portaria Demo")

        now = timezone.now()

        event_show, _ = Event.objects.update_or_create(
            organizer=organizer,
            title="Turnê Nacional 2026",
            defaults=dict(
                source_provider=Event.SourceProvider.TICKETMASTER,
                source_id="demo-tm-001",
                description="Show de encerramento da turnê nacional, com participações especiais.",
                image_url="https://s1.ticketm.net/dam/a/example/demo-show.jpg",
                category=Event.Category.SHOW,
                venue_name="Allianz Parque",
                address="Av. Palestra Itália, 1",
                city="São Paulo",
                date_time=now + timedelta(days=30),
                capacity=100,
                price=Decimal("150.00"),
                status=Event.Status.PUBLISHED,
            ),
        )

        event_movie, _ = Event.objects.update_or_create(
            organizer=organizer,
            title="Sessão Especial: Ecos do Amanhã",
            defaults=dict(
                source_provider=Event.SourceProvider.TMDB,
                source_id="demo-tmdb-002",
                description="Sessão especial com bate-papo com o elenco após a exibição.",
                image_url="https://image.tmdb.org/t/p/w500/demo-poster.jpg",
                category=Event.Category.MOVIE,
                venue_name="Cinemark Shopping Central",
                address="Rua das Artes, 500",
                city="Rio de Janeiro",
                date_time=now + timedelta(days=10),
                capacity=60,
                price=Decimal("35.00"),
                status=Event.Status.PUBLISHED,
            ),
        )

        event_small, _ = Event.objects.update_or_create(
            organizer=organizer,
            title="Noite Acústica — Casa Pequena",
            defaults=dict(
                source_provider=Event.SourceProvider.MANUAL,
                description=(
                    "Evento intimista, capacidade reduzida de propósito — bom pra testar a "
                    "trava de concorrência na aprovação de pagamento (poucas vagas, esgota rápido)."
                ),
                category=Event.Category.SHOW,
                venue_name="Casa de Shows Pequena",
                address="Rua Ipiranga, 88",
                city="Porto Alegre",
                date_time=now + timedelta(days=5),
                capacity=5,
                price=Decimal("80.00"),
                status=Event.Status.PUBLISHED,
            ),
        )

        Event.objects.update_or_create(
            organizer=organizer,
            title="Pré-venda Fechada 2027",
            defaults=dict(
                source_provider=Event.SourceProvider.MANUAL,
                description=(
                    "Rascunho ainda não publicado — mostra a diferença entre o painel do "
                    "organizador (GET /api/organizer/events, vê tudo) e a listagem pública "
                    "(GET /api/events/, só publicados)."
                ),
                category=Event.Category.SHOW,
                venue_name="A definir",
                city="Curitiba",
                date_time=now + timedelta(days=90),
                capacity=200,
                price=Decimal("120.00"),
                status=Event.Status.DRAFT,
            ),
        )

        valid_ticket, used_ticket = self._seed_tickets(event_show, customer1)

        self.stdout.write(self.style.SUCCESS("\nDados de teste semeados com sucesso.\n"))
        self._print_summary(
            organizer, customer1, customer2, gate, event_show, event_movie, event_small,
            valid_ticket, used_ticket,
        )

    def _seed_user(self, email, role, first_name):
        user, _ = User.objects.get_or_create(email=email, defaults={"role": role})
        user.role = role
        user.first_name = first_name
        user.is_active = True
        user.set_password(DEMO_PASSWORD)
        user.save()
        return user

    def _seed_tickets(self, event, customer):
        """2 paid tickets for customer 1 on this event: 1 already validated (so
        the "already used" state can be tested right away) and 1 still valid
        (to test real validation). Only runs on the first execution."""
        existing = Ticket.objects.filter(reservation__event=event, owner=customer)
        if existing.exists():
            tickets = list(existing.order_by("id"))
            return tickets[1], tickets[0]

        reservation = Reservation.objects.create(
            event=event,
            customer=customer,
            quantity=2,
            status=Reservation.Status.PAID,
            total_price=event.price * 2,
        )
        Payment.objects.create(
            reservation=reservation, status=Payment.Status.APPROVED, card_last_digits="1111"
        )
        tickets = Ticket.objects.bulk_create(
            [Ticket(reservation=reservation, event=event, owner=customer) for _ in range(2)]
        )

        used_ticket = tickets[0]
        used_ticket.status = Ticket.Status.USED
        used_ticket.used_at = timezone.now()
        used_ticket.save(update_fields=["status", "used_at"])

        valid_ticket = tickets[1]
        return valid_ticket, used_ticket

    def _print_summary(
        self, organizer, customer1, customer2, gate, event_show, event_movie, event_small,
        valid_ticket, used_ticket,
    ):
        lines = [
            "Credenciais de teste (senha igual pra todo mundo):",
            f"  Organizador: {organizer.email} / {DEMO_PASSWORD}",
            f"  Cliente 1:   {customer1.email} / {DEMO_PASSWORD}",
            f"  Cliente 2:   {customer2.email} / {DEMO_PASSWORD}",
            f"  Portaria:    {gate.email} / {DEMO_PASSWORD}",
            "",
            "Eventos publicados:",
            f"  #{event_show.id}  {event_show.title} — {event_show.city} (capacidade {event_show.capacity})",
            f"  #{event_movie.id}  {event_movie.title} — {event_movie.city} (capacidade {event_movie.capacity})",
            f"  #{event_small.id}  {event_small.title} — {event_small.city} "
            f"(capacidade {event_small.capacity}, boa pra testar a trava de concorrência)",
            "",
            f"Ingresso já validado (pra testar 'já_utilizado' direto): {used_ticket.public_code}",
            f"Ingresso ainda válido (pra testar a validação na portaria): {valid_ticket.public_code} "
            f"— evento #{event_show.id}",
        ]
        self.stdout.write("\n".join(lines))
