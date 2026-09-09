"use client";

import { useState, type ReactNode } from "react";
import { Tabs, TabsContent, TabsNav } from "@/components/ui/tabs";

interface EntityTab {
  id: string;
  label: string;
  content: ReactNode;
  badge?: string | number;
}

interface EntityTabsProps {
  tabs: EntityTab[];
  defaultTab?: string;
  /**
   * When true, a tab's content is mounted only after the tab is first
   * activated (and stays mounted afterwards). Use for tabs whose content
   * triggers on-demand data fetching that shouldn't fire on page load.
   */
  lazy?: boolean;
}

export function EntityTabs({ tabs, defaultTab, lazy = false }: EntityTabsProps) {
  const initial = defaultTab || tabs[0]?.id;
  // Controlled so the dropdown in `TabsNav` can label itself with the open tab.
  // Seeded lazily rather than from `useState(initial)`: callers build `tabs`
  // from data, so the first render often has none and would freeze the initial
  // value at undefined.
  const [selected, setSelected] = useState<string>();
  // Track which tabs have been opened so lazy content mounts once and persists.
  const [visited, setVisited] = useState<Set<string>>(() => new Set());

  if (tabs.length === 0) return null;

  const active = selected ?? initial;

  const onValueChange = (value: string) => {
    setSelected(value);
    setVisited((prev) => (prev.has(value) ? prev : new Set(prev).add(value)));
  };

  return (
    <Tabs value={active} onValueChange={onValueChange}>
      <TabsNav
        items={tabs.map(({ id, label, badge }) => ({ value: id, label, badge }))}
        value={active ?? ""}
        onValueChange={onValueChange}
      />
      {tabs.map((tab) => (
        <TabsContent key={tab.id} value={tab.id}>
          {lazy && tab.id !== active && !visited.has(tab.id) ? null : tab.content}
        </TabsContent>
      ))}
    </Tabs>
  );
}
