// Story 1.2 stand-in screen. The full cockpit shell (auth-protected routes,
// role-aware nav, marble palette tokens) lands in Story 1.10. This page just
// confirms Tailwind, the Vite dev server, and HMR are wired end-to-end.

function App() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 text-zinc-950">
      <div className="text-center">
        <h1 className="text-4xl font-medium tracking-tight">Hello, cockpit.</h1>
        <p className="mt-3 text-sm text-zinc-500">
          Edit <code className="rounded bg-zinc-100 px-1 py-0.5">src/App.tsx</code> and save — HMR
          keeps this page live.
        </p>
      </div>
    </main>
  );
}

export default App;
