declare module 'plotly.js-dist-min'
declare module 'react-plotly.js/factory' {
  import type * as React from 'react'
  import type { PlotParams } from 'react-plotly.js'

  export default function createPlotlyComponent(plotly: unknown): React.ComponentType<PlotParams>
}
