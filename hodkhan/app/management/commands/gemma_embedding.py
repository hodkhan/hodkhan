# gemma_embedding.py
"""
GemmaEmbedding adapter class to replace FastText with local Gemma model.
Maintains exact same interface as FastText for drop-in replacement.
"""

import os
import torch
import numpy as np
from typing import List, Optional, Union
from transformers import AutoTokenizer, AutoModel
import hashlib
import json


class GemmaEmbedding:
    """
    Drop-in replacement for FastText embeddings using local Gemma model.
    Maintains the same interface for backward compatibility.
    """
    
    _instance = None  # Singleton instance for lazy loading
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern to avoid multiple model loads."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self, 
        model_path: str = "./EmbeddingGemma",
        device: str = "auto",
        normalize: bool = True,
        batch_size: int = 32,
        cache_embeddings: bool = True,
        seed: int = 42
    ):
        """
        Initialize Gemma embedding model.
        
        Args:
            model_path: Path to local Gemma model directory
            device: Device to use ('cuda', 'cpu', or 'auto')
            normalize: Whether to normalize embeddings (L2 norm)
            batch_size: Batch size for processing multiple texts
            cache_embeddings: Whether to cache computed embeddings
            seed: Random seed for reproducibility
        """
        # Skip initialization if already initialized
        if hasattr(self, '_initialized'):
            return
            
        self.model_path = model_path
        self.batch_size = batch_size
        self.normalize = normalize
        self.cache_embeddings = cache_embeddings
        self.seed = seed
        
        # Set seeds for reproducibility
        torch.manual_seed(seed)
        np.random.seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
        
        # Device selection
        if device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        
        # Load tokenizer and model
        self._load_model()
        
        # Cache for embeddings (optional)
        self._embedding_cache = {} if cache_embeddings else None
        self._initialized = True
    
    def _load_model(self):
        """Load the Gemma model and tokenizer from local path."""
        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                local_files_only=True,
                trust_remote_code=True
            )
            
            # Load model
            self.model = AutoModel.from_pretrained(
                self.model_path,
                local_files_only=True,
                trust_remote_code=True,
                torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32
            ).to(self.device)
            
            # Set model to eval mode
            self.model.eval()
            
            # Get embedding dimension
            with torch.no_grad():
                dummy_input = self.tokenizer("test", return_tensors="pt", truncation=True)
                dummy_input = {k: v.to(self.device) for k, v in dummy_input.items()}
                dummy_output = self.model(**dummy_input)
                # Use pooled output or mean of last hidden state
                if hasattr(dummy_output, 'pooler_output') and dummy_output.pooler_output is not None:
                    self.embedding_dim = dummy_output.pooler_output.shape[-1]
                else:
                    self.embedding_dim = dummy_output.last_hidden_state.shape[-1]
                    
        except Exception as e:
            raise RuntimeError(f"Failed to load Gemma model from {self.model_path}: {e}")
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"gemma_embed_{self.seed}_{text_hash}"
    
    def _mean_pooling(self, model_output, attention_mask):
        """Mean pooling - take attention mask into account for correct averaging."""
        token_embeddings = model_output.last_hidden_state
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    
    @torch.no_grad()
    def _compute_embedding(self, text: str) -> np.ndarray:
        """
        Compute embedding for a single text.
        Internal method that does the actual computation.
        """
        # Tokenize
        inputs = self.tokenizer(
            text,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        )
        
        # Move to device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Get model output
        outputs = self.model(**inputs)
        
        # Get embeddings - use pooler output if available, otherwise mean pooling
        if hasattr(outputs, 'pooler_output') and outputs.pooler_output is not None:
            embeddings = outputs.pooler_output
        else:
            embeddings = self._mean_pooling(outputs, inputs['attention_mask'])
        
        # Normalize if requested
        if self.normalize:
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        
        # Convert to numpy
        embedding = embeddings.cpu().numpy().squeeze()
        
        return embedding
    
    @torch.no_grad()
    def _compute_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """
        Compute embeddings for multiple texts in batches.
        """
        all_embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            
            # Tokenize batch
            inputs = self.tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt"
            )
            
            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Get model outputs
            outputs = self.model(**inputs)
            
            # Get embeddings
            if hasattr(outputs, 'pooler_output') and outputs.pooler_output is not None:
                embeddings = outputs.pooler_output
            else:
                embeddings = self._mean_pooling(outputs, inputs['attention_mask'])
            
            # Normalize if requested
            if self.normalize:
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            
            # Convert to numpy and append
            batch_embeddings = embeddings.cpu().numpy()
            all_embeddings.append(batch_embeddings)
        
        # Concatenate all batches
        return np.vstack(all_embeddings)
    
    def get_embedding(self, text: str) -> np.ndarray:
        """
        Get embedding for a single text.
        Maintains FastText interface: get_sentence_vector(text) -> ndarray
        
        Args:
            text: Input text string
            
        Returns:
            numpy array of embeddings
        """
        if not text or not text.strip():
            # Return zero vector for empty text (consistent with FastText behavior)
            return np.zeros(self.embedding_dim, dtype=np.float32)
        
        # Check cache
        if self._embedding_cache is not None:
            cache_key = self._get_cache_key(text)
            if cache_key in self._embedding_cache:
                return self._embedding_cache[cache_key].copy()
        
        # Compute embedding
        embedding = self._compute_embedding(text)
        
        # Cache if enabled
        if self._embedding_cache is not None:
            cache_key = self._get_cache_key(text)
            self._embedding_cache[cache_key] = embedding.copy()
        
        return embedding
    
    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Get embeddings for multiple texts.
        
        Args:
            texts: List of input text strings
            
        Returns:
            numpy array of shape (n_texts, embedding_dim)
        """
        if not texts:
            return np.array([], dtype=np.float32).reshape(0, self.embedding_dim)
        
        # Check which texts need computation
        texts_to_compute = []
        indices_to_compute = []
        results = np.zeros((len(texts), self.embedding_dim), dtype=np.float32)
        
        for i, text in enumerate(texts):
            if not text or not text.strip():
                # Zero vector for empty text
                results[i] = np.zeros(self.embedding_dim, dtype=np.float32)
            elif self._embedding_cache is not None:
                cache_key = self._get_cache_key(text)
                if cache_key in self._embedding_cache:
                    results[i] = self._embedding_cache[cache_key].copy()
                else:
                    texts_to_compute.append(text)
                    indices_to_compute.append(i)
            else:
                texts_to_compute.append(text)
                indices_to_compute.append(i)
        
        # Compute missing embeddings
        if texts_to_compute:
            computed_embeddings = self._compute_embeddings_batch(texts_to_compute)
            
            # Fill results and cache
            for idx, text, embedding in zip(indices_to_compute, texts_to_compute, computed_embeddings):
                results[idx] = embedding
                if self._embedding_cache is not None:
                    cache_key = self._get_cache_key(text)
                    self._embedding_cache[cache_key] = embedding.copy()
        
        return results
    
    # FastText compatibility method
    def get_sentence_vector(self, text: str) -> np.ndarray:
        """
        FastText-compatible method name.
        Alias for get_embedding to maintain backward compatibility.
        """
        return self.get_embedding(text)
    
    def get_word_vector(self, word: str) -> np.ndarray:
        """
        FastText-compatible method for word vectors.
        Since Gemma is a sentence encoder, we return the embedding of the single word.
        """
        return self.get_embedding(word)
    
    def clear_cache(self):
        """Clear the embedding cache."""
        if self._embedding_cache is not None:
            self._embedding_cache.clear()
    
    @property
    def vector_size(self) -> int:
        """FastText-compatible property for vector dimension."""
        return self.embedding_dim


# Factory function for FastText compatibility
def load_model(model_path: str = "./EmbeddingGemma", **kwargs) -> GemmaEmbedding:
    """
    FastText-compatible factory function.
    Usage: model = load_model("app.management.commands../EmbeddingGemma")
    """
    return GemmaEmbedding(model_path=model_path, **kwargs)