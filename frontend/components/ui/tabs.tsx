"use client"

import * as React from "react"
import { Tabs as TabsPrimitive } from "radix-ui"
import { useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"

function Tabs({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      className={cn("flex flex-col gap-2", className)}
      {...props}
    />
  )
}

function TabsList({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn(
        "inline-flex h-9 w-full min-w-0 items-center justify-start gap-1 overflow-x-auto rounded-none border-b bg-transparent p-0",
        className
      )}
      {...props}
    />
  )
}

function TabsTrigger({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-none border-b-2 border-transparent px-3 py-1.5 text-sm font-medium text-muted-foreground transition-all hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 data-[state=active]:border-primary data-[state=active]:text-foreground",
        className
      )}
      {...props}
    />
  )
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("mt-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2", className)}
      {...props}
    />
  )
}

export interface TabsNavItem {
  value: string
  label: string
  badge?: string | number
}

// Where the bar gives way to the dropdown. Container widths, not viewport ones:
// the container is the content column, so a collapsed sidebar brings the bar
// back at a viewport width that would still hide it under a media query. The
// right threshold depends on how many tabs there are, hence the choice.
const COLLAPSE = {
  sm: { menu: "@md:hidden", list: "hidden @md:inline-flex" },
  md: { menu: "@2xl:hidden", list: "hidden @2xl:inline-flex" },
  lg: { menu: "@4xl:hidden", list: "hidden @4xl:inline-flex" },
} as const

interface TabsNavProps {
  items: TabsNavItem[]
  value: string
  onValueChange: (value: string) => void
  /** How wide the container must be before the bar replaces the dropdown. */
  collapse?: keyof typeof COLLAPSE
}

/**
 * The navigation for a `Tabs`, as a bar in a wide container and as a select in
 * a narrow one. `TabsList` scrolls sideways rather than overflowing the page,
 * but a scrolling nav hides its own tabs — past a few triggers there is nothing
 * on screen to say the rest exist. Both paths write the same value, so the
 * active tab survives a resize across the threshold.
 *
 * Controlled, because the select trigger has to render the active tab's label.
 */
function TabsNav({ items, value, onValueChange, collapse = "md" }: TabsNavProps) {
  const t = useTranslations()

  const label = (item: TabsNavItem) => (
    <>
      {item.label}
      {item.badge !== undefined && (
        <Badge variant="secondary" className="ml-1.5 px-1.5 py-0 text-xs">
          {item.badge}
        </Badge>
      )}
    </>
  )

  return (
    <>
      {/* The bar comes first in the DOM even though the select is what shows in
          a narrow container: the select trigger repeats the active tab's label,
          so a text query would otherwise resolve to whichever of the two is
          hidden. */}
      <TabsList className={COLLAPSE[collapse].list}>
        {items.map((item) => (
          <TabsTrigger key={item.value} value={item.value}>
            {label(item)}
          </TabsTrigger>
        ))}
      </TabsList>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger
          aria-label={t("common.sections")}
          className={cn("w-full", COLLAPSE[collapse].menu)}
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {items.map((item) => (
            <SelectItem key={item.value} value={item.value}>
              {label(item)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </>
  )
}

export { Tabs, TabsList, TabsNav, TabsTrigger, TabsContent }
