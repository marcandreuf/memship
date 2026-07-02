"use client";

import { useState, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

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
  // Track which tabs have been opened so lazy content mounts once and persists.
  const [visited, setVisited] = useState<Set<string>>(
    () => new Set(initial ? [initial] : [])
  );

  if (tabs.length === 0) return null;

  return (
    <Tabs
      defaultValue={initial}
      onValueChange={(value) =>
        setVisited((prev) =>
          prev.has(value) ? prev : new Set(prev).add(value)
        )
      }
    >
      <TabsList>
        {tabs.map((tab) => (
          <TabsTrigger key={tab.id} value={tab.id}>
            {tab.label}
            {tab.badge !== undefined && (
              <Badge variant="secondary" className="ml-1.5 text-xs px-1.5 py-0">
                {tab.badge}
              </Badge>
            )}
          </TabsTrigger>
        ))}
      </TabsList>
      {tabs.map((tab) => (
        <TabsContent key={tab.id} value={tab.id}>
          {lazy && !visited.has(tab.id) ? null : tab.content}
        </TabsContent>
      ))}
    </Tabs>
  );
}
