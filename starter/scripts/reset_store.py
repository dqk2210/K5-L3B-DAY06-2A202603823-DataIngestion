# -*- coding: utf-8 -*-
"""Drop the old chunks table when the embedding model/dimensions change."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv

load_dotenv()
import psycopg

conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
row = conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
print("pgvector:", row[0])
conn.execute("DROP TABLE IF EXISTS chunks")
print("dropped table chunks (old-dimension vectors invalidated by model change)")
conn.close()
