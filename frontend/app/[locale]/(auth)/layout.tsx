import { AppFooter } from "@/components/layout/footer";

// The auth screens had no footer at all, so the licence notice the AGPL
// release ships was absent from login and registration (#527). The route group
// owns the full-height column and each page fills it with `flex-1`, so the
// footer sits at the bottom of the viewport rather than below the fold.
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      {children}
      <AppFooter />
    </div>
  );
}
