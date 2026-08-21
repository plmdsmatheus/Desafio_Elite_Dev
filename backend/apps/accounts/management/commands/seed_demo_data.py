from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Event
from apps.ticketing.models import Payment, Reservation, Ticket

DEMO_PASSWORD = "demo1234"

# Extra published events beyond the 3 "flagship" ones above — just enough
# volume (10, on top of Hamilton/Duna/Noite Acústica = 13 total) to exercise
# the carousel (page 1) and pagination (PAGE_SIZE=6, so this spans 3 pages)
# with real content. Same idea as the flagship events: title/image/synopsis
# and, for shows, venue/address/city all come from a real live search against
# Ticketmaster Discovery / TMDb — not invented. TMDb never suggests a venue
# (movies don't have one), so those four have an organizer-picked Brazilian
# cinema, matching how this would actually work in the real creation flow.
EXTRA_REAL_EVENTS = [
    dict(
        title="Wicked (Touring)",
        source_provider=Event.SourceProvider.TICKETMASTER,
        source_id="G5eVZ_2Mi0rxo",
        description=(
            "O fenômeno da Broadway que conta a história não contada das bruxas de Oz, "
            "antes de Dorothy cair de paraquedas em Munchkinland."
        ),
        image_url="https://s1.ticketm.net/dam/a/8f4/eac77d3f-de25-40f5-af88-00ea8c1568f4_SOURCE",
        category=Event.Category.SHOW,
        venue_name="DPAC",
        address="123 Vivian St",
        city="Durham",
        days_from_now=15,
        capacity=150,
        price=Decimal("180.00"),
    ),
    dict(
        title="Chicago - The Musical",
        source_provider=Event.SourceProvider.TICKETMASTER,
        source_id="Z7r9jZ1A7x3x3",
        description=(
            "Assassinato, ganância, corrupção, violência, traição — tudo que fazemos de "
            "melhor, num dos musicais mais premiados de todos os tempos."
        ),
        image_url="https://s1.ticketm.net/dam/a/ff9/5e9369f8-04d5-4a67-a77c-f850943fcff9_SOURCE",
        category=Event.Category.SHOW,
        venue_name="Ambassador Theatre-NY",
        address="215 W. 49th St.",
        city="New York",
        days_from_now=20,
        capacity=120,
        price=Decimal("220.00"),
    ),
    dict(
        title="STOMP",
        source_provider=Event.SourceProvider.TICKETMASTER,
        source_id="G5vVZ_CBlytbD",
        description=(
            "Percussão, dança e comédia com vassouras, latões de lixo e tudo mais que "
            "não parece um instrumento musical — até o elenco de STOMP subir no palco."
        ),
        image_url="https://s1.ticketm.net/dam/a/5e0/2de96446-3f5a-4b0f-a503-1a128c6ab5e0_SOURCE",
        category=Event.Category.SHOW,
        venue_name="Hackensack Meridian Health Theatre at the Count Basie Center",
        address="99 Monmouth St",
        city="Red Bank",
        days_from_now=25,
        capacity=80,
        price=Decimal("90.00"),
    ),
    dict(
        title="Blue Man Group",
        source_provider=Event.SourceProvider.TICKETMASTER,
        source_id="Z7r9jZ1A7-br_",
        description=(
            "Três figuras azuis silenciosas, muita percussão e tinta fluorescente numa "
            "experiência que mistura teatro, música e comédia física."
        ),
        image_url="https://s1.ticketm.net/dam/a/a30/855bbdbe-7466-447b-a847-6c731c3e4a30_SOURCE",
        category=Event.Category.SHOW,
        venue_name="ICON Park",
        address="8375 International Drive",
        city="Orlando",
        days_from_now=35,
        capacity=200,
        price=Decimal("130.00"),
    ),
    dict(
        title="Dear Evan Hansen",
        source_provider=Event.SourceProvider.TICKETMASTER,
        source_id="vvG10Z_5_VfKym",
        description=(
            "Uma mentira bem-intencionada foge do controle nesse musical vencedor do Tony "
            "sobre solidão, luto e a vontade de pertencer a algum lugar."
        ),
        image_url="https://s1.ticketm.net/dam/e/467/0714f582-50de-40b8-888e-812fae65c467_TABLET_LANDSCAPE_LARGE_16_9.jpg",
        category=Event.Category.SHOW,
        venue_name="California Theatre of the Performing Arts",
        address="562 W. 4th St",
        city="San Bernardino",
        days_from_now=50,
        capacity=90,
        price=Decimal("160.00"),
    ),
    dict(
        title="SIX the Musical",
        source_provider=Event.SourceProvider.TICKETMASTER,
        source_id="vvG1fZ_5hmye-8",
        description=(
            "As seis esposas de Henrique VIII reescrevem a própria história num show-pop "
            "concert que já virou fenômeno mundial."
        ),
        image_url="https://s1.ticketm.net/dam/a/198/6a5e0647-8703-4053-988d-a09b783f7198_SOURCE",
        category=Event.Category.SHOW,
        venue_name="Indiana University Auditorium",
        address="1211 East 7th Street",
        city="Bloomington",
        days_from_now=60,
        capacity=70,
        price=Decimal("95.00"),
    ),
    dict(
        title="Vingadores: Doutor Destino",
        source_provider=Event.SourceProvider.TMDB,
        source_id="1003596",
        description=(
            "Heróis icônicos de três universos diferentes são colocados em rota de "
            "colisão mortal e enfrentam uma ameaça que nenhum deles pode deter sozinho."
        ),
        image_url="https://image.tmdb.org/t/p/w500/j8ThEXgdGWYg1uWdSqygOSnlIA2.jpg",
        category=Event.Category.MOVIE,
        venue_name="Cinemark Shopping Iguatemi",
        address="Av. Brig. Faria Lima, 2232",
        city="São Paulo",
        days_from_now=12,
        capacity=150,
        price=Decimal("32.00"),
    ),
    dict(
        title="Divertida Mente 2",
        source_provider=Event.SourceProvider.TMDB,
        source_id="1022789",
        description=(
            "\"Divertida Mente 2\" retorna à mente da adolescente Riley, que agora "
            "precisa lidar com novas emoções chegando bem na hora em que menos espera."
        ),
        image_url="https://image.tmdb.org/t/p/w500/lHKNS35r4RTa9GO72vdadMLxoiV.jpg",
        category=Event.Category.MOVIE,
        venue_name="UCI Kinoplex BH Shopping",
        address="Av. Fleming, 1300",
        city="Belo Horizonte",
        days_from_now=18,
        capacity=100,
        price=Decimal("28.00"),
    ),
    dict(
        title="Coringa: Delírio a Dois",
        source_provider=Event.SourceProvider.TMDB,
        source_id="889737",
        description=(
            "Arthur Fleck está institucionalizado em Arkham à espera do julgamento por "
            "seus crimes como Coringa, enquanto vive um novo romance e a música nunca "
            "está muito longe."
        ),
        image_url="https://image.tmdb.org/t/p/w500/9RmVr8dPWicFyPZ5JCQK3NcBNB5.jpg",
        category=Event.Category.MOVIE,
        venue_name="Cinépolis Shopping Curitiba",
        address="Av. Cândido de Abreu, 776",
        city="Curitiba",
        days_from_now=22,
        capacity=80,
        price=Decimal("30.00"),
    ),
    dict(
        title="Batman",
        source_provider=Event.SourceProvider.TMDB,
        source_id="414906",
        description=(
            "Em seu segundo ano de combate ao crime, Batman descobre corrupção em "
            "Gotham City que se conecta à sua própria família, enquanto enfrenta um "
            "serial killer conhecido como Charada."
        ),
        image_url="https://image.tmdb.org/t/p/w500/wd7b4Nv9QBHDTIjc2m7sr0IUMoh.jpg",
        category=Event.Category.MOVIE,
        venue_name="Cinemark Salvador Shopping",
        address="Av. Tancredo Neves, 148",
        city="Salvador",
        days_from_now=28,
        capacity=110,
        price=Decimal("26.00"),
    ),
]


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

        # Real snapshot fetched from the Ticketmaster Discovery API (search
        # "Hamilton") — title, image and venue/address are the API's actual
        # response, not placeholder text. date_time stays relative to `now`
        # (not the API's real performance date) so the seed never goes stale.
        # Looked up by old title too: this event used to be seeded as "Turnê
        # Nacional 2026" with a fake image — renaming in place (instead of
        # keying update_or_create on the new title, which would just create a
        # second event) keeps its id and any tickets/reservations already
        # pointing at it intact.
        event_show = self._upsert_event(
            organizer,
            old_titles=["Turnê Nacional 2026"],
            title="Hamilton",
            defaults=dict(
                source_provider=Event.SourceProvider.TICKETMASTER,
                source_id="Z1r9uZrrZCuZ1AvPVfP",
                description=(
                    "O musical que revolucionou a Broadway conta a história de Alexander "
                    "Hamilton com hip-hop, R&B e um elenco multirracial. Vencedor de 11 "
                    "prêmios Tony, incluindo Melhor Musical."
                ),
                image_url="https://s1.ticketm.net/dam/a/d7a/6ffed4d3-61d3-44c3-8e63-cc776582fd7a_SOURCE",
                category=Event.Category.SHOW,
                venue_name="The National Theatre",
                address="1321 Pennsylvania Avenue NW",
                city="Washington",
                date_time=now + timedelta(days=45),
                capacity=100,
                price=Decimal("150.00"),
                status=Event.Status.PUBLISHED,
            ),
        )

        # Real snapshot from the TMDb API (search "Duna: Parte Dois") — title,
        # poster and synopsis are the API's actual pt-BR response. Venue/city
        # are organizer-entered by design: TMDb has no concept of a movie
        # theater, so those fields are never suggested by that provider.
        event_movie = self._upsert_event(
            organizer,
            old_titles=["Sessão Especial: Ecos do Amanhã"],
            title="Duna: Parte Dois",
            defaults=dict(
                source_provider=Event.SourceProvider.TMDB,
                source_id="693134",
                description=(
                    "A jornada de Paul Atreides continua. Ele está determinado a buscar "
                    "vingança contra aqueles que destruíram sua família e seu lar. Com a "
                    "ajuda de Chani e dos Fremen, ele embarca em uma jornada espiritual, "
                    "mística e marcial rumo ao seu destino."
                ),
                image_url="https://image.tmdb.org/t/p/w500/8LJJjLjAzAwXS40S5mx79PJ2jSs.jpg",
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

        for data in EXTRA_REAL_EVENTS:
            days_from_now = data.pop("days_from_now")
            title = data.pop("title")
            Event.objects.update_or_create(
                organizer=organizer,
                title=title,
                defaults={
                    **data,
                    "date_time": now + timedelta(days=days_from_now),
                    "status": Event.Status.PUBLISHED,
                },
            )
            # Put back what we popped — this loop runs again on every
            # `docker compose up`, and a dict is mutated in place by .pop().
            data["days_from_now"] = days_from_now
            data["title"] = title

        valid_ticket, used_ticket = self._seed_tickets(event_show, customer1)

        self.stdout.write(self.style.SUCCESS("\nDados de teste semeados com sucesso.\n"))
        self._print_summary(
            organizer, customer1, customer2, gate, event_show, event_movie, event_small,
            valid_ticket, used_ticket,
        )

    def _upsert_event(self, organizer, old_titles, title, defaults):
        """Like `update_or_create(organizer=organizer, title=title, defaults=defaults)`,
        but also matches on `old_titles` first — so renaming a seeded event's
        title (e.g. swapping in a real catalog title) updates the existing
        row in place instead of leaving it behind and creating a duplicate."""
        event = Event.objects.filter(organizer=organizer, title__in=old_titles).first()
        if event:
            for field, value in defaults.items():
                setattr(event, field, value)
            event.title = title
            event.save()
            return event

        event, _ = Event.objects.update_or_create(
            organizer=organizer, title=title, defaults=defaults
        )
        return event

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
            "Eventos publicados (destaque):",
            f"  #{event_show.id}  {event_show.title} — {event_show.city} (capacidade {event_show.capacity})",
            f"  #{event_movie.id}  {event_movie.title} — {event_movie.city} (capacidade {event_movie.capacity})",
            f"  #{event_small.id}  {event_small.title} — {event_small.city} "
            f"(capacidade {event_small.capacity}, boa pra testar a trava de concorrência)",
            f"  + {len(EXTRA_REAL_EVENTS)} eventos reais (Ticketmaster/TMDb) pra testar "
            "carrossel e paginação — veja a listagem pública.",
            "",
            f"Ingresso já validado (pra testar 'já_utilizado' direto): {used_ticket.public_code}",
            f"Ingresso ainda válido (pra testar a validação na portaria): {valid_ticket.public_code} "
            f"— evento #{event_show.id}",
        ]
        self.stdout.write("\n".join(lines))
