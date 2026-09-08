import {
  ApiError,
  type BusinessSettings,
  type GenerateReplyRequest,
  type ImportSummary,
  type Review,
  type UpdateReviewRequest,
} from "./types";
import type { ReputationService } from "./service";

/**
 * HTTP implementation of ReputationService against the FastAPI backend
 * (Milestone 3: Connected Full-Stack). The mock stays the default for
 * offline work and unit tests; this client activates via VITE_USE_API.
 *
 * Base URL resolution: VITE_API_BASE_URL (e.g. http://localhost:8000 in
 * dev, backend has CORS open) or "" for same-origin / Vite proxy setups.
 */

function baseUrl(): string {
  const raw = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
  return raw.replace(/\/$/, "");
}

function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    if ("message" in body && typeof body.message === "string") return body.message;
    if ("detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        const first = detail[0] as { msg?: unknown } | undefined;
        if (first && typeof first.msg === "string") return first.msg;
      }
    }
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${baseUrl()}/api${path}`, init);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const body: unknown = text ? (JSON.parse(text) as unknown) : null;
  if (!res.ok) {
    throw new ApiError(res.status, errorMessage(body, `Request failed (${res.status})`));
  }
  return body as T;
}

function jsonInit(method: string, payload: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
}

export function createHttpReputationService(): ReputationService {
  return {
    async getSettings() {
      try {
        return await request<BusinessSettings | null>("/settings");
      } catch (error) {
        // Spec allows 404 as "no profile yet" alongside 200+null.
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },

    saveSettings(payload) {
      return request<BusinessSettings>("/settings", jsonInit("PUT", payload));
    },

    listReviews() {
      return request<Review[]>("/reviews");
    },

    createReview(payload) {
      return request<Review>("/reviews", jsonInit("POST", payload));
    },

    async importReviewsCsv(file) {
      const form = new FormData();
      form.append("file", new File([file.text], file.name, { type: "text/csv" }));
      return request<ImportSummary>("/reviews/import", { method: "POST", body: form });
    },

    generateReply(id, payload?: GenerateReplyRequest | undefined) {
      const body = payload?.instructions?.trim()
        ? { instructions: payload.instructions }
        : undefined;
      return request<Review>(
        `/reviews/${encodeURIComponent(id)}/generate`,
        body ? jsonInit("POST", body) : { method: "POST" },
      );
    },

    updateReview(id, payload: UpdateReviewRequest) {
      return request<Review>(`/reviews/${encodeURIComponent(id)}`, jsonInit("PATCH", payload));
    },

    async deleteReview(id) {
      await request<void>(`/reviews/${encodeURIComponent(id)}`, { method: "DELETE" });
    },
  };
}
