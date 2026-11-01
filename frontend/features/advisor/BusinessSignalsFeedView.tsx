"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  CheckCircle2,
  RefreshCw,
  Bell,
  Clock,
  ShieldAlert,
  ArrowRight,
  Filter,
  Check,
} from "lucide-react";
import { smartRecommendationsService } from "@/services/smart-recommendations-service";
import type {
  BusinessSignalItem,
  BusinessSignalsFeedResponse,
} from "@/types/smart-recommendations";

export function BusinessSignalsFeedView() {
  const [feed, setFeed] = useState<BusinessSignalsFeedResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [selectedSeverity, setSelectedSeverity] = useState<string>("ALL");
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  const loadFeed = useCallback(async (severityFilter?: string) => {
    try {
      setLoading(true);
      const sev = severityFilter && severityFilter !== "ALL" ? severityFilter : undefined;
      const res = await smartRecommendationsService.getSignalsFeed(sev);
      setFeed(res);
    } catch (err) {
      console.error("Failed to load business signals feed:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFeed(selectedSeverity);
  }, [loadFeed, selectedSeverity]);

  const handleScanNow = async () => {
    try {
      setIsScanning(true);
      setFeedbackMsg(null);
      const res = await smartRecommendationsService.evaluateMonitoring();
      setFeedbackMsg(`Scan complete: ${res.new_events_detected} new signal(s) evaluated.`);
      await loadFeed(selectedSeverity);
    } catch (err) {
      console.error("Failed to evaluate monitoring:", err);
      setFeedbackMsg("Scan failed. Please try again.");
    } finally {
      setIsScanning(false);
    }
  };

  const handleDismiss = async (eventId: string) => {
    try {
      await smartRecommendationsService.dismissSignal(eventId);
      if (feed) {
        setFeed({
          ...feed,
          signals: feed.signals.map((s) =>
            s.event_id === eventId ? { ...s, status: "ACKNOWLEDGED" } : s
          ),
        });
      }
    } catch (err) {
      console.error("Failed to dismiss signal:", err);
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case "CRITICAL":
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200">CRITICAL RISK</span>;
      case "HIGH":
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">HIGH PRIORITY</span>;
      case "MEDIUM":
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-800 border border-yellow-200">MEDIUM WATCH</span>;
      case "LOW":
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">LOW</span>;
      default:
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">OPPORTUNITY / INFO</span>;
    }
  };

  const getSignalIcon = (eventType: string, severity: string) => {
    if (severity === "CRITICAL" || severity === "HIGH") {
      return <ShieldAlert className="w-5 h-5 text-red-600" />;
    }
    if (eventType.includes("GROWTH") || eventType.includes("SURGE") || eventType.includes("IMPROVED")) {
      return <TrendingUp className="w-5 h-5 text-emerald-600" />;
    }
    if (eventType.includes("DECLINE") || eventType.includes("DETERIORATED")) {
      return <TrendingDown className="w-5 h-5 text-amber-600" />;
    }
    return <AlertTriangle className="w-5 h-5 text-indigo-600" />;
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-gray-100 pb-4">
        <div>
          <div className="flex items-center space-x-2">
            <Bell className="w-6 h-6 text-indigo-600" />
            <h2 className="text-xl font-bold text-gray-900">
              Business Signals & Opportunities
            </h2>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Proactive event detection across revenue shifts, client concentration, demand trends, and operational health.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleScanNow}
            disabled={isScanning}
            className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-colors shadow-sm"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isScanning ? "animate-spin" : ""}`} />
            {isScanning ? "Scanning Changes..." : "Scan Changes Now"}
          </button>
        </div>
      </div>

      {feedbackMsg && (
        <div className="bg-indigo-50 border border-indigo-200 text-indigo-800 px-4 py-2.5 rounded-lg text-sm flex items-center justify-between">
          <span>{feedbackMsg}</span>
          <button onClick={() => setFeedbackMsg(null)} className="text-indigo-600 font-semibold hover:text-indigo-800 text-xs">Dismiss</button>
        </div>
      )}

      {/* Metric Breakdown Cards */}
      {feed && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-red-50 border border-red-100 rounded-lg p-3">
            <span className="text-xs font-medium text-red-700">Critical Risks</span>
            <div className="text-2xl font-bold text-red-900 mt-0.5">{feed.critical_count}</div>
          </div>
          <div className="bg-amber-50 border border-amber-100 rounded-lg p-3">
            <span className="text-xs font-medium text-amber-700">High Priority</span>
            <div className="text-2xl font-bold text-amber-900 mt-0.5">{feed.high_count}</div>
          </div>
          <div className="bg-yellow-50 border border-yellow-100 rounded-lg p-3">
            <span className="text-xs font-medium text-yellow-700">Medium Watch</span>
            <div className="text-2xl font-bold text-yellow-900 mt-0.5">{feed.medium_count}</div>
          </div>
          <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-3">
            <span className="text-xs font-medium text-emerald-700">Opportunities / Info</span>
            <div className="text-2xl font-bold text-emerald-900 mt-0.5">{feed.low_and_info_count}</div>
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-1 text-sm border-b border-gray-100">
        <Filter className="w-4 h-4 text-gray-400 mr-1" />
        {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((sev) => (
          <button
            key={sev}
            onClick={() => setSelectedSeverity(sev)}
            className={`px-3 py-1.5 rounded-md font-medium text-xs transition-colors ${
              selectedSeverity === sev
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {sev === "ALL" ? "All Signals" : sev}
          </button>
        ))}
      </div>

      {/* Signals List */}
      {loading ? (
        <div className="py-12 flex flex-col items-center justify-center text-gray-500 space-y-2">
          <RefreshCw className="w-6 h-6 animate-spin text-indigo-600" />
          <p className="text-sm">Evaluating proactive business signals...</p>
        </div>
      ) : feed && feed.signals.length > 0 ? (
        <div className="space-y-4">
          {feed.signals.map((sig: BusinessSignalItem) => (
            <div
              key={sig.event_id}
              className={`p-5 rounded-xl border transition-all ${
                sig.status === "ACKNOWLEDGED"
                  ? "bg-gray-50 border-gray-200 opacity-60"
                  : sig.severity === "CRITICAL"
                  ? "bg-red-50/40 border-red-200"
                  : sig.severity === "HIGH"
                  ? "bg-amber-50/40 border-amber-200"
                  : "bg-white border-gray-200 hover:shadow-sm"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start space-x-3">
                  <div className="p-2 rounded-lg bg-white border border-gray-100 shadow-2xs mt-0.5">
                    {getSignalIcon(sig.event_type, sig.severity)}
                  </div>
                  <div>
                    <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                      <h3 className="font-semibold text-gray-900 text-base">{sig.title}</h3>
                      {getSeverityBadge(sig.severity)}
                      {sig.escalation_level > 0 && (
                        <span className="text-[10px] font-bold uppercase bg-red-600 text-white px-2 py-0.5 rounded">
                          Escalated (L{sig.escalation_level})
                        </span>
                      )}
                    </div>
                    <div className="flex items-center space-x-3 text-xs text-gray-400 mt-1">
                      <span className="flex items-center">
                        <Clock className="w-3.5 h-3.5 mr-1" />
                        {new Date(sig.detected_at).toLocaleDateString()}
                      </span>
                      <span>Source: {sig.source.replace("_", " ")}</span>
                      <span>Confidence: {Math.round(sig.confidence * 100)}%</span>
                    </div>
                  </div>
                </div>

                {sig.status === "NEW" ? (
                  <button
                    onClick={() => handleDismiss(sig.event_id)}
                    className="text-xs text-gray-400 hover:text-gray-700 border border-gray-200 hover:border-gray-400 px-2.5 py-1 rounded transition-colors"
                  >
                    Acknowledge
                  </button>
                ) : (
                  <span className="inline-flex items-center text-xs text-emerald-600 font-medium">
                    <Check className="w-3.5 h-3.5 mr-1" /> Acknowledged
                  </span>
                )}
              </div>

              {/* What Changed & Why It Matters */}
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <div className="bg-white/80 p-3 rounded-lg border border-gray-100">
                  <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block mb-1">
                    What Changed
                  </span>
                  <p className="text-gray-800">{sig.what_changed}</p>
                </div>

                <div className="bg-white/80 p-3 rounded-lg border border-gray-100">
                  <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block mb-1">
                    Why It Matters
                  </span>
                  <p className="text-gray-800">{sig.why_it_matters}</p>
                </div>
              </div>

              {/* Suggested Action Bar */}
              <div className="mt-3 pt-3 border-t border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div className="text-xs text-gray-700 flex items-start sm:items-center space-x-1.5">
                  <span className="font-semibold text-indigo-700 whitespace-nowrap">Suggested Action:</span>
                  <span>{sig.suggested_action}</span>
                </div>
                {sig.linked_recommendation_id && (
                  <span className="text-xs text-indigo-600 font-medium whitespace-nowrap flex items-center">
                    Linked to {sig.linked_recommendation_id} <ArrowRight className="w-3 h-3 ml-1" />
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="py-12 text-center text-gray-500 border border-dashed border-gray-200 rounded-xl">
          <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
          <h4 className="font-medium text-gray-900">No Active Warning Signals</h4>
          <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
            Your revenue trends, customer concentration, and health scores are within safe operating parameters.
          </p>
        </div>
      )}
    </div>
  );
}
