# PostgreSQL source schema

All seven tables belong to the rcm360 schema. The ER diagram shows primary keys, foreign keys, and the observed encounter-to-claim relationship. The claim table has a unique encounter foreign key. Every encounter has one claim in this snapshot.

~~~mermaid
erDiagram
    PATIENTS ||--o{ ENCOUNTERS : attends
    PROVIDERS ||--o{ ENCOUNTERS : serves
    PATIENTS ||--o{ CLAIMS : linked_to
    ENCOUNTERS ||--o| CLAIMS : billed_as
    PATIENTS ||--o{ DIAGNOSES : linked_to
    ENCOUNTERS ||--o{ DIAGNOSES : records
    PATIENTS ||--o{ PRESCRIPTIONS : linked_to
    ENCOUNTERS ||--o{ PRESCRIPTIONS : records
    DIAGNOSES ||--o{ PRESCRIPTIONS : prompts
    PATIENTS ||--o{ LAB_RESULTS : linked_to
    ENCOUNTERS ||--o{ LAB_RESULTS : records

    PATIENTS {
        text patient_id PK
    }
    PROVIDERS {
        text provider_id PK
        text npi UK
    }
    ENCOUNTERS {
        text encounter_id PK
        text patient_id FK
        text provider_id FK
    }
    CLAIMS {
        text claim_id PK
        text encounter_id FK, UK
        text patient_id FK
    }
    DIAGNOSES {
        text diagnosis_id PK
        text encounter_id FK
        text patient_id FK
    }
    PRESCRIPTIONS {
        text prescription_id PK
        text diagnosis_id FK
        text encounter_id FK
        text patient_id FK
    }
    LAB_RESULTS {
        text lab_id PK
        text encounter_id FK
        text patient_id FK
    }
~~~

The claim analytics view follows the claim's encounter foreign key and reads the provider ID on that encounter. Aggregate diagnosis, prescription, and lab rows to encounter grain before joining them to claim amounts.
