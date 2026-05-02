// PanelStub — Story 3.6 AC #6.
// Placeholder for the three non-Documents panels (Identity, UBO, Risk)
// that land in Epic 5+. Minimal: dashed border, title, "Coming in Epic N".

export interface PanelStubProps {
  title: string;
  epic: string;
}

export function PanelStub({ title, epic }: PanelStubProps): JSX.Element {
  return (
    <div className="rounded-md border-2 border-dashed border-zinc-300 bg-zinc-50 px-4 py-6 flex flex-col items-center justify-center min-h-[200px]">
      <h3 className="text-sm font-semibold text-zinc-700 mb-1">{title}</h3>
      <p className="text-xs text-zinc-500">Coming in Epic {epic}</p>
    </div>
  );
}
