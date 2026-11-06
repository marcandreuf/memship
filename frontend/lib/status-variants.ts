export type StatusVariant = "default" | "secondary" | "destructive" | "outline";

export const MEMBER_STATUS_VARIANTS: Record<string, StatusVariant> = {
  active: "default",
  pending: "secondary",
  suspended: "destructive",
  cancelled: "outline",
  expired: "outline",
};

export const REGISTRATION_STATUS_VARIANTS: Record<string, StatusVariant> = {
  confirmed: "default",
  waitlist: "secondary",
  pending: "outline",
  cancelled: "destructive",
};

export const ACTIVITY_STATUS_VARIANTS: Record<string, StatusVariant> = {
  draft: "outline",
  published: "default",
  archived: "secondary",
  cancelled: "destructive",
  completed: "secondary",
};

export const RECEIPT_STATUS_VARIANTS: Record<string, StatusVariant> = {
  new: "outline",
  pending: "secondary",
  emitted: "secondary",
  paid: "default",
  returned: "destructive",
  cancelled: "destructive",
  overdue: "destructive",
};

export const REMITTANCE_STATUS_VARIANTS: Record<string, StatusVariant> = {
  draft: "outline",
  ready: "secondary",
  submitted: "secondary",
  processed: "default",
  closed: "default",
  cancelled: "destructive",
};

export const MANDATE_STATUS_VARIANTS: Record<string, StatusVariant> = {
  active: "default",
  cancelled: "destructive",
  expired: "secondary",
};

export const BILLING_RUN_STATUS_VARIANTS: Record<string, StatusVariant> = {
  success: "default",
  failed: "destructive",
  partial_failure: "secondary",
};
