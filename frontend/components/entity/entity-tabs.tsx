"use client";

import { type ReactNode } from "react";
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
}

export function EntityTabs({ tabs, defaultTab }: EntityTabsProps) {
  if (tabs.length === 0) return null;

  return (
    <Tabs defaultValue={defaultTab || tabs[0].id}>
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
          {tab.content}
        </TabsContent>
      ))}
    </Tabs>
  );
}
