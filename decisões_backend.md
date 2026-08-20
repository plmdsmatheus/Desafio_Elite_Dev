# Diagramas de Arquitetura — Plataforma de Eventos e Ingressos

Este documento reúne os principais diagramas arquiteturais da plataforma e destaca as decisões técnicas que justificam a estrutura escolhida.

---

## 1. Visão geral da arquitetura

```mermaid
flowchart LR
    FE["Frontend<br/>React + Vite"]

    API["Backend<br/>Django + DRF"]

    DB[("PostgreSQL")]

    TM["Ticketmaster<br/>Discovery API"]
    TMDB["TMDb API"]

    FE -->|"HTTP/JSON<br/>JWT"| API

    API --> DB
    API --> TM
    API --> TMDB

    subgraph Backend["Backend"]
        API
    end

    subgraph External["Serviços externos"]
        TM
        TMDB
    end
```

### Decisão técnica

O frontend se comunica somente com o backend. As integrações com Ticketmaster e TMDb ficam centralizadas no Django.

Isso protege as chaves das APIs externas, reduz o acoplamento do frontend aos fornecedores e permite que o backend normalize as respostas externas.

---

## 2. Arquitetura interna do Django

```mermaid
flowchart TD
    Accounts["accounts<br/>Usuários + JWT + Permissions"]

    Events["events<br/>Eventos + CRUD"]

    Catalog["catalog<br/>Ticketmaster + TMDb"]

    Ticketing["ticketing<br/>Reservas + Pagamentos + Tickets"]

    Accounts --> Events
    Events --> Ticketing
    Events --> Catalog

    Ticketing -.->|"FK Event"| Events
    Catalog -.->|"consulta/mapeamento"| Events
```

### Responsabilidades

| App | Responsabilidade |
|---|---|
| `accounts` | Usuários, papéis, JWT e permissions |
| `catalog` | Integração com Ticketmaster/TMDb |
| `events` | CRUD e consulta de eventos |
| `ticketing` | Reservas, pagamentos, ingressos e validação |

### Decisão técnica

Os apps são separados por domínio de negócio. Isso reduz o acoplamento e mantém cada módulo responsável por uma parte específica do sistema.

A direção principal das dependências é:

```text
accounts
   │
   ▼
events
   │
   ├──────────────► catalog
   │
   ▼
ticketing
```

`events` não importa `ticketing` diretamente no nível de módulo. A propriedade `Event.tickets_sold` utiliza import local para evitar uma dependência circular, já que `Reservation` referencia `Event`.

---

## 3. Integração com catálogo externo e snapshot

```mermaid
sequenceDiagram
    actor O as Organizador
    participant FE as Frontend
    participant API as Django API
    participant CAT as Catalog
    participant TM as Ticketmaster/TMDb
    participant DB as PostgreSQL

    O->>FE: Busca evento
    FE->>API: GET /api/catalog/search
    API->>CAT: search(query)
    CAT->>TM: Consulta API externa
    TM-->>CAT: Dados externos
    CAT-->>API: CatalogItem normalizado
    API-->>FE: Resultado

    O->>FE: Seleciona item
    FE->>API: POST /api/events
    API->>DB: Salva snapshot do evento
    DB-->>API: Event criado
    API-->>FE: Evento
```

### Snapshot do catálogo

```mermaid
flowchart LR
    External["Ticketmaster / TMDb"]

    Catalog["CatalogProvider"]

    Snapshot["Event<br/>source_provider<br/>source_id<br/>title<br/>description<br/>image_url<br/>..."]

    External --> Catalog
    Catalog --> Snapshot

    Snapshot -.->|"A partir daqui<br/>independente da API"| External
```

### Decisão técnica

O catálogo externo é utilizado como fonte de descoberta, não como uma referência viva do evento.

Depois que o organizador escolhe um item, os dados são copiados para `Event`. O organizador pode editar esses dados posteriormente sem depender da disponibilidade ou do estado atual da API externa.

---

## 4. Fluxo de reserva e pagamento

```mermaid
sequenceDiagram
    actor C as Cliente
    participant API as Django API
    participant DB as PostgreSQL

    C->>API: POST /api/reservations
    API->>DB: Cria Reservation
    DB-->>API: status = pending
    API-->>C: Reserva criada

    C->>API: POST /reservations/{id}/pay

    API->>DB: LOCK Reservation
    API->>DB: LOCK Event

    API->>DB: Calcula tickets_sold

    alt Capacidade disponível
        API->>DB: Payment = approved
        API->>DB: Reservation = paid
        API->>DB: Cria Tickets
        DB-->>API: Commit
        API-->>C: Pagamento aprovado
    else Capacidade esgotada
        API->>DB: Payment = declined
        API->>DB: Reservation = declined
        DB-->>API: Commit
        API-->>C: Pagamento recusado
    end
```

### Estados da reserva

```mermaid
stateDiagram-v2
    [*] --> pending: Criar reserva

    pending --> paid: Pagamento aprovado
    pending --> declined: Pagamento recusado
    pending --> canceled: Cancelamento

    paid --> [*]
    declined --> [*]
    canceled --> [*]
```

