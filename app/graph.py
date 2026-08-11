from langgraph.graph import StateGraph, END
from app.state import AnalystState
from nodes.schema import schema_node
from nodes.generate_sql import generate_sql_node
from nodes.validate_sql import validate_sql_node
from nodes.answer_node import answer_node
from nodes.sql_node import sql_node

# Import the new nodes
from nodes.validate_visualization import validate_visualization_node
from nodes.render_plotly import render_plotly_node


builder = StateGraph(AnalystState)
builder.add_node("schema", schema_node)
builder.add_node("generate_sql", generate_sql_node)
builder.add_node("validate_sql", validate_sql_node)
builder.add_node("exec_sql", sql_node)

builder.add_node("validate_visualization", validate_visualization_node)
builder.add_node("render_plotly", render_plotly_node)
builder.add_node("answer_node", answer_node)

builder.set_entry_point("schema")

builder.add_edge("schema", "generate_sql")
builder.add_edge("generate_sql", "validate_sql")
builder.add_edge("validate_sql", "exec_sql")
builder.add_edge("validate_visualization", "render_plotly")
builder.add_edge("render_plotly", "answer_node")
builder.add_edge("exec_sql", "validate_visualization")

builder.add_edge("answer_node", END)

graph = builder.compile()
