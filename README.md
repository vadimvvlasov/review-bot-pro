# Review Bot Pro

Create a system design Review-Reply Bot ("Reputation Manager") application. 


---

# Product Specification: Review-Reply Bot (MVP) — Version 4.0



Review-Reply Bot ("Reputation Manager") is a Minimum Viable Product (MVP) designed to automate and streamline customer review response management for local businesses on geoservices (such as Google Maps, Yelp, and TripAdvisor) using generative Artificial Intelligence.



This specification (v4.0) represents a complete **Executable Product Specification**. It establishes rigid data models, validation limits, state-transition rules, and AI pipeline requirements to serve as the single source of truth for contract-driven full-stack development.



---



## 1. Repository & Project Summary (About)

The following summary is designated for the GitHub repository's **About** description:



> **AI-powered Reputation Manager MVP built with FastAPI, SQLite, and React. Synthesizes business context & brand voice to generate context-aware, structured review replies in one click. Developed as part of AI Dev Tools Zoomcamp 2026.**



---



## 2. Product Overview & Business Goals



### Problem Statement

Local business owners (restaurants, auto repair shops, beauty salons) frequently receive reviews on geoservices. Promptly and professionally replying to these reviews is critical for search rankings and customer loyalty. However, owners lack the time to draft customized replies, often resulting in ignored feedback or repetitive, robotic responses.



### Solution

Review-Reply Bot concentrates reviews in a clean, local dashboard, enabling the business owner to import reviews, generate smart, context-aware replies with a single click, customize them using plain-text AI instructions or manual editing, and copy the finalized response.



### Business Goals

* **Operational Velocity:** Accelerate response workflows from minutes to seconds through single-click AI generation and zero-friction copying.

* **Cost Control & Efficiency:** Execute LLM calls strictly on-demand (per review) to prevent runaway token costs and API rate-limiting issues.

* **Scalability Foundation:** Design the OpenAPI contract and SQLite database schema to be platform-agnostic, enabling seamless transition to real geoservice APIs (such as Google Business Profile) and robust production databases (PostgreSQL) in subsequent modules.



---



## 3. MVP Scope Boundaries & Non-Goals



### In Scope (MVP)

1. **Single-User / Single-Location (Owner-First):** Flat database structure optimized for one business owner without multi-tenancy, user roles, or organizational division management.

2. **Dual Input Channels:** Single review creation via an interactive manual form (ideal for development, testing, and live demos) and batch import via CSV files.

3. **Dynamic Context Engineering:** Reusable business profile settings (business name, business type, description, and brand voice) stored in the database and dynamically injected into the LLM system prompt.

4. **On-Demand Generation:** Replies are generated strictly on-demand when the user clicks "Generate Reply" for a specific review, rather than automatically processing the entire batch on import.

5. **In-Place Response Mutation:** Clicking "Regenerate" with updated instructions overwrites the existing draft in the database. No version history of intermediate failed drafts is retained in SQLite, preventing database bloat.

6. **Interactive AI Steering:** Owners can manually edit the generated draft or provide plain-text steering instructions (e.g., *"Make it more empathetic and apologize for the long wait"*) to regenerate a modified draft.

7. **Two-State Review Lifecycle:** Explicitly bounded state machine: `draft` (unprocessed or unapproved) -> `approved` (finalized by the owner).

8. **Single-Call Structured Outputs:** The FastAPI backend utilizes LLM structured JSON output to generate the reply text, detect sentiment, and extract keywords in a single atomic API transaction.

9. **Graceful Degradation:** Partial failure of AI metadata extraction (sentiment, tags) does not block the delivery of the response text; missing fields safely degrade to `NULL` / `[]` in the database.

10. **Modern Tech Stack:** FastAPI (backend), SQLite (database), Pydantic (data validation), OpenAPI 3.0 (contract), and React (Vite-based frontend).



### Out of Scope (Non-Goals)

* Multi-location, multi-branch, or agency-level portal management.

* Auto-generating replies for the entire batch of reviews immediately upon CSV import.

* Direct API publishing or automated background posting to Google Maps, Yelp, or TripAdvisor (state transition `posted` is deferred to future integrations).

* Asynchronous task queues (Celery/Redis) — all generation requests are synchronous HTTP calls to FastAPI.

* Custom fine-tuning of models on historical reviews.



---



## 4. User Journeys & Executable Acceptance Criteria (AC)



