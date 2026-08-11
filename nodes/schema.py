from schema.models import TableSchema
from schema.schema_discovery import discover_schema
from typing import List, Dict, Any
import os
import uuid
from google import genai
from pinecone import Pinecone, ServerlessSpec
from utils.console import node_start, node_detail, node_end


def _gemini_embed(text: str, api_key: str | None = None) -> List[float]:
    api_key = api_key or os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found – set it in your .env or export it."
        )
    client = genai.Client(api_key=api_key)
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config={"output_dimensionality": 768},
    )
    return response.embeddings[0].values


def _get_pinecone_index(api_key: str | None = None):
    pc_api_key = api_key or os.getenv("PINECONE_API_KEY")
    pc_index_name=os.getenv("PINECONE_INDEX_NAME","schema-embeddings")

    if not pc_api_key:
        raise RuntimeError(
            "PINECONE_API_KEY not found set it in your .env or export it."
        )
    pc = Pinecone(api_key=pc_api_key)

    existing_indexes = [idx.name for idx in pc.list_indexes()]
    if pc_index_name not in existing_indexes:
        pc.create_index(
            name=pc_index_name,
            dimension=768,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    return pc.Index(pc_index_name)

def _resolve_source_type(state: dict) -> str:

    if state.get("connection_string"):
        return "sql"
    raise ValueError("Provide a 'connection_string' for SQL analysis")



def _format_table_schema(table: TableSchema) -> str:
    lines = [f"table: {table.name}", "columns:"]
    lines.extend(f"- {column.name}: {column.datatype}" for column in table.columns)

    if table.primary_keys:
        lines.append(f"primary_keys: {', '.join(table.primary_keys)}")

    if table.foreign_keys:
        lines.append("foreign_keys:")
        lines.extend(
            f"- {fk.column} -> {fk.ref_table}.{fk.ref_column}"
            for fk in table.foreign_keys
        )

    return "\n".join(lines)


def _format_database_schema(schema: dict[str, TableSchema]) -> str:
    return "\n\n".join(_format_table_schema(table) for table in schema.values())


def _reconstruct_schema(raw: dict) -> dict[str, TableSchema]:
    """Rebuild ``TableSchema`` objects from a plain dict received over WebSocket."""
    result: dict[str, TableSchema] = {}
    for table_name, table_data in raw.items():
        columns = [
            Column(name=c["name"], datatype=c["datatype"])
            for c in table_data.get("columns", [])
        ]
        primary_keys = table_data.get("primary_keys", [])
        foreign_keys = [
            ForeignKey(
                column=fk["column"],
                ref_table=fk["ref_table"],
                ref_column=fk["ref_column"],
            )
            for fk in table_data.get("foreign_keys", [])
        ]
        result[table_name] = TableSchema(
            name=table_name,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
        )
    return result


def schema_node(state: Dict[str, Any]) -> Dict[str, Any]:
    node_start("schema", "Discovering database schema & generating embeddings")

    source_type = _resolve_source_type(state)
    state["source_type"] = source_type
    node_detail("schema", "Source type", source_type)

    # Only SQL source is supported now
    connection_string = state["connection_string"]
    user_id = state.get("user_id")

    # Route through WebSocket connector if available
    from app import ws_hub
    if user_id and ws_hub.has_connection(user_id):
        node_detail("schema", "Mode", "WebSocket connector (remote)")
        import asyncio
        try:
            raw_schema = asyncio.get_event_loop().run_until_complete(
                ws_hub.execute_remote(user_id, "discover_schema", {
                    "connection_string": connection_string,
                })
            )
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                raw_schema = loop.run_until_complete(
                    ws_hub.execute_remote(user_id, "discover_schema", {
                        "connection_string": connection_string,
                    })
                )
            finally:
                loop.close()
        # Reconstruct TableSchema objects from the dict sent over WebSocket
        discovered_schema = _reconstruct_schema(raw_schema)
    else:
        node_detail("schema", "Mode", "Direct SQLAlchemy connection")
        discovered_schema = discover_schema(connection_string)

    schema_context = _format_database_schema(discovered_schema)

    table_names = list(discovered_schema.keys())
    node_detail("schema", "Tables discovered", f"{len(table_names)} tables: {', '.join(table_names)}")

    # Extract db_name for namespace (e.g., .../pagila -> pagila)
    db_name = connection_string.split("/")[-1].split("?")[0]
    state["pinecone_namespace"] = db_name

    index = _get_pinecone_index(state.get("pinecone_api_key"))
    stats = index.describe_index_stats()
    is_embedded = db_name in stats.namespaces and stats.namespaces[db_name].vector_count > 0
    force_reembed = state.get("force_reembed", False)

    if is_embedded and not force_reembed:
        node_detail("schema", "Pinecone", f"Namespace '{db_name}' already embedded, skipping upsert.")
    else:
        vectors = []
        # Loop through each table, embed it, and prepare for Pinecone
        for table_name, table in discovered_schema.items():
            table_text = _format_table_schema(table)
            embedding_vector = _gemini_embed(table_text, state.get("gemini_api_key"))
            
            # Use deterministic ID to prevent duplicates
            vector_id = table_name
            metadata = {"schema_text": table_text, "table_name": table_name}
            
            vectors.append((vector_id, embedding_vector, metadata))
            
        # Upsert all table vectors into Pinecone at once
        if vectors:
            index.upsert(vectors=vectors, namespace=db_name)
            node_detail("schema", "Pinecone", f"Upserted {len(vectors)} vectors to namespace '{db_name}'.")

    state["schema"] = discovered_schema
    state["schema_context"] = schema_context
    state["pinecone_vector_id"] = "table-by-table-upsert"

    node_end("schema", f"Schema indexed with {len(table_names)} tables")
    return state

# ---------------------------------------------------------------------------
# Stand‑alone execution helper
# ---------------------------------------------------------------------------
