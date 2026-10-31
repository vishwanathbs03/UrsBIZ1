"use client";

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  smartRecommendationsService,
  type GetRecommendationsParams,
} from "@/services/smart-recommendations-service";
import type {
  RecommendationStatus,
  SmartRecommendationsResponse,
} from "@/types/smart-recommendations";

export function useSmartRecommendations(initialParams?: GetRecommendationsParams) {
  const queryClient = useQueryClient();
  const [params, setParams] = useState<GetRecommendationsParams>(
    initialParams || { category: "all", priority: "all", status: "all" }
  );

  const queryKey = ["smart-recommendations", params];

  const query = useQuery<SmartRecommendationsResponse>({
    queryKey,
    queryFn: () => smartRecommendationsService.getRecommendations(params),
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({
      recommendationId,
      status,
      notes,
    }: {
      recommendationId: string;
      status: RecommendationStatus;
      notes?: string;
    }) => smartRecommendationsService.updateStatus(recommendationId, status, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["smart-recommendations"] });
    },
  });

  const explainMutation = useMutation({
    mutationFn: (recommendationId: string) =>
      smartRecommendationsService.explainRecommendation(recommendationId),
  });

  const updateStatus = useCallback(
    (recommendationId: string, status: RecommendationStatus, notes?: string) => {
      return updateStatusMutation.mutateAsync({ recommendationId, status, notes });
    },
    [updateStatusMutation]
  );

  const explain = useCallback(
    (recommendationId: string) => {
      return explainMutation.mutateAsync(recommendationId);
    },
    [explainMutation]
  );

  return {
    data: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    params,
    setParams,
    refetch: query.refetch,
    updateStatus,
    isUpdatingStatus: updateStatusMutation.isPending,
    explain,
    isExplaining: explainMutation.isPending,
  };
}
