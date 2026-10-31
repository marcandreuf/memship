"use client";

import { useState, type ReactNode } from "react";
import { Tabs, TabsContent, TabsNav } from "@/components/ui/tabs";
import { useTabParam } from "@/hooks/use-url-state";

interface EntityTab {
  id: string;
  label: string;
  content: ReactNode;
  badge?: string | number;
}

interface EntityTabsProps {
  tabs: EntityTab[];
  /** Tab to open when the URL names none. Defaults to the first tab. */
  defaultTab?: string;
  /**
   * When true, a tab's content is mounted only after the tab is first
   * activated (and stays mounted afterwards). Use for tabs whose content
   * triggers on-demand data fetching that shouldn't fire on page load.
   */
  lazy?: boolean;
}

/**
 * The open tab lives in the URL (`?tab=`), not in component state.
 *
 * It was `useState`, which made opening a record from a tab a one-way trip:
 * Browser Back returned to the record's *first* tab, because nothing recorded
 * which tab had been left (memship#471). A query parameter also makes a tab
 * linkable and survives a refresh.
 *
 * This supersedes the per-page reading of `?tab=` that `profile/page.tsx` did
 * on its own. One mechanism, in the component every tabbed page already uses.
 */
export function EntityTabs({ tabs, defaultTab, lazy = false }: EntityTabsProps) {
  const [tab, setTab] = useTabParam();
  // Track which tabs have been opened so lazy content mounts once and persists.
  const [visited, setVisited] = useState<Set<string>>(() => new Set());

  if (tabs.length === 0) return null;

  // A `?tab=` naming a tab this record does not have is ignored rather than
  // rendering an empty panel: the id may be stale, or belong to a tab the
  // caller omitted for this user. Callers also build `tabs` from data, so the
  // first render often has none and must not freeze the choice.
  const named = tabs.some(({ id }) => id === tab) ? tab : undefined;
  const active = named ?? defaultTab ?? tabs[0]?.id;

  const onValueChange = (value: string) => {
    setTab(value);
    setVisited((prev) => (prev.has(value) ? prev : new Set(prev).add(value)));
  };

  return (
    <Tabs value={active} onValueChange={onValueChange}>
      <TabsNav
        items={tabs.map(({ id, label, badge }) => ({ value: id, label, badge }))}
        value={active ?? ""}
        onValueChange={onValueChange}
      />
      {tabs.map((tabItem) => (
        <TabsContent key={tabItem.id} value={tabItem.id}>
          {lazy && tabItem.id !== active && !visited.has(tabItem.id)
            ? null
            : tabItem.content}
        </TabsContent>
      ))}
    </Tabs>
  );
}