### Decisão técnica

Criar uma reserva não significa consumir o estoque.

Somente reservas com:

```text
Reservation.status == "paid"
```

são consideradas no cálculo de ingressos vendidos.

Isso separa claramente:

- intenção de compra;
- processamento do pagamento;
- consumo efetivo da capacidade.

---

## 5. Concorrência e controle de capacidade

Essa é uma das principais decisões técnicas da aplicação.

### Problema

Imagine um evento com capacidade para 100 pessoas e apenas 2 vagas restantes.

Dois clientes podem tentar comprar 2 ingressos simultaneamente.

Sem controle de concorrência:

```text
Cliente A                    Cliente B
    │                            │
    │ tickets_sold = 98         │
    │                            │
    │                            │ tickets_sold = 98
    │                            │
    │ compra 2                   │ compra 2
    │                            │
    └────────────┬───────────────┘
                 ▼
          102 ingressos
          CAPACIDADE = 100
                 ❌
```

### Solução com row locking

```mermaid
sequenceDiagram
    actor A as Cliente A
    actor B as Cliente B

    participant API as Django
    participant DB as PostgreSQL

    A->>API: Pagar reserva A
    B->>API: Pagar reserva B

    API->>DB: SELECT Event FOR UPDATE
    DB-->>API: Event bloqueado

    API->>DB: Calcula tickets_sold
    API->>DB: Aprova A
    API->>DB: Commit

    DB-->>API: Libera lock

    API->>DB: SELECT Event FOR UPDATE
    DB-->>API: Event bloqueado

    API->>DB: Calcula tickets_sold novamente

    alt Ainda há capacidade
        API->>DB: Aprova B
    else Capacidade atingida
        API->>DB: Recusa B
    end

    API->>DB: Commit
```

### Garantia

O pagamento utiliza:

```text
transaction.atomic()
        +
select_for_update()
```

A reserva é bloqueada e o evento também é bloqueado antes da decisão final de pagamento.

A capacidade é recalculada dentro da transação e dentro do lock.

### Por que essa abordagem?

O objetivo é impedir que duas transações concorrentes enxerguem simultaneamente o mesmo estoque disponível e ultrapassem a capacidade do evento.

---

## 6. Proteção contra pagamento duplicado

O lock também protege contra situações como:

- duplo clique;
- retry de rede;
- duas requisições simultâneas;
- tentativa de pagar novamente a mesma reserva.

```mermaid
sequenceDiagram
    actor C as Cliente
    participant API as Django
    participant DB as PostgreSQL

    C->>API: POST /pay
    C->>API: POST /pay

    API->>DB: LOCK Reservation
    DB-->>API: Reservation bloqueada

    API->>DB: Verifica status
    API->>DB: Processa pagamento
    API->>DB: Commit

    DB-->>API: Libera lock

    API->>DB: Segunda requisição adquire lock
    API->>DB: Reconfere status

    alt Reserva já paga
        API-->>C: Operação rejeitada / já processada
    else Ainda pendente
        API->>DB: Processa pagamento
    end
```

### Decisão técnica

O status da reserva é reconferido **dentro da transação**, e não apenas antes dela.

Isso evita que duas requisições criem dois pagamentos para a mesma reserva.

---

## 7. Segurança do QR Code

O QR Code não contém simplesmente o `public_code`.

O código é assinado pelo backend utilizando o mecanismo de signing do Django.

```mermaid
flowchart LR
    Code["public_code"]

    Sign["Django signing<br/>SECRET_KEY + salt"]

    QR["QR Code<br/>payload assinado"]

    Gate["Portaria"]

    API["POST /api/gate/validate"]

    Verify["Verifica assinatura"]

    Ticket["Ticket"]

    Code --> Sign
    Sign --> QR

    QR --> Gate
    Gate --> API
    API --> Verify

    Verify -->|válido| Ticket
    Verify -->|inválido| Reject["❌ Rejeitado"]
```

### Por que assinar o QR?

O backend possui o `SECRET_KEY`, portanto um usuário externo não consegue simplesmente criar um payload válido para um ingresso inexistente.

A assinatura garante a autenticidade do payload.

---

## 8. Validação do ingresso na portaria

A API aceita duas formas de identificação:

1. payload assinado vindo do QR Code;
2. `public_code` digitado manualmente pela portaria.

```mermaid
flowchart TD
    Input["code recebido"]

    Verify["Tentar verificar assinatura"]

    Input --> Verify

    Verify -->|Assinatura válida| Signed["Usar código assinado"]
    Verify -->|Falhou / código manual| Manual["Buscar public_code"]

    Signed --> Ticket["Ticket"]
    Manual --> Ticket

    Ticket --> Lock["select_for_update()"]

    Lock --> Check{"Ticket status == valid?"}

    Check -->|Sim| Used["Entrada autorizada<br/>status = used"]
    Check -->|Não| Invalid["❌ Entrada recusada"]
```

