import sqlite3
import json
import os
from sentence_transformers import SentenceTransformer
from django.conf import settings


class VectorSearchManager:
    def __init__(self):
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self.sqlite_vec_available = self._check_sqlite_vec_availability()

    def _check_sqlite_vec_availability(self):
        """Check if sqlite-vec extension is available"""
        try:
            conn = sqlite3.connect(':memory:')
            conn.enable_load_extension(True)

            # Try different possible names for the extension
            extension_names = ['vec0', 'sqlite_vec', 'vec']
            for ext_name in extension_names:
                try:
                    conn.load_extension(ext_name)
                    conn.close()
                    return True
                except Exception as ex_in:
                    print("Failed to load extension: ", ext_name)
                    print(ex_in)
                    continue

            conn.close()
            return False
        except Exception as ex_out:
            print("Failed here with following error: ")
            print(ex_out)
            return False

    def get_embedding(self, text):
        """Generate embedding for given text"""
        embedding = self.model.encode(text)
        return embedding.tolist()

    def similarity_search(self, source_type, query_text, limit=25):
        """Perform similarity search using sqlite-vec or fallback"""
        db_path = settings.VECTOR_DATABASES[source_type]

        if not os.path.exists(db_path):
            return []

        # Generate embedding for query text
        query_embedding = self.get_embedding(query_text)

        if self.sqlite_vec_available:
            return self._sqlite_vec_search(db_path, query_embedding, limit)
        else:
            return self._fallback_similarity_search(db_path, query_embedding, limit)

    def _sqlite_vec_search(self, db_path, query_embedding, limit):
        """Perform search using sqlite-vec extension"""
        conn = sqlite3.connect(db_path)

        try:
            print("\n Printing before loading sqlite-vec extension ===================== ")
            conn.enable_load_extension(True)
            conn.load_extension("vec0")
            print("\n Printing after loading sqlite-vec extension ===================== \n ")
            cursor = conn.cursor()

            # Perform vector similarity search using sqlite-vec
            query = """
            SELECT 
                s.id,
                s.source_text,
                s.category,
                s.created_date,
                s.author,
                e.metadata,
                vec_distance_cosine(e.embedding_vect, ?) as distance
            FROM source_tbl s
            JOIN embedding_tbl e ON s.id = e.source_id
            ORDER BY distance ASC
            LIMIT ?
            """

            cursor.execute(query, (json.dumps(query_embedding), limit))
            results = cursor.fetchall()

            formatted_results = []
            for row in results:
                formatted_results.append({
                    'id': row[0],
                    'source_text': row[1],
                    'category': row[2],
                    'created_date': row[3],
                    'author': row[4],
                    'metadata': json.loads(row[5]) if row[5] else {},
                    'distance': row[6]
                })

            conn.close()
            return formatted_results

        except Exception as ex:
            print("Printing value of ex: ")
            print(ex)
            print("\n Printing failed to load sqlite-vec extension ===================== \n ")
            conn.close()
            # Fall back to manual calculation if sqlite-vec fails
            return self._fallback_similarity_search(db_path, query_embedding, limit)

    def _fallback_similarity_search(self, db_path, query_embedding, limit):
        """Fallback similarity search without sqlite-vec"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all embeddings
        cursor.execute("""
            SELECT 
                s.id,
                s.source_text,
                s.category,
                s.created_date,
                s.author,
                e.embedding_vect,
                e.metadata
            FROM source_tbl s
            JOIN embedding_tbl e ON s.id = e.source_id
        """)

        results = cursor.fetchall()
        conn.close()

        # Calculate cosine similarity manually
        similarities = []
        for row in results:
            try:
                stored_embedding = json.loads(row[5])
                similarity = self._cosine_similarity(query_embedding, stored_embedding)
                similarities.append({
                    'id': row[0],
                    'source_text': row[1],
                    'category': row[2],
                    'created_date': row[3],
                    'author': row[4],
                    'metadata': json.loads(row[6]) if row[6] else {},
                    'distance': 1 - similarity  # Convert similarity to distance
                })
            except (json.JSONDecodeError, TypeError) as e:
                # Skip invalid embeddings
                continue

        # Sort by distance and return top results
        similarities.sort(key=lambda x: x['distance'])
        return similarities[:limit]

    def _cosine_similarity(self, vec1, vec2):
        """Calculate cosine similarity between two vectors"""
        import math

        if len(vec1) != len(vec2):
            return 0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0

        return dot_product / (magnitude1 * magnitude2)