### Journey 1: Company Profile Configuration

* **User Story:** As a business owner, I want to configure my business name, type, description, and brand voice so that the AI-generated replies align with my brand identity and sound natural.

* **AC-01 (Persistence):** Given a business owner saving settings through the frontend form, when the payload is submitted, the backend must save or update exactly one row (where `id = 1`) in the `business_settings` table.

* **AC-02 (Settings Fetching):** Given the application reloading or settings page being visited, the system must fetch the existing row from `business_settings` and pre-populate the form.



### Journey 2: Adding Reviews (Form and CSV Import)

* **User Story:** As a business owner, I want to add reviews individually via a manual form or upload them in bulk via a CSV file to build my active queue of reviews requiring replies.

* **AC-03 (Manual Form Validation):** Given the manual creation form, the frontend and backend must strictly enforce validation:

* `author_name`: required, 1–100 characters.

* `review_text`: required, 3–5000 characters.

* `rating`: required, integer between 1 and 5 (inclusive).

* **AC-04 (CSV File Constraints):** Given a CSV upload request:

* The file size must be strictly checked on the backend and capped at **1 MB max**.

* The backend must enforce a processing limit of **max 100 reviews** per file.

* If the file size exceeds 1 MB or contains > 100 entries, the server must reject the upload with `400 Bad Request`.

* **AC-05 (CSV Schema Validation):** The CSV file must contain column headers for `author_name`, `review_text`, and `rating`.

* **AC-06 (Graceful Partial Import):** Given a CSV upload containing both valid and invalid rows (e.g., rating > 5 or empty text):

* All valid rows must be inserted into SQLite under a single transaction.

* All invalid rows must be skipped.

* The server must respond with `201 Created` and a JSON summary detailing import statistics:

```json

{\n \"status\": \"success\",\n \"imported\": 95,\n \"skipped\": 5,\n \"errors\": [\n {\"row\": 12, \"error\": \"Rating must be between 1 and 5\"},\n {\"row\": 43, \"error\": \"Author name cannot be empty\"}\n ]\n }

```

* **AC-07 (Import Default State):** Imported reviews must default to status `draft`, with `reply_text = NULL`, `detected_sentiment = NULL`, and `detected_tags = []`. No AI responses are generated automatically.

* **AC-08 (Duplicate Prevention):** The backend must prevent duplicate reviews. If the combination of `author_name` and `review_text` already exists, the record is skipped during CSV import or rejected with `409 Conflict` on manual entry.



### Journey 3: On-Demand Generation & Structured Output

* **User Story:** As a business owner, I want to click "Generate Reply" on a review to get a context-aware, structured response accompanied by automated sentiment and topic categorization.

* **AC-09 (Single-Call Structured JSON):** Given a generation trigger, the backend must make a single API request to the LLM (using JSON Schema or Structured Outputs) to generate the response text, classify sentiment, and extract tags simultaneously.

* **AC-10 (Output Constraints):** The generated reply text must be **between 1 and 3 sentences** and strictly **under 500 characters** (including punctuation and spaces).

* **AC-11 (Sentiment Enum):** The classified sentiment must fall strictly within the enum values: `positive`, `neutral`, `negative`.

* **AC-12 (Tag Extraction):** The tags must return as a list of 1 to 3 short lowercase keywords (e.g., `["service", "pricing"]`) representing the core review topics.

* **AC-13 (Graceful Degradation):** Given a partial model failure (e.g., reply text generated successfully, but sentiment is invalid or tags fail to parse):

* The backend must capture the text response and save it.

* The metadata fields in the database must fall back to `NULL` (sentiment) and `[]` (tags).

* The frontend must display the text reply for manual editing and hide or show a neutral/unknown status for metadata badges.

* **AC-14 (Complete LLM Failure):** If the LLM API is completely unreachable or timed out, the backend must return `500 Internal Server Error`, and the frontend must display an alert with a \"Retry\" button.



### Journey 4: Interactive Editing, Steering, and Approval

* **User Story:** As a business owner, I want to refine the response draft manually or by giving plain-text instructions to the AI, and then finalize it to complete the review cycle.

* **AC-15 (Interactive Regeneration):** Given custom steering instructions, when "Regenerate" is clicked, the backend must send the review, business profile, existing draft, and instructions to the LLM. The newly returned reply text and metadata must overwrite the previous values in SQLite.

