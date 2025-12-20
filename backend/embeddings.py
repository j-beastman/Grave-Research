
from typing import List
from fastembed import TextEmbedding

class EmbeddingService:
    _instance = None
    _model = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # lazy loading to avoid import cost at startup if not used
        pass

    @property
    def model(self):
        if self._model is None:
            # "BAAI/bge-small-en-v1.5" is also good, but "sentence-transformers/all-MiniLM-L6-v2" is default and fast.
            # FastEmbed defaults to "BAAI/bge-small-en-v1.5" which is 384 dim.
            self._model = TextEmbedding()
        return self._model

    def generate(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            return []
        
        # fastembed returns a generator
        embeddings = list(self.model.embed(texts))
        return [e.tolist() for e in embeddings]

    def generate_one(self, text: str) -> List[float]:
        if not text:
            return []
        return self.generate([text])[0]
