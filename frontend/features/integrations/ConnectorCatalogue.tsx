"use client";

import React, { useState } from "react";
import { ConnectorCatalogueItem } from "@/services/integration-service";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConnectionModal } from "./ConnectionModal";
import {
  Cable,
  CheckCircle,
  Clock,
  ExternalLink,
  Info,
  Plug,
  ShieldCheck,
  AlertTriangle,
} from "lucide-react";

interface ConnectorCatalogueProps {
  connectors: ConnectorCatalogueItem[];
  onConnectionCreated: () => void;
}

export const ConnectorCatalogue: React.FC<ConnectorCatalogueProps> = ({
  connectors,
  onConnectionCreated,
}) => {
  const [selectedConnector, setSelectedConnector] = useState<ConnectorCatalogueItem | null>(null);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "OPERATIONAL":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle className="h-3.5 w-3.5" /> Operational
          </span>
        );
      case "READY_FOR_CREDENTIALS":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <ShieldCheck className="h-3.5 w-3.5" /> Ready for Credentials
          </span>
        );
      case "BETA":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <Clock className="h-3.5 w-3.5" /> Beta
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-muted text-muted-foreground border border-border">
            Coming Soon
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold tracking-tight text-foreground">
            Available Data Connectors
          </h2>
          <p className="text-sm text-muted-foreground">
            Connect accounting software, ERPs, and POS feeds to automatically synchronize business transactions.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {connectors.map((c) => (
          <div
            key={c.connector_id}
            className="flex flex-col justify-between rounded-xl border border-border bg-card p-6 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden"
          >
            <div>
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-primary/10 text-primary">
                    <Plug className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-foreground flex items-center gap-2">
                      {c.name}
                      <span className="text-xs font-normal text-muted-foreground">v{c.version}</span>
                    </h3>
                    <p className="text-xs text-muted-foreground font-medium">{c.provider}</p>
                  </div>
                </div>
                {getStatusBadge(c.operational_status)}
              </div>

              <p className="text-sm text-muted-foreground mb-4 leading-relaxed">
                {c.description}
              </p>

              <div className="space-y-2 mb-4">
                <div className="text-xs font-semibold text-foreground/80 uppercase tracking-wider">
                  Capabilities
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {c.capabilities.map((cap) => (
                    <span
                      key={cap}
                      className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-muted text-foreground/90 border border-border/60"
                    >
                      {cap.replace(/_/g, " ")}
                    </span>
                  ))}
                  <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-muted text-foreground/70 border border-border/60">
                    Auth: {c.auth_method}
                  </span>
                </div>
              </div>

              {c.known_limitations && c.known_limitations.length > 0 && (
                <div className="rounded-lg bg-muted/40 border border-border/40 p-3 mb-4">
                  <div className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5 mb-1.5">
                    <Info className="h-3.5 w-3.5" /> Technical Boundaries
                  </div>
                  <ul className="text-xs text-muted-foreground/90 space-y-1 list-disc list-inside">
                    {c.known_limitations.map((lim, idx) => (
                      <li key={idx}>{lim}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="pt-4 border-t border-border flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                {c.config_fields.length} setup parameters required
              </span>
              <Button
                size="sm"
                onClick={() => setSelectedConnector(c)}
                disabled={c.operational_status === "COMING_SOON"}
              >
                Configure Connection
              </Button>
            </div>
          </div>
        ))}
      </div>

      {selectedConnector && (
        <ConnectionModal
          connector={selectedConnector}
          isOpen={!!selectedConnector}
          onClose={() => setSelectedConnector(null)}
          onSuccess={() => {
            setSelectedConnector(null);
            onConnectionCreated();
          }}
        />
      )}
    </div>
  );
};