* **AC-16 (Frontend State Isolation):** When the owner manually edits the response text in the frontend textarea, these edits must remain strictly in local frontend state. No database writes or auto-saves are triggered during typing.

* **AC-17 (One-Step Approval):** Given edited or finalized response text:

* When the user clicks "Approve", the frontend sends a single `PATCH` request to `/api/reviews/{id}` with the text and status set to `approved`.

* The backend updates the SQLite row in one transaction and sets the status to `approved`.

* The UI moves the review from the pending queue to the "Completed" tab.



---



## 5. Data Architecture (SQLite Schema)



```sql

-- Reusable Business Settings (Always exactly one row where id = 1)

CREATE TABLE business_settings (

id INTEGER PRIMARY KEY CHECK (id = 1),

business_name TEXT NOT NULL,

business_type TEXT NOT NULL, -- e.g., "Coffee Shop", "Auto Repair"

description TEXT NOT NULL, -- Detailed context for the LLM

brand_voice TEXT NOT NULL -- e.g., "friendly and warm", "formal", "humorous"

);



-- Flat Review Queue Table

CREATE TABLE reviews (

id TEXT PRIMARY KEY, -- UUID string

author_name TEXT NOT NULL, -- Max 100 characters enforced at API layer

rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),

review_text TEXT NOT NULL, -- Max 5000 characters enforced at API layer

source TEXT NOT NULL, -- e.g., "manual", "google", "yelp"

reply_text TEXT NULL, -- Overwritten on regenerate, finalized on approve

detected_sentiment TEXT NULL CHECK (detected_sentiment IN ('positive', 'neutral', 'negative')),

detected_tags TEXT NOT NULL DEFAULT '[]', -- JSON-serialized list of strings (e.g., '["service", "coffee"]')

status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved')),

created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);

```



---



## 6. Executable Data Contracts (Pydantic Schemas)



These schemas must be used directly by the FastAPI backend to validate payloads and enforce API borders.



### Business Settings Schemas

```python

from pydantic import BaseModel, Field



class BusinessSettingsSchema(BaseModel):

business_name: str = Field(..., min_length=1, max_length=100, example="Daily Grind Cafe")

business_type: str = Field(..., min_length=1, max_length=50, example="Coffee Shop")

description: str = Field(..., min_length=3, max_length=1000, example="Cozy local cafe serving organic brews and homemade pastries.")

brand_voice: str = Field(..., min_length=1, max_length=100, example="warm, welcoming, and slightly playful")

```



### Structured Output Schemas (LLM Contract)

```python

from enum import Enum

from pydantic import BaseModel, Field

from typing import List, Optional



class SentimentEnum(str, Enum):

POSITIVE = "positive"

NEUTRAL = "neutral"

NEGATIVE = "negative"



class LLMStructuredOutput(BaseModel):

reply_text: str = Field(

...,

min_length=10,

max_length=500,

description="AI-generated reply strictly bounded to 1-3 sentences and under 500 characters."

)

detected_sentiment: Optional[SentimentEnum] = Field(

default=None,

description="Overall review sentiment. Must be positive, neutral, or negative. Degrades to null on model error."

)

detected_tags: List[str] = Field(

default_factory=list,

description="1-3 short lowercase keywords representing review topics. Degrades to empty list on model error."

)

```



### Review Schemas

```python

from datetime import datetime

from pydantic import BaseModel, Field, conint

from typing import List, Optional



class ReviewCreateSchema(BaseModel):

author_name: str = Field(..., min_length=1, max_length=100, example="John Doe")

review_text: str = Field(..., min_length=3, max_length=5000, example="Great espresso but service was a bit slow today.")

rating: conint(ge=1, le=5) = Field(..., example=4)

created_at: Optional[datetime] = Field(default=None, description="Defaults to server timestamp if omitted.")



class GenerateReplyRequest(BaseModel):

instructions: Optional[str] = Field(

default=None,

max_length=500,

example="Apologize for the slow service and offer a free cookie next time."

)



class UpdateReviewRequest(BaseModel):

reply_text: Optional[str] = Field(None, max_length=500, description="Owner-edited response text.")

status: Optional[str] = Field(None, pattern="^(draft|approved)$", description="Updates status to approved.")

```



---



## 7. Testing Strategy & Verification Protocols



To maintain high engineering discipline, the MVP must achieve high code coverage across both happy paths and error cases.



### Unit Testing (Pytest)

