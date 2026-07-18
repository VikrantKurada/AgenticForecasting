export default function HomePage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">Agentic Forecasting</h1>
      <p className="max-w-md text-sm text-slate-500 dark:text-slate-400">
        Create a project in the sidebar, open a chat, and ask a forecasting question —
        GDP and inflation nowcasts, sovereign default risk, yield curve trajectories,
        or geopolitical spillovers. A team of agents plans the workflow, pulls real
        data, runs the models, and explains its methodology.
      </p>
    </div>
  )
}
