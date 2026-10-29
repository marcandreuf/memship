"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { usePartySearch } from "../hooks/use-entities";
import type { PartySearchResult } from "../services/entities-api";

interface PartyPickerProps {
  value: PartySearchResult | null;
  onSelect: (party: PartySearchResult | null) => void;
  placeholder?: string;
}

/**
 * Search-as-you-type selector for any party — a member's person or an entity.
 * Replaces the raw numeric party-ID inputs on the forms that address something
 * to a party (the mandate form first).
 */
export function PartyPicker({ value, onSelect, placeholder }: PartyPickerProps) {
  const t = useTranslations();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handle = setTimeout(() => setDebounced(query), 300);
    return () => clearTimeout(handle);
  }, [query]);

  const { data: results = [], isLoading } = usePartySearch(debounced);

  // Close on a click anywhere else; onBlur would fire before an option's click.
  useEffect(() => {
    function onPointerDown(event: PointerEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  if (value) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-md border px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm font-medium">{value.display_name}</span>
          <Badge variant="outline">{t(`entities.kinds.${value.kind}`)}</Badge>
          {value.national_id && (
            <span className="shrink-0 font-mono text-xs text-muted-foreground">
              {value.national_id}
            </span>
          )}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => {
            onSelect(null);
            setQuery("");
            setDebounced("");
          }}
        >
          {t("entities.partyPickerChange")}
        </Button>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative">
      <Input
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder ?? t("entities.partyPickerPlaceholder")}
        autoComplete="off"
      />
      {open && debounced.trim().length > 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover text-popover-foreground shadow-md">
          {isLoading ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">{t("common.loading")}</p>
          ) : results.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">
              {t("entities.partyPickerNoResults")}
            </p>
          ) : (
            <ul className="max-h-60 overflow-y-auto py-1">
              {results.map((party) => (
                <li key={party.id}>
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-accent"
                    onClick={() => {
                      onSelect(party);
                      setOpen(false);
                    }}
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="truncate">{party.display_name}</span>
                      <Badge variant="outline">{t(`entities.kinds.${party.kind}`)}</Badge>
                    </span>
                    {party.national_id && (
                      <span className="shrink-0 font-mono text-xs text-muted-foreground">
                        {party.national_id}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