1. **Input Schema Validation:** Ensure Pydantic rejects review inputs with rating < 1 or > 5, or review text under 3 characters.

2. **CSV Parser Edge Cases:** Test parser with an empty CSV, a CSV exceeding 100 rows, a CSV exceeding 1 MB, and files containing malformed headers.

3. **Pydantic Fallback (Graceful Degradation):** Verify that the `LLMStructuredOutput` schema parses successfully when sentiment is null or tags contain invalid types.

4. **System Prompt Composition:** Write unit tests to assert that business profile fields are formatted correctly into the prompt string.



### Integration Testing (Database & Endpoint Verification)

1. **Settings Persistence:** Verify `PUT /api/settings` writes to SQLite row `id = 1` and subsequent `GET /api/settings` returns the exact payload.

2. **CSV Partial Import Loop:** Upload a test CSV containing 3 valid rows and 1 invalid row. Assert that the response is `201 Created`, exactly 3 rows exist in the database, and the error report contains details for the failed row.

3. **Life-cycle State Transition:** Perform a mock `PATCH` request to `/api/reviews/{id}` to update `reply_text` and change status to `approved`. Verify state change in SQLite.

4. **Idempotency & Mutability:** Verify that repeated `POST /api/reviews/{id}/generate` requests successfully update the existing SQLite row and replace the response text without appending duplicate review records.



### External API Mocking

* **LLM Isolation:** All outbound LLM calls must be intercepted and mocked using `unittest.mock` or pytest fixtures. No actual tokens should be spent and no network calls should be made during automated unit/integration test runs.



---



## 8. Phased Implementation Roadmap & Verifiable Milestones



To prevent technical drift and guarantee a robust full-stack integration loop (avoiding unchecked "vibe-coding" pitfalls), development must progress through four sequential, test-gated milestones. Each milestone represents a complete, verifiable state.



```

[ Milestone 1: Spec & API Contract ]

│

▼

[ Milestone 2: Frontend Prototype ]

(Uses Mocked Backend Calls)

│

▼

[ Milestone 3: Connected Full-Stack ]

(Uses In-Memory Backend Store)

│

▼

[ Milestone 4: SQLite Persistence ]

(SQLAlchemy ORM + SQLite DB)

```



### Milestone 1: Executable Specification & API Contract

* **Goal:** Establish the strict schema and behavioral agreement between client and server before writing execution logic.

* **Verifiable Deliverable:**

* Finalized `product-spec.md` and complete OpenAPI-compliant `openapi.yaml` contract.

* **Verification Gate:** Contract must parse correctly under standard Swagger/OpenAPI linters.



### Milestone 2: Frontend Prototype with Mocked API Layer

* **Goal:** Build and test the user experience in complete isolation.

* **Verifiable Deliverable:**

* Interactive React/Vite client running locally on a Vite development server.

* The frontend service layer acts as a complete stub, mirroring contract schemas locally with deterministic fake data.

* **Verification Gate:** UI is fully interactive (settings forms, lists, review queues can be navigated, "generate" button returns instant fake response and switches states locally). All React/frontend tests pass.



### Milestone 3: Connected Full-Stack App (In-Memory Backend)

* **Goal:** Prove the physical network and data serialization loop between client and server.

* **Verifiable Deliverable:**

* A running FastAPI server that exposes endpoints matching `openapi.yaml`.

* Backend logic reads/writes to a temporary **in-memory Python dictionary store** (no database files created).

* Frontend API calls are redirected to the FastAPI server using Vite’s development proxy or CORS configurations.

* **Verification Gate:** Client and server communicate over HTTP. Setting fields in UI actually reflects in other panels. Back-end unit/mock integration tests pass.



### Milestone 4: Database-Agnostic SQLite Persistence

* **Goal:** Introduce permanent data storage with a layer of abstraction that allows future postgres substitution.

* **Verifiable Deliverable:**

* SQLAlchemy ORM model mappings mapping to the schema in Section 5.

* FastAPI backend configured to manage SQLite database sessions.

* Local `.db` SQLite file initialized on server startup.

* **Verification Gate:** Full integration test suite execution (`pytest backend/tests`). State is preserved—creating or approving reviews must survive server restarts. System is officially ready for multi-process containerization (Docker Compose) in subsequent modules.


---

Centralize every backend call in one services layer, and create a mock

implementation of it so the whole app runs without a real backend.

Add tests.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/bb127d18-7905-41b6-92ac-04ba8f1b2e91).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