### Controle contra dupla validação

```mermaid
sequenceDiagram
    actor G1 as Portaria 1
    actor G2 as Portaria 2

    participant API as Django
    participant DB as PostgreSQL

    G1->>API: Validar Ticket X
    G2->>API: Validar Ticket X

    API->>DB: SELECT Ticket FOR UPDATE
    DB-->>API: Ticket bloqueado

    API->>DB: Verifica status = valid
    API->>DB: status = used
    API->>DB: Commit

    DB-->>API: Libera lock

    API->>DB: Segunda requisição obtém lock
    API->>DB: Verifica status = used

    API-->>G2: ❌ Ticket já utilizado
```

### Decisão técnica

O ticket é bloqueado durante a validação.

Assim, duas portarias não conseguem validar o mesmo ingresso simultaneamente.

---

## 9. Modelo de dados

```mermaid
erDiagram
    User ||--o{ Event : "organiza"
    User ||--o{ Reservation : "reserva"
    User ||--o{ Ticket : "possui"

    Event ||--o{ Reservation : "tem"
    Event ||--o{ Ticket : "tem"

    Reservation ||--o| Payment : "gera"
    Reservation ||--o{ Ticket : "emite"

    User {
        int id PK
        string email UK
        string role
        string password
    }

    Event {
        int id PK
        int organizer_id FK
        string source_provider
        string source_id
        string title
        text description
        string image_url
        string category
        string venue_name
        string address
        string city
        datetime date_time
        int capacity
        decimal price
        string status
        datetime created_at
        datetime updated_at
    }

    Reservation {
        int id PK
        int event_id FK
        int customer_id FK
        int quantity
        string status
        decimal total_price
        datetime created_at
        datetime updated_at
    }

    Payment {
        int id PK
        int reservation_id FK
        string status
        string card_last_digits
        datetime created_at
    }

    Ticket {
        int id PK
        int reservation_id FK
        int event_id FK
        int owner_id FK
        string public_code UK
        uuid share_slug UK
        string status
        datetime used_at
        datetime created_at
    }
```

---

## 10. Por que `Ticket.event` é denormalizado?

O relacionamento principal já existe:

```text
Ticket → Reservation → Event
```

Mesmo assim, `Ticket` mantém:

```text
event_id
```

diretamente.

```mermaid
flowchart LR
    Ticket["Ticket"]

    Reservation["Reservation"]

    Event["Event"]

    Ticket --> Reservation
    Reservation --> Event

    Ticket -.->|"event_id<br/>denormalizado"| Event
```

### Decisão técnica

Essa denormalização é intencional.

Na portaria, é útil consultar diretamente o ticket e seu evento para verificar se o ingresso pertence ao evento esperado, evitando um join adicional nessa operação.

---

## 11. Arquitetura de autenticação e autorização

```mermaid
flowchart TD
    User["User"]

    Role{"role"}

    Organizer["organizer"]
    Customer["customer"]
    Gate["gate"]

    Permissions["Django Permissions"]

    IsOrganizer["IsOrganizer"]
    IsCustomer["IsCustomer"]
    IsGate["IsGate"]

    User --> Role

    Role --> Organizer
    Role --> Customer
    Role --> Gate

    Organizer --> IsOrganizer
    Customer --> IsCustomer
    Gate --> IsGate

    IsOrganizer --> Permissions
    IsCustomer --> Permissions
    IsGate --> Permissions
```

### Fluxo JWT

```mermaid
sequenceDiagram
    actor U as Usuário
    participant FE as Frontend
    participant API as Django

    U->>FE: Login com e-mail/senha
    FE->>API: POST /api/auth/login
    API-->>FE: access_token + refresh_token + usuário

    FE->>API: Request protegida
    Note over FE,API: Authorization: Bearer <access_token>

    API->>API: Valida JWT
    API->>API: Verifica permission

    alt Autorizado
        API-->>FE: 200 OK
    else Não autorizado
        API-->>FE: 403 Forbidden
    end
```

---

# 12. Resumo das principais decisões

| Problema | Decisão | Benefício |
|---|---|---|
| Organização do backend | Apps separados por domínio | Menor acoplamento |
| APIs externas | Backend como intermediário | Segurança e abstração |
| Dados externos | Snapshot em `Event` | Independência das APIs |
| Autenticação | JWT | API stateless |
| Autorização | Roles + permissions | Controle por responsabilidade |
| Estoque | Contabilizar apenas `paid` | Regra de negócio clara |
| Concorrência | `select_for_update()` | Evita overselling |
| Pagamento duplicado | Lock da `Reservation` | Idempotência operacional |
| QR Code | Payload assinado | Evita falsificação |
| Validação do ticket | Lock do `Ticket` | Evita dupla entrada |
| Ticket → Event | Denormalização | Consulta eficiente na portaria |
| Dependência circular | Import local em `tickets_sold` | Mantém separação dos apps |

---

A API completa está documentada via Swagger em `/api/docs`, conforme a arquitetura definida no projeto.
