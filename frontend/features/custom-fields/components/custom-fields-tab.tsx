"use client";

import { TabContentSkeleton } from "@/components/ui/skeletons";
import {
  useCustomFields,
  usePersonCustomFields,
  useUpdatePersonCustomFields,
} from "../hooks/use-custom-fields";
import { CustomFieldsForm } from "./custom-fields-form";

/** Custom fields for one person, as a tab on the member detail page.
 *  Values hang off the person, so this takes personId — the same shape as
 *  ContactInfoTab. */
export function CustomFieldsTab({ personId }: { personId: number }) {
  const { data: definitions = [], isLoading: loadingDefinitions } =
    useCustomFields();
  const { data: values = {}, isLoading: loadingValues } =
    usePersonCustomFields(personId);
  const updateMutation = useUpdatePersonCustomFields(personId);

  if (loadingDefinitions || loadingValues) return <TabContentSkeleton />;

  return (
    <CustomFieldsForm
      definitions={definitions}
      values={values}
      onSave={(next) => updateMutation.mutateAsync(next)}
      isSaving={updateMutation.isPending}
    />
  );
}
