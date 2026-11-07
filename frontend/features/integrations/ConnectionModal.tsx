"use client";

import React, { useState, useEffect } from "react";
import {
  ConnectorCatalogueItem,
  ConfigFieldOut,
  ConnectionCreateReq,
  integrationService,
} from "@/services/integration-service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Eye, EyeOff, X, ShieldAlert, CheckCircle2 } from "lucide-react";

interface ConnectionModalProps {
  connector: ConnectorCatalogueItem;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const ConnectionModal: React.FC<ConnectionModalProps> = ({
  connector,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [connectionName, setConnectionName] = useState(`${connector.name} Connection`);
  const [configValues, setConfigValues] = useState<Record<string, unknown>>(() => {
    const defaults: Record<string, unknown> = {};
    connector.config_fields.forEach((f) => {
      if (!f.is_secret && f.default_value !== undefined && f.default_value !== null) {
        defaults[f.key] = f.default_value;
      }
    });
    return defaults;
  });
  const [credentialValues, setCredentialValues] = useState<Record<string, unknown>>({});
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleConfigChange = (key: string, value: unknown) => {
    setConfigValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleCredentialChange = (key: string, value: unknown) => {
    setCredentialValues((prev) => ({ ...prev, [key]: value }));
  };

  const toggleShowSecret = (key: string) => {
    setShowSecrets((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);
    setIsSubmitting(true);

    try {
      const payload: ConnectionCreateReq = {
        connector_id: connector.connector_id,
        name: connectionName.trim(),
        configuration: configValues,
        credentials: credentialValues,
      };

      await integrationService.createConnection(payload);
      setSuccessMsg("Connection configured successfully! You can now verify authentication.");
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create connection.";
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const configFields = connector.config_fields.filter((f) => !f.is_secret);
  const secretFields = connector.config_fields.filter((f) => f.is_secret);

  return (
    <div role="dialog" aria-modal="true" aria-label="Connector Configuration" className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-xl rounded-xl border border-border bg-card shadow-2xl p-6 my-8 animate-in fade-in zoom-in-95 duration-200">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          aria-label="Close dialog"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="mb-5">
          <h2 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            Configure {connector.name}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {connector.description}
          </p>
        </div>

        {errorMsg && (
          <div className="mb-4 rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive flex items-start gap-2.5">
            <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />
            <div>{errorMsg}</div>
          </div>
        )}

        {successMsg && (
          <div className="mb-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-3 text-sm text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <div>{successMsg}</div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
              Connection Name <span className="text-destructive">*</span>
            </label>
            <Input
              value={connectionName}
              onChange={(e) => setConnectionName(e.target.value)}
              required
              placeholder="e.g. Main Bangalore Store"
            />
          </div>

          {configFields.length > 0 && (
            <div className="space-y-3 pt-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Configuration Settings
              </h3>
              {configFields.map((field) => (
                <div key={field.key}>
                  <label className="block text-xs font-medium text-foreground mb-1">
                    {field.label} {field.required && <span className="text-destructive">*</span>}
                  </label>
                  {field.options && field.options.length > 0 ? (
                    <select
                      className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                      value={String(configValues[field.key] ?? field.default_value ?? "")}
                      onChange={(e) => handleConfigChange(field.key, e.target.value)}
                      required={field.required}
                    >
                      {field.options.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <Input
                      type={field.field_type === "number" ? "number" : "text"}
                      value={String(configValues[field.key] ?? "")}
                      onChange={(e) =>
                        handleConfigChange(
                          field.key,
                          field.field_type === "number" ? Number(e.target.value) : e.target.value
                        )
                      }
                      required={field.required}
                      placeholder={field.description || field.label}
                    />
                  )}
                  {field.description && (
                    <p className="text-xs text-muted-foreground mt-1">{field.description}</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {secretFields.length > 0 && (
            <div className="space-y-3 pt-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-amber-500 flex items-center gap-1.5">
                Authentication & Credentials (Encrypted at Rest)
              </h3>
              {secretFields.map((field) => {
                const isVisible = !!showSecrets[field.key];
                return (
                  <div key={field.key}>
                    <label className="block text-xs font-medium text-foreground mb-1">
                      {field.label} {field.required && <span className="text-destructive">*</span>}
                    </label>
                    <div className="relative">
                      <Input
                        type={isVisible ? "text" : "password"}
                        value={String(credentialValues[field.key] ?? "")}
                        onChange={(e) => handleCredentialChange(field.key, e.target.value)}
                        required={field.required}
                        placeholder={field.description || "Enter secret key"}
                        className="pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => toggleShowSecret(field.key)}
                        className="absolute right-3 top-2.5 text-muted-foreground hover:text-foreground"
                      >
                        {isVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    {field.description && (
                      <p className="text-xs text-muted-foreground mt-1">{field.description}</p>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <div className="pt-4 flex items-center justify-end gap-3 border-t border-border">
            <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || !connectionName.trim()}>
              {isSubmitting ? "Configuring..." : "Save Connection"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
