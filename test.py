from app.graph import graph

result = graph.invoke(
    {
        "csv_path": "data/nmd.csv",
        "question": "what is the total sales?"
    }
)
print(result["answer"])