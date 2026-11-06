"use client";

import React, { useEffect, useState } from "react";
import {
  ConnectionOut,
  ConnectorCatalogueItem,
  IntegrationAuditOut,
  SyncExecutionOut,
  integrationService,
} from "@/services/integration-service";
import { ActiveConnectionsList } from "./ActiveConnectionsList";
import { ConnectorCatalogue } from "./ConnectorCatalogue";
import { SyncHistoryTable } from "./SyncHistoryTable";
import { Button } from "@/components/ui/button";
import {
  Activity,
  CheckCircle2,
  Database,
  History,
  Layers,
  Plug,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

export const IntegrationsView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>("connections");
  const [catalogue, setCatalogue] = useState<ConnectorCatalogueItem[]>([]);
  const [connections, setConnections] = useState<ConnectionOut[]>([]);
  const [syncHistory, setSyncHistory] = useState<SyncExecutionOut[]>([]);
  const [audits, setAudits] = useState<IntegrationAuditOut[]>([]);
  const [syncTotal, setSyncTotal] = useState<number>(0);
  const [syncPage, setSyncPage] = useState<number>(1);
  const [auditTotal, setAuditTotal] = useState<number>(0);
  const [auditPage, setAuditPage] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadData = async () => {
    setErrorMsg(null);
    try {
      const [catRes, connRes, syncRes, auditRes] = await Promise.all([
        integrationService.getCatalogue(),
        integrationService.getConnections(),
        integrationService.getAllSyncs(syncPage, 10),
        integrationService.getAudits(auditPage, 10),
      ]);
      setCatalogue(catRes);
      setConnections(connRes);
      setSyncHistory(syncRes.items);
      setSyncTotal(syncRes.total);
      setAudits(auditRes.items);
      setAuditTotal(auditRes.total);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load integration data.";
      setErrorMsg(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [syncPage, auditPage]);

  // Derived KPI metrics
  const totalConnections = connections.length;
  const connectedCount = connections.filter((c) => c.status === "CONNECTED").length;
  const totalImportedRecords = syncHistory.reduce((acc, curr) => acc + curr.records_imported, 0);
  const lastSync = connections.find((c) => c.last_sync_at)?.last_sync_at;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-foreground flex items-center gap-2.5">
            <Plug className="h-7 w-7 text-primary" />
            Integrations & Connector Centre
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Connect accounting software, ERPs, and POS feeds into the UrsBiz deterministic intelligence engine.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={loadData}
          disabled={isLoading}
          className="gap-2 shrink-0 self-start sm:self-auto"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {errorMsg && (
        <div className="rounded-xl bg-destructive/10 border border-destructive/20 p-4 text-sm text-destructive flex items-center gap-3">
          <ShieldAlert className="h-5 w-5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="flex items-center justify-between text-muted-foreground text-xs font-semibold uppercase tracking-wider mb-2">
            <span>Configured Sources</span>
            <Layers className="h-4 w-4 text-primary" />
          </div>
          <div className="text-2xl font-bold text-foreground">{totalConnections}</div>
          <p className="text-xs text-muted-foreground mt-1">Active data channels</p>
        </div>

        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="flex items-center justify-between text-muted-foreground text-xs font-semibold uppercase tracking-wider mb-2">
            <span>Live Connected</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
            {connectedCount}
          </div>
          <p className="text-xs text-muted-foreground mt-1">Authenticated & healthy</p>
        </div>

        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="flex items-center justify-between text-muted-foreground text-xs font-semibold uppercase tracking-wider mb-2">
            <span>Imported Records</span>
            <Database className="h-4 w-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold text-foreground">
            {totalImportedRecords.toLocaleString()}
          </div>
          <p className="text-xs text-muted-foreground mt-1">Across recent sync runs</p>
        </div>

        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="flex items-center justify-between text-muted-foreground text-xs font-semibold uppercase tracking-wider mb-2">
            <span>Last Sync</span>
            <Activity className="h-4 w-4 text-amber-500" />
          </div>
          <div className="text-sm font-semibold text-foreground truncate">
            {lastSync ? new Date(lastSync).toLocaleDateString() : "No sync yet"}
          </div>
          <p className="text-xs text-muted-foreground mt-1">Continuous provenance</p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-6 border-b border-border">
        <button
          onClick={() => setActiveTab("connections")}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
            activeTab === "connections"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Activity className="h-4 w-4" />
          Connections
          {connections.length > 0 && (
            <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-primary/20 text-primary font-bold">
              {connections.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("catalogue")}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
            activeTab === "catalogue"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Plug className="h-4 w-4" />
          Connector Catalogue
        </button>

        <button
          onClick={() => setActiveTab("history")}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
            activeTab === "history"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <History className="h-4 w-4" />
          Sync Runs
          {syncTotal > 0 && (
            <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-muted text-muted-foreground font-medium">
              {syncTotal}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("audits")}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
            activeTab === "audits"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <ShieldCheck className="h-4 w-4" />
          Audit Trail
        </button>
      </div>

      {activeTab === "connections" && (
        <ActiveConnectionsList
          connections={connections}
          onRefresh={loadData}
          onNavigateToCatalogue={() => setActiveTab("catalogue")}
        />
      )}

      {activeTab === "catalogue" && (
        <ConnectorCatalogue
          connectors={catalogue}
          onConnectionCreated={() => {
            loadData();
            setActiveTab("connections");
          }}
        />
      )}

      {activeTab === "history" && (
        <SyncHistoryTable
          executions={syncHistory}
          total={syncTotal}
          page={syncPage}
          pageSize={10}
          onPageChange={setSyncPage}
        />
      )}

      {activeTab === "audits" && (
        <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
          <div className="p-4 border-b border-border bg-muted/30">
            <h3 className="font-bold text-sm text-foreground">
              Immutable Integration Event Log
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Every connection creation, credential rotation, ping test, and sync run is recorded with append-only integrity.
            </p>
          </div>
          <div className="divide-y divide-border/60">
            {audits.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted-foreground">
                No integration events recorded yet.
              </div>
            ) : (
              audits.map((a) => (
                <div key={a.id} className="p-4 hover:bg-muted/20 transition-colors flex items-start justify-between gap-4">
                  <div>
                    <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-muted text-foreground border border-border">
                      {a.event_type}
                    </span>
                    {a.connector_id && (
                      <span className="ml-2 text-xs text-muted-foreground font-medium">
                        Connector: {a.connector_id}
                      </span>
                    )}
                    <div className="text-xs text-muted-foreground font-mono mt-1.5">
                      {JSON.stringify(a.details)}
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground whitespace-nowrap">
                    {new Date(a.created_at).toLocaleString()}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
