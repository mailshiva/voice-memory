from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, TOP_K

_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def store_memory(content: str, embedding: list[float], source: str) -> int:
    """Save a transcribed or typed memo along with its embedding.
    Returns the new memory's id, so it can be shown to the user for later
    reference (e.g. so they can erase it by id)."""
    result = _client.table("memories").insert({
        "content": content,
        "embedding": embedding,
        "source": source,
    }).execute()
    return result.data[0]["id"]


def delete_memory(memory_id: int) -> bool:
    """Delete a memory by id. Returns True if a row was actually deleted."""
    result = _client.table("memories").delete().eq("id", memory_id).execute()
    return bool(result.data)


def search_memories(query_embedding: list[float], top_k: int = TOP_K) -> list[dict]:
    """Return the top_k most semantically similar memories via the match_memories RPC."""
    result = _client.rpc("match_memories", {
        "query_embedding": query_embedding,
        "match_count": top_k,
    }).execute()
    return result.data or []


def get_state(key: str) -> str | None:
    """Read a small persisted value (e.g. the last processed Telegram
    update_id) — needed because GitHub Actions runs are stateless between
    jobs, so this state has to live somewhere external."""
    result = _client.table("bot_state").select("value").eq("key", key).execute()
    if result.data:
        return result.data[0]["value"]
    return None


def set_state(key: str, value: str) -> None:
    _client.table("bot_state").upsert({"key": key, "value": value}).execute()
