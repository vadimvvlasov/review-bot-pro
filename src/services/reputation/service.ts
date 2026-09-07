import type {
  BusinessSettings,
  GenerateReplyRequest,
  ImportSummary,
  Review,
  ReviewCreate,
  UpdateReviewRequest,
} from "./types";
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
  generateReply(id: string, payload?: GenerateReplyRequest): Promise<Review>;
  /** PATCH /api/reviews/{id} */
  updateReview(id: string, payload: UpdateReviewRequest): Promise<Review>;
  /** DELETE /api/reviews/{id} */
  deleteReview(id: string): Promise<void>;
}

/**
 * Active implementation. The mock keeps the whole product runnable with no
 * backend; point this at an HTTP client once the FastAPI server exists.
 */
export const reputationService: ReputationService = createMockReputationService();
