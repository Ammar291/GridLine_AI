from sqlalchemy import text


async def test_schema_has_documents_and_chunks(db_engine):
    async with db_engine.connect() as conn:
        rows = await conn.execute(
            text("select table_name from information_schema.tables where table_schema = 'public' order by 1")
        )
        names = {r[0] for r in rows}
    assert {"documents", "chunks"} <= names


async def test_chunks_have_vector_column_and_hnsw_index(db_engine):
    async with db_engine.connect() as conn:
        col = await conn.execute(
            text(
                "select udt_name from information_schema.columns "
                "where table_name='chunks' and column_name='embedding'"
            )
        )
        assert col.scalar_one() == "vector"
        idx = await conn.execute(text("select indexdef from pg_indexes where tablename = 'chunks'"))
        defs = " ".join(r[0] for r in idx)
    assert "hnsw" in defs and "vector_cosine_ops" in defs
