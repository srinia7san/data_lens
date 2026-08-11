import pandas as pd
import plotly.express as px
import tempfile
import os
from utils.console import node_start, node_detail, node_end

def render_plotly_node(state):
    node_start("render_plotly", "Rendering Plotly Visualization")

    if state.get("response_mode") == "answer":
        state["final_visualization"] = None
        node_detail("render_plotly", "Skip", "Response mode is answer-only.")
        node_end("render_plotly", "Skipped rendering")
        return state
    
    df_path = state.get("df_path")
    df = pd.read_parquet(df_path) if df_path and os.path.exists(df_path) else None
    config = state.get("final_visualization")
    
    if df is None or df.empty or not config:
        node_detail("render_plotly", "Skip", "No data or config to render.")
        node_end("render_plotly", "Skipped rendering")
        return state
        
    chart_type = config.get("chart_type")
    x = config.get("x_axis")
    y = config.get("y_axis")
    title = config.get("title")
    labels = {
        x: config.get("x_label", x),
        y: config.get("y_label", y)
    }
    
    fig = None
    try:
        # Match Chart Type
        if chart_type in ["bar", "column"]:
            fig = px.bar(df, x=x, y=y, title=title, labels=labels)
        elif chart_type == "line":
            fig = px.line(df, x=x, y=y, title=title, labels=labels)
        elif chart_type == "scatter":
            fig = px.scatter(df, x=x, y=y, title=title, labels=labels)
        elif chart_type == "pie":
            fig = px.pie(df, names=x, values=y, title=title)
        elif chart_type == "histogram":
            fig = px.histogram(df, x=x, title=title, labels=labels)
        elif chart_type == "violin":
            fig = px.violin(df, x=x, y=y, title=title, labels=labels, box=True)
        elif chart_type == "box":
            fig = px.box(df, x=x, y=y, title=title, labels=labels)
        elif chart_type == "area":
            fig = px.area(df, x=x, y=y, title=title, labels=labels)
        elif chart_type == "treemap":
            fig = px.treemap(df, path=[x], values=y, title=title)
        elif chart_type == "sunburst":
            fig = px.sunburst(df, path=[x], values=y, title=title)
        elif chart_type == "funnel":
            fig = px.funnel(df, x=y, y=x, title=title) # Funnel plots often flip x and y for visual flow
        else:
            # Ultimate Fallback
            fig = px.bar(df, x=x, y=y, title=title, labels=labels)
            
        fig.update_layout(template="plotly_dark") # Beautiful dark theme
        
        # Save to temporary HTML file
        fd, path = tempfile.mkstemp(suffix=".html", prefix="da_report_")
        os.close(fd)
        
        fig.write_html(path)
        state["html_report_path"] = path
        
        node_detail("render_plotly", "Report Path", path)

    except Exception as e:
        node_detail("render_plotly", "Error", f"Failed to render chart: {e}")
        
    node_end("render_plotly", "Rendering complete")
    return state
