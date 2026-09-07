import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { reputationService } from "./service";
import type {
  BusinessSettings,
  GenerateReplyRequest,
  ReviewCreate,
  UpdateReviewRequest,
} from "./types";

export const settingsQueryOptions = queryOptions({
  queryKey: ["settings"],
  queryFn: () => reputationService.getSettings(),
});

export const reviewsQueryOptions = queryOptions({
  queryKey: ["reviews"],
  queryFn: () => reputationService.listReviews(),
});

export function useSaveSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: BusinessSettings) => reputationService.saveSettings(payload),
    onSuccess: (data) => qc.setQueryData(settingsQueryOptions.queryKey, data),
  });
}

export function useCreateReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReviewCreate) => reputationService.createReview(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: reviewsQueryOptions.queryKey }),
  });
}

export function useImportCsv() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const text = await file.text();
      return reputationService.importReviewsCsv({ name: file.name, size: file.size, text });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: reviewsQueryOptions.queryKey }),
  });
}

export function useGenerateReply() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; payload?: GenerateReplyRequest | undefined }) =>
      reputationService.generateReply(vars.id, vars.payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: reviewsQueryOptions.queryKey }),
  });
}

export function useUpdateReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; payload: UpdateReviewRequest }) =>
      reputationService.updateReview(vars.id, vars.payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: reviewsQueryOptions.queryKey }),
  });
}

export function useDeleteReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => reputationService.deleteReview(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: reviewsQueryOptions.queryKey }),
  });
}
