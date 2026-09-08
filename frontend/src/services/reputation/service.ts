import type {
  BusinessSettings,
  GenerateReplyRequest,
  ImportSummary,
  Review,
  ReviewCreate,
  UpdateReviewRequest,
} from "./types";
import { createHttpReputationService } from "./http-service";
import { createMockReputationService } from "./mock-service";

/**
 * The single boundary between the UI and the backend. Every network call in the
 * app goes through this interface, so swapping the mock for the FastAPI client
 * is a one-line change in `reputationService`.
 */
export interface ReputationService {
  /** GET /api/settings */
  getSettings(): Promise<BusinessSettings | null>;
  /** PUT /api/settings */
  saveSettings(payload: BusinessSettings): Promise<BusinessSettings>;
  /** GET /api/reviews */
  listReviews(): Promise<Review[]>;
  /** POST /api/reviews */
  createReview(payload: ReviewCreate): Promise<Review>;
  /** POST /api/reviews/import (CSV) */
  importReviewsCsv(file: { name: string; size: number; text: string }): Promise<ImportSummary>;
  /** POST /api/reviews/{id}/generate */
  generateReply(id: string, payload?: GenerateReplyRequest | undefined): Promise<Review>;
  /** PATCH /api/reviews/{id} */
  updateReview(id: string, payload: UpdateReviewRequest): Promise<Review>;
  /** DELETE /api/reviews/{id} */
  deleteReview(id: string): Promise<void>;
}

/**
 * Active implementation. Set VITE_USE_API=true to talk to the FastAPI
 * backend (VITE_API_BASE_URL, e.g. http://localhost:8000); otherwise the
 * mock keeps the whole product runnable with no backend.
 */
export const reputationService: ReputationService =
  import.meta.env.VITE_USE_API === "true"
    ? createHttpReputationService()
    : createMockReputationService();
