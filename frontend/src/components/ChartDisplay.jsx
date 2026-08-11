import { useEffect, useRef, useMemo } from "react";

/**
 * Renders a Plotly chart from query results + the AI chart config.
 * Uses window.Plotly (loaded via CDN script tag in index.html).
 */
export default function ChartDisplay({ config, rows }) {
  const chartRef = useRef(null);
  const Plotly = window.Plotly;

  // Build the plotly figure from config + rows
  const figure = useMemo(() => {
    if (!config || !rows || rows.length === 0) return null;

    const { chart_type, x_axis, y_axis, title, x_label, y_label } = config;

    const xValues = rows.map((r) => r[x_axis]);
    const yValues = rows.map((r) => r[y_axis]);

    let trace;
    switch (chart_type) {
      case "pie":
        trace = {
          type: "pie",
          labels: xValues,
          values: yValues,
          hole: 0.4,
          marker: {
            colors: [
              "#2563eb", "#3b82f6", "#10b981", "#f59e0b", "#ef4444",
              "#6366f1", "#a855f7", "#ec4899", "#14b8a6", "#84cc16",
            ],
          },
          textfont: { color: "#f8fafc" },
        };
        break;

      case "scatter":
        trace = {
          type: "scatter",
          mode: "markers",
          x: xValues,
          y: yValues,
          marker: { color: "#2563eb", size: 8 },
        };
        break;

      case "line":
        trace = {
          type: "scatter",
          mode: "lines+markers",
          x: xValues,
          y: yValues,
          line: { color: "#2563eb", width: 2.5 },
          marker: { color: "#3b82f6", size: 6 },
        };
        break;

      case "area":
        trace = {
          type: "scatter",
          mode: "lines",
          fill: "tozeroy",
          x: xValues,
          y: yValues,
          line: { color: "#2563eb" },
          fillcolor: "#142244",
        };
        break;

      case "histogram":
        trace = {
          type: "histogram",
          x: xValues,
          marker: { color: "#2563eb" },
        };
        break;

      case "box":
        trace = {
          type: "box",
          x: xValues,
          y: yValues,
          marker: { color: "#2563eb" },
        };
        break;

      case "bar":
      default:
        trace = {
          type: "bar",
          x: xValues,
          y: yValues,
          marker: {
            color: "#2563eb",
            line: { color: "#3b82f6", width: 1 },
          },
        };
        break;
    }

    const layout = {
      title: {
        text: title || "",
        font: { color: "#f8fafc", size: 15, family: "inherit" },
      },
      xaxis: {
        title: { text: x_label || x_axis, font: { color: "#94a3b8", size: 12 } },
        color: "#94a3b8",
        gridcolor: "#1e2433",
        tickfont: { size: 11, color: "#94a3b8" },
        automargin: true,
      },
      yaxis: {
        title: { text: y_label || y_axis, font: { color: "#94a3b8", size: 12 } },
        color: "#94a3b8",
        gridcolor: "#1e2433",
        tickfont: { size: 11, color: "#94a3b8" },
        automargin: true,
      },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { family: "inherit", color: "#f8fafc" },
      margin: { t: 40, r: 24, b: 50, l: 50 },
      showlegend: chart_type === "pie",
      legend: { font: { color: "#94a3b8", size: 11 } },
      autosize: true,
      height: 420,
    };

    return { data: [trace], layout };
  }, [config, rows]);

  useEffect(() => {
    if (!figure || !chartRef.current) return;

    Plotly.newPlot(chartRef.current, figure.data, figure.layout, {
      responsive: true,
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
    });

    const handleResize = () => {
      if (chartRef.current) {
        Plotly.Plots.resize(chartRef.current);
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      if (chartRef.current) {
        Plotly.purge(chartRef.current);
      }
    };
  }, [figure]);

  if (!figure) return null;

  return <div className="chart-container" ref={chartRef} />;
}
