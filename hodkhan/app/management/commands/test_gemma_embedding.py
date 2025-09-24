# test_gemma_embedding.py
"""
Unit tests for GemmaEmbedding adapter to verify API compatibility
and deterministic behavior.
"""

import unittest
import numpy as np
from app.management.commands.gemma_embedding import GemmaEmbedding, load_model


class TestGemmaEmbedding(unittest.TestCase):
    """Test suite for GemmaEmbedding adapter."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        cls.model = GemmaEmbedding(
            model_path="./EmbeddingGemma",
            device="cpu",  # Use CPU for testing
            seed=42
        )
        cls.test_texts = [
            "This is a test sentence.",
            "Another example text for testing.",
            "Machine learning is fascinating.",
        ]
    
    def test_api_compatibility(self):
        """Test that all FastText-compatible methods exist."""
        # Check methods exist
        self.assertTrue(hasattr(self.model, 'get_sentence_vector'))
        self.assertTrue(hasattr(self.model, 'get_word_vector'))
        self.assertTrue(hasattr(self.model, 'vector_size'))
        
        # Check new methods
        self.assertTrue(hasattr(self.model, 'get_embedding'))
        self.assertTrue(hasattr(self.model, 'get_embeddings'))
    
    def test_single_embedding(self):
        """Test single text embedding generation."""
        text = "Test sentence for embedding"
        
        # Test get_embedding
        embedding1 = self.model.get_embedding(text)
        self.assertIsInstance(embedding1, np.ndarray)
        self.assertEqual(embedding1.ndim, 1)
        self.assertEqual(embedding1.shape[0], self.model.embedding_dim)
        
        # Test FastText-compatible method
        embedding2 = self.model.get_sentence_vector(text)
        np.testing.assert_array_equal(embedding1, embedding2)
    
    def test_batch_embedding(self):
        """Test batch embedding generation."""
        embeddings = self.model.get_embeddings(self.test_texts)
        
        self.assertIsInstance(embeddings, np.ndarray)
        self.assertEqual(embeddings.shape[0], len(self.test_texts))
        self.assertEqual(embeddings.shape[1], self.model.embedding_dim)
        
        # Verify batch and single produce same results
        for i, text in enumerate(self.test_texts):
            single_embedding = self.model.get_embedding(text)
            np.testing.assert_allclose(
                embeddings[i], single_embedding, 
                rtol=1e-5, atol=1e-6
            )
    
    def test_deterministic_output(self):
        """Test that same input produces same output (deterministic)."""
        text = "Deterministic test"
        
        # Generate embedding multiple times
        embeddings = [self.model.get_embedding(text) for _ in range(3)]
        
        # All should be identical
        for i in range(1, len(embeddings)):
            np.testing.assert_array_equal(embeddings[0], embeddings[i])
    
    def test_empty_text_handling(self):
        """Test handling of empty or whitespace text."""
        empty_texts = ["", " ", "\n", "\t"]
        
        for text in empty_texts:
            embedding = self.model.get_embedding(text)
            self.assertIsInstance(embedding, np.ndarray)
            self.assertEqual(embedding.shape[0], self.model.embedding_dim)
            # Should return zero vector for empty text
            np.testing.assert_array_equal(
                embedding, 
                np.zeros(self.model.embedding_dim, dtype=np.float32)
            )
    
    def test_normalization(self):
        """Test that embeddings are normalized when normalize=True."""
        text = "Normalization test"
        embedding = self.model.get_embedding(text)
        
        # Check L2 norm is approximately 1
        norm = np.linalg.norm(embedding)
        self.assertAlmostEqual(norm, 1.0, places=5)
    
    def test_cache_functionality(self):
        """Test that caching works correctly."""
        text = "Cache test"
        
        # Clear cache first
        self.model.clear_cache()
        
        # First call should compute
        embedding1 = self.model.get_embedding(text)
        
        # Second call should use cache (result should be identical)
        embedding2 = self.model.get_embedding(text)
        np.testing.assert_array_equal(embedding1, embedding2)
    
    def test_factory_function(self):
        """Test FastText-compatible factory function."""
        model = load_model("./EmbeddingGemma", device="cpu", seed=42)
        self.assertIsInstance(model, GemmaEmbedding)
        
        # Test it works
        embedding = model.get_sentence_vector("Test")
        self.assertIsInstance(embedding, np.ndarray)
    
    def test_vector_size_property(self):
        """Test vector_size property for FastText compatibility."""
        vector_size = self.model.vector_size
        self.assertIsInstance(vector_size, int)
        self.assertGreater(vector_size, 0)
        self.assertEqual(vector_size, self.model.embedding_dim)
    
    def test_singleton_pattern(self):
        """Test that singleton pattern prevents multiple model loads."""
        model1 = GemmaEmbedding(model_path="./EmbeddingGemma")
        model2 = GemmaEmbedding(model_path="./EmbeddingGemma")
        self.assertIs(model1, model2)


if __name__ == '__main__':
    unittest.main()