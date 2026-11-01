"use client";

import { useQuery } from "@tanstack/react-query";
import { smartRecommendationsService } from "@/services/smart-recommendations-service";
import type {
  AdvancedRecommendationsOverviewResponse,
  PersonalizedGrowthStrategy,
  RecommendationPortfolioResponse,
} from "@/types/smart-recommendations";

export function useAdvancedRecommendations() {
  const overviewQuery = useQuery<AdvancedRecommendationsOverviewResponse>({
    queryKey: ["advanced-recommendations-overview"],
    queryFn: () => smartRecommendationsService.getAdvancedOverview(),
    staleTime: 60000,
  });

  const strategyQuery = useQuery<PersonalizedGrowthStrategy>({
    queryKey: ["advanced-growth-strategy"],
    queryFn: () => smartRecommendationsService.getGrowthStrategy(),
    staleTime: 60000,
  });

  const portfolioQuery = useQuery<RecommendationPortfolioResponse>({
    queryKey: ["recommendations-portfolio"],
    queryFn: () => smartRecommendationsService.getPortfolio(),
    staleTime: 60000,
  });

  return {
    overview: overviewQuery.data,
    isLoadingOverview: overviewQuery.isLoading,
    isErrorOverview: overviewQuery.isError,
    strategy: strategyQuery.data,
    isLoadingStrategy: strategyQuery.isLoading,
    isErrorStrategy: strategyQuery.isError,
    portfolio: portfolioQuery.data,
    isLoadingPortfolio: portfolioQuery.isLoading,
    isErrorPortfolio: portfolioQuery.isError,
    refetchAll: () => {
      overviewQuery.refetch();
      strategyQuery.refetch();
      portfolioQuery.refetch();
    },
  };
}
