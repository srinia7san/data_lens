import pandas as pd
import os
from utils.console import node_start, node_detail, node_end

def validate_visualization_node(state):
    node_start("validate_viz", "Validating AI visualization recommendation")

    df_path = state.get("df_path")
    df = pd.read_parquet(df_path) if df_path and os.path.exists(df_path) else None

    ai_chart = state.get("ai_chart_type", "").lower()
    x_axis = state.get("ai_x_axis")
    y_axis = state.get("ai_y_axis")
    title = state.get("ai_title", "Data Visualization")
    
    if df is None or df.empty:
        node_detail("validate_viz", "Warning", "DataFrame is empty or missing. Cannot visualize.")
        state["final_visualization"] = None
        node_end("validate_viz", "Validation complete - empty data")
        return state
        
    columns = list(df.columns)
    valid_x = x_axis in columns
    valid_y = y_axis in columns
    
    # Simple Rule-Based Engine
    final_chart = ai_chart
    final_x = x_axis if valid_x else None
    final_y = y_axis if valid_y else None
    
    # 1. Column existence validation (Fallback to first two columns)
    if not valid_x or not valid_y:
        node_detail("validate_viz", "Issue", "AI suggested columns not in dataframe. Engaging fallback.")
        if len(columns) >= 2:
            final_x = columns[0]
            final_y = columns[1]
        elif len(columns) == 1:
            final_x = columns[0]
            final_chart = "histogram"
            
    # 2. Data size validation (e.g., Pie chart with too many categories)
    if final_chart == "pie" and final_x:
        unique_categories = df[final_x].nunique()
        if unique_categories > 15:
            node_detail("validate_viz", "Issue", "Too many categories for Pie chart. Switching to Bar chart.")
            final_chart = "bar"
            
    # Build final validated config
    config = {
        "chart_type": final_chart,
        "x_axis": final_x,
        "y_axis": final_y,
        "title": title,
        "x_label": state.get("ai_x_label", final_x),
        "y_label": state.get("ai_y_label", final_y)
    }
    
    state["final_visualization"] = config
    node_detail("validate_viz", "Final Config", str(config))
    node_end("validate_viz", "Validation complete")
    
    return state
