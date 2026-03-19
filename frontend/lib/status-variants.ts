export const MEMBER_STATUS_VARIANTS: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  active: "default",
  pending: "secondary",
  suspended: "destructive",
  cancelled: "outline",
  expired: "outline",
};

export const ACTIVITY_STATUS_VARIANTS: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  draft: "outline",
  published: "default",
  archived: "secondary",
  cancelled: "destructive",
  completed: "secondary",
};
