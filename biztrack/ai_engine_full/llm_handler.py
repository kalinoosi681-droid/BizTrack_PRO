"""
Handles communication with local Large Language Models (LLMs).

This module provides a standardized interface for interacting with different
local LLM backends. It uses llama-cpp-python for maximum portability,
allowing the AI engine to run without requiring an Ollama server.

Key Components:
- LlamaCPPHandler: CPU-based handler using llama-cpp-python
- get_llm_handler: Factory function that returns the best available handler
"""
import logging
import os
import hashlib

class Config:
    """
    Centralized configuration for LLM handlers.
    Sources settings from environment variables with sensible defaults.
    """
    # Default to the `models` directory
    LLAMA_CPP_MODEL_PATH = os.getenv("LLAMA_CPP_MODEL_PATH", "models")
    LLAMA_CPP_N_CTX = int(os.getenv("LLAMA_CPP_N_CTX", "4096"))
    LLAMA_CPP_N_GPU_LAYERS = int(os.getenv("LLAMA_CPP_N_GPU_LAYERS", "0"))

logger = logging.getLogger(__name__)


class LlamaCPPHandler:
    """
    LLM handler using the `llama-cpp-python` library.
    Optimized for CPU inference on Windows.
    """
    
    def __init__(self):
        """Initialize with model path detection"""
        configured = Config.LLAMA_CPP_MODEL_PATH
        self.model_path = configured
        self.llm = None
        self._model_loaded = False
        self._load_error = None

        # Auto-detect .gguf file in directory
        try:
            expanded_path = os.path.expanduser(os.path.expandvars(configured))
            if os.path.isdir(expanded_path):
                files = [f for f in os.listdir(expanded_path) if f.lower().endswith('.gguf')]
                if files:
                    files.sort()
                    self.model_path = os.path.join(expanded_path, files[0])
                    logger.info(f"✅ Auto-detected model: {files[0]}")
            elif os.path.isfile(expanded_path):
                self.model_path = expanded_path
                logger.info(f"✅ Using configured model: {os.path.basename(expanded_path)}")
        except Exception as e:
            logger.warning(f"Model path detection warning: {e}")
            self.model_path = configured
        
    def initialize(self):
        """Quick validation without loading model yet"""
        try:
            model_path_expanded = os.path.expanduser(os.path.expandvars(self.model_path))

            if not os.path.exists(model_path_expanded):
                logger.error(f"❌ Model file not found: {model_path_expanded}")
                logger.error(f"💡 Please ensure 'Llama-3.2-3B-Instruct-Q4_K_M.gguf' is in the 'models/' folder")
                logger.error(f"📂 Expected location: {os.path.abspath(model_path_expanded)}")
                return False

            file_size_mb = os.path.getsize(model_path_expanded) / (1024 * 1024)
            
            logger.info(f"✅ Model file found: {os.path.basename(model_path_expanded)}")
            logger.info(f"📍 Full path: {model_path_expanded}")
            logger.info(f"📦 File size: {file_size_mb:.1f} MB")
            logger.info(f"💡 Model will load on first use (10-30 seconds)")
            logger.info(f"🧵 CPU threads: {os.cpu_count() or 1}")
            
            return True

        except Exception as e:
            logger.error(f"❌ Model validation error: {e}")
            return False
    
    def _load_model(self):
        """Lazily load the model on first use"""
        if self._model_loaded or self.llm is not None:
            return

        try:
            from llama_cpp import Llama

            model_path_expanded = os.path.expanduser(os.path.expandvars(self.model_path))

            if not os.path.exists(model_path_expanded):
                raise FileNotFoundError(f"Model file not found: {model_path_expanded}")

            logger.info(f"🔄 Loading model (10-30 seconds)...")
            logger.info(f"📂 From: {model_path_expanded}")
            
            self.llm = Llama(
                model_path=model_path_expanded,
                n_ctx=Config.LLAMA_CPP_N_CTX,
                n_threads=os.cpu_count() or 1,
                n_gpu_layers=Config.LLAMA_CPP_N_GPU_LAYERS,
                verbose=False
            )

            logger.info("✅ Model loaded successfully!")
            logger.info(f"💾 Context: {Config.LLAMA_CPP_N_CTX} tokens")
            logger.info(f"🧵 Threads: {os.cpu_count() or 1}")
            logger.info(f"🚀 Ready!")
            
            self._model_loaded = True

        except ImportError:
            logger.error("❌ llama-cpp-python not installed!")
            logger.error("💡 Install: pip install llama-cpp-python")
            raise
            
        except Exception as e:
            msg = str(e)
            
            if 'Shared library' in msg or 'llama.dll' in msg:
                logger.error("❌ Native library not found!")
                logger.error("💡 Reinstall: pip install --upgrade --force-reinstall llama-cpp-python")
            else:
                logger.error(f"❌ Load failed: {e}")
            raise
    
    def generate(self, prompt: str, **kwargs):
        """Generate response (lazy loads model on first call)"""
        if not self._model_loaded:
            logger.info("⏳ First inference - loading model...")
            self._load_model()
        
        if not self.llm:
            yield "Model not loaded. Check logs."
            return

        try:
            stream = kwargs.get('stream', True)
            max_tokens = kwargs.get('max_tokens', 2000)
            temperature = kwargs.get('temperature', 0.7)
            
            response = self.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=0.9,
                top_k=40,
                stream=stream,
                stop=["User:", "Human:", "\n\n\n"]
            )
            
            if stream:
                for chunk in response:
                    yield chunk['choices'][0]['text']
            else:
                yield response['choices'][0]['text']
                
        except Exception as e:
            logger.error(f"Generation error: {e}")
            yield f"Error: {str(e)}"
    
    def _fallback_embedding(self, text: str, dim: int = 128) -> list:
        """Fallback hash-based embedding"""
        digest = hashlib.sha256(text.encode('utf-8')).digest()
        vec = []
        state = digest
        
        while len(vec) < dim:
            for b in state:
                vec.append((b / 255.0) * 2.0 - 1.0)
                if len(vec) >= dim:
                    break
            state = hashlib.sha256(state).digest()
        return vec[:dim]
    
    def embed_text(self, text: str) -> list:
        """Generate embeddings (uses fallback for speed)"""
        return self._fallback_embedding(text, dim=128)


def get_llm_handler():
    """Get LLM handler (llama.cpp only)"""
    logger.info("🔧 Initializing LLM handler...")
    
    expanded_path = os.path.expanduser(os.path.expandvars(Config.LLAMA_CPP_MODEL_PATH))
    
    if os.path.exists(expanded_path) or os.path.isdir(os.path.dirname(expanded_path)):
        cpp_handler = LlamaCPPHandler()
        if cpp_handler.initialize():
            logger.info("✅ LlamaCPP handler ready")
            return cpp_handler
    
    logger.error("❌ No LLM handler available!")
    logger.error("📋 Checklist:")
    logger.error("   1. Create 'models' folder")
    logger.error("   2. Download Llama-3.2-3B-Instruct-Q4_K_M.gguf")
    logger.error("   3. Place in 'models' folder")
    logger.error("   4. pip install llama-cpp-python")
    
    return None

logger.info("📚 LLM Handler loaded")