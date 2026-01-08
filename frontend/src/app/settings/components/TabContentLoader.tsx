export function TabContentLoader({ children }: { children: string }) {
  return (
    <div className="flex items-center justify-center h-32">
      <div className="text-muted-foreground">Loading {children}...</div>
    </div>
  );
}
