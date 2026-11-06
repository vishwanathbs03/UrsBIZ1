"use client";

import React, { useState } from "react";
import {
  ConnectionOut,
  ConnectionTestResultOut,
  integrationService,
} from "@/services/integration-service";
import { Button } from "@/components/ui/button";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock,
  KeyRound,
  Play,
  Plug,
  RefreshCw,
  Trash2,
  Unplug,
  XCircle,
} from "lucide-react";

interface ActiveConnectionsListProps {
  connections: ConnectionOut[];
  onRefresh: () => void;
  onNavigateToCatalogue: () => void;
}

export const ActiveConnectionsList: React.FC<ActiveConnectionsListProps> = ({
  connections,
  onRefresh,
  onNavigateToCatalogue,
}) => {
  const [loadingActions, setLoadingActions] = useState<Record<string, boolean>>({});
  const [testResults, setTestResults] = useState<Record<number, ConnectionTestResultOut>>({});
  const [actionError, setActionError] = useState<string | null>(null);

  const setBusy = (id: number, action: string, busy: boolean) => {
    setLoadingActions((prev) => ({ ...prev, [`${id}_${action}`]: busy }));
  };

  const isBusy = (id: number, action: string) => {
    return !!loadingActions[`${id}_${action}`];
  };

  const handleTest = async (conn: ConnectionOut) => {
    setActionError(null);
    setBusy(conn.id, "test", true);
    try {
      const res = await integrationService.testConnection(conn.id);
      setTestResults((prev) => ({ ...prev, [conn.id]: res }));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Connection test failed.";
      setActionError(msg);
    } finally {
      setBusy(conn.id, "test", false);
    }
  };

  const handleConnect = async (conn: ConnectionOut) => {
    setActionError(null);
    setBusy(conn.id, "connect", true);
    try {
      await integrationService.connect(conn.id);
      onRefresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Connect failed.";
      setActionError(msg);
    } finally {
      setBusy(conn.id, "connect", false);
    }
  };

  const handleDisconnect = async (conn: ConnectionOut) => {
    setActionError(null);
    setBusy(conn.id, "disconnect", true);
    try {
      await integrationService.disconnect(conn.id);
      onRefresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Disconnect failed.";
      setActionError(msg);
    } finally {
      setBusy(conn.id, "disconnect", false);
    }
  };

  const handleSync = async (conn: ConnectionOut) => {
    setActionError(null);
    setBusy(conn.id, "sync", true);
    try {
      await integrationService.triggerSync(conn.id);
      onRefresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Sync failed.";
      setActionError(msg);
    } finally {
      setBusy(conn.id, "sync", false);
    }
  };

  const handleDelete = async (conn: ConnectionOut) => {
    if (!window.confirm(`Are you sure you want to remove connection '${conn.name}'?`)) {
      return;
    }
    setActionError(null);
    setBusy(conn.id, "delete", true);
    try {
      await integrationService.deleteConnection(conn.id);
      onRefresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete connection.";
      setActionError(msg);
    } finally {
      setBusy(conn.id, "delete", false);
    }
  };

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case "CONNECTED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3.5 w-3.5" /> Connected
          </span>
        );
      case "CONFIGURED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <Clock className="h-3.5 w-3.5" /> Configured
          </span>
        );
      case "CONNECTING":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 animate-pulse">
            <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Connecting
          </span>
        );
      case "REAUTH_REQUIRED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-500/20">
            <KeyRound className="h-3.5 w-3.5" /> Re-auth Required
          </span>
        );
      case "ERROR":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-destructive/10 text-destructive border border-destructive/20">
            <XCircle className="h-3.5 w-3.5" /> Error
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-muted text-muted-foreground border border-border">
            <Unplug className="h-3.5 w-3.5" /> Disconnected
          </span>
        );
    }
  };

  if (connections.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card/40 p-12 text-center">
        <div className="mx-auto w-12 h-12 rounded-full bg-primary/10 text-primary flex items-center justify-center mb-4">
          <Plug className="h-6 w-6" />
        </div>
        <h3 className="text-base font-semibold text-foreground mb-1">
          No external data sources connected
        </h3>
        <p className="text-sm text-muted-foreground max-w-md mx-auto mb-6">
          Connect your Tally Prime, Zoho Books, or recurring POS feeds to continuously synchronize verified business transactions.
        </p>
        <Button onClick={onNavigateToCatalogue}>Browse Connector Catalogue</Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {actionError && (
        <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4">
        {connections.map((conn) => {
          const testRes = testResults[conn.id];
          return (
            <div
              key={conn.id}
              className="rounded-xl border border-border bg-card p-5 shadow-sm space-y-4"
            >
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-primary/10 text-primary">
                    <Activity className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-foreground flex items-center gap-2">
                      {conn.name}
                      <span className="text-xs font-medium text-muted-foreground">
                        ({conn.connector_id})
                      </span>
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      Created on {new Date(conn.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {renderStatusBadge(conn.status)}
                </div>
              </div>

              {conn.last_error_message && (
                <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-xs text-destructive flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold">{conn.last_error_category}: </span>
                    {conn.last_error_message}
                  </div>
                </div>
              )}

              {testRes && (
                <div
                  className={`rounded-lg p-3 text-xs flex items-center gap-2 border ${
                    testRes.success
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                      : "bg-destructive/10 text-destructive border-destructive/20"
                  }`}
                >
                  {testRes.success ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                  ) : (
                    <AlertCircle className="h-4 w-4 shrink-0" />
                  )}
                  <span>{testRes.message}</span>
                </div>
              )}

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-2 border-y border-border/60 text-xs">
                <div>
                  <span className="text-muted-foreground block mb-0.5">Masked Credentials</span>
                  <span className="font-mono text-foreground font-medium">
                    {conn.masked_credentials?.api_key ||
                      conn.masked_credentials?.auth_token ||
                      (conn.has_credentials ? "••••••••" : "Unset")}
                  </span>
                </div>

                <div>
                  <span className="text-muted-foreground block mb-0.5">Last Sync Status</span>
                  <span className="font-semibold text-foreground">
                    {conn.last_sync_status || "Never Run"}
                  </span>
                </div>

                <div>
                  <span className="text-muted-foreground block mb-0.5">Last Synchronized</span>
                  <span className="text-foreground">
                    {conn.last_sync_at
                      ? new Date(conn.last_sync_at).toLocaleString()
                      : "Never"}
                  </span>
                </div>

                <div>
                  <span className="text-muted-foreground block mb-0.5">Sync Cursor</span>
                  <span className="font-mono text-foreground">
                    {conn.sync_cursor ? `Cursor: ${conn.sync_cursor}` : "Initial (Head)"}
                  </span>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleTest(conn)}
                    disabled={isBusy(conn.id, "test")}
                  >
                    {isBusy(conn.id, "test") ? "Testing..." : "Test Ping"}
                  </Button>

                  {conn.status === "CONNECTED" ? (
                    <>
                      <Button
                        size="sm"
                        onClick={() => handleSync(conn)}
                        disabled={isBusy(conn.id, "sync")}
                        className="gap-1.5"
                      >
                        <Play className="h-3.5 w-3.5" />
                        {isBusy(conn.id, "sync") ? "Syncing..." : "Sync Now"}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDisconnect(conn)}
                        disabled={isBusy(conn.id, "disconnect")}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        Disconnect
                      </Button>
                    </>
                  ) : (
                    <Button
                      size="sm"
                      onClick={() => handleConnect(conn)}
                      disabled={isBusy(conn.id, "connect")}
                    >
                      {isBusy(conn.id, "connect") ? "Connecting..." : "Connect Provider"}
                    </Button>
                  )}
                </div>

                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => handleDelete(conn)}
                  disabled={isBusy(conn.id, "delete")}
                  className="text-destructive hover:bg-destructive/10"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
