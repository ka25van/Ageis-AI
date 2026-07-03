import os
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Repository, RepositoryFile
from app.core.di import get_db_session
from app.services.repository_intelligence import RepositoryIntelligence
from app.db.session import async_session_maker
from app.services.embeddings import EmbeddingService


class RepositoryIngestionService:
    """Service for cloning repositories and extracting file metadata."""

    # Language detection by file extension
    LANGUAGE_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".java": "java",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".r": "r",
        ".m": "objective-c",
        ".mm": "objective-c++",
        ".sh": "shell",
        ".bash": "shell",
        ".zsh": "shell",
        ".ps1": "powershell",
        ".sql": "sql",
        ".html": "html",
        ".htm": "html",
        ".css": "css",
        ".scss": "scss",
        ".sass": "sass",
        ".less": "less",
        ".json": "json",
        ".xml": "xml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
        ".conf": "ini",
        ".md": "markdown",
        ".markdown": "markdown",
        ".txt": "text",
        ".rst": "restructuredtext",
        ".dockerfile": "dockerfile",
        ".dockerignore": "dockerfile",
        ".gitignore": "gitignore",
        ".env": "dotenv",
    }

    # Files/folders to ignore
    IGNORE_PATTERNS = {
        ".git",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "target",
        ".gradle",
        "venv",
        ".venv",
        "env",
        ".env",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".DS_Store",
        "Thumbs.db",
        "*.log",
        "*.lock",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Cargo.lock",
        "go.sum",
        "composer.lock",
        "poetry.lock",
        "Pipfile.lock",
        "*.min.js",
        "*.min.css",
        "vendor",
        ".idea",
        ".vscode",
        "*.swp",
        "*.swo",
        "*~",
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    def detect_language(self, file_path: str) -> Optional[str]:
        """Detect programming language from file extension."""
        suffix = Path(file_path).suffix.lower()
        return self.LANGUAGE_MAP.get(suffix)

    def should_ignore(self, path: str) -> bool:
        """Check if path should be ignored."""
        path_parts = Path(path).parts
        for part in path_parts:
            if part in self.IGNORE_PATTERNS:
                return True
            # Check glob patterns
            for pattern in self.IGNORE_PATTERNS:
                if "*" in pattern:
                    import fnmatch
                    if fnmatch.fnmatch(part, pattern):
                        return True
        return False

    async def clone_repository(
        self,
        repo_url: str,
        branch: str = "main",
        access_token: Optional[str] = None,
    ) -> str:
        """Clone a git repository to a temporary directory."""
        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix="aegis_repo_")

        # Prepare clone URL with token if provided
        clone_url = repo_url
        if access_token and "github.com" in repo_url:
            clone_url = repo_url.replace("https://", f"https://{access_token}@")

        try:
            # Clone repository
            cmd = ["git", "clone", "--depth", "1", "--branch", branch, clone_url, temp_dir]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                # Try default branch if specific branch fails
                if branch != "main":
                    cmd = ["git", "clone", "--depth", "1", clone_url, temp_dir]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise Exception(f"Git clone failed: {result.stderr}")

            return temp_dir

        except subprocess.TimeoutExpired:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise Exception("Git clone timed out")
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def is_binary_file(self, file_path: str) -> bool:
        """Check if file is binary by reading first 8KB."""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    return True
                # Check for high ratio of non-text bytes
                text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x7f)))
                if chunk:
                    non_text = sum(1 for b in chunk if b not in text_chars)
                    if non_text / len(chunk) > 0.3:
                        return True
        except Exception:
            return True
        return False

    def extract_file_metadata(self, repo_path: str, file_path: str) -> Dict:
        """Extract metadata from a single file."""
        full_path = os.path.join(repo_path, file_path)
        stat = os.stat(full_path)

        # Skip binary files - don't read content
        if self.is_binary_file(full_path):
            language = self.detect_language(file_path)
            import hashlib
            content_hash = hashlib.sha256(b"").hexdigest()
            return {
                "path": file_path,
                "language": language,
                "size_bytes": stat.st_size,
                "content_hash": content_hash,
                "content": None,
                "metadata": {
                    "extension": Path(file_path).suffix,
                    "filename": Path(file_path).name,
                    "directory": str(Path(file_path).parent),
                    "is_binary": True,
                },
            }

        # Read file content (limit size)
        content = None
        content_hash = ""
        try:
            if stat.st_size < 1024 * 1024:  # 1MB limit
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    import hashlib
                    content_hash = hashlib.sha256(content.encode()).hexdigest()
        except Exception:
            pass

        language = self.detect_language(file_path)

        return {
            "path": file_path,
            "language": language,
            "size_bytes": stat.st_size,
            "content_hash": content_hash,
            "content": content,
            "metadata": {
                "extension": Path(file_path).suffix,
                "filename": Path(file_path).name,
                "directory": str(Path(file_path).parent),
                "is_binary": False,
            },
        }

    def scan_repository(self, repo_path: str) -> List[Dict]:
        """Scan repository and return file metadata list."""
        files = []

        for root, dirs, filenames in os.walk(repo_path):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if not self.should_ignore(os.path.join(root, d))]

            for filename in filenames:
                rel_root = os.path.relpath(root, repo_path)
                if rel_root == ".":
                    file_path = filename
                else:
                    file_path = os.path.join(rel_root, filename)

                if self.should_ignore(file_path):
                    continue

                try:
                    metadata = self.extract_file_metadata(repo_path, file_path)
                    files.append(metadata)
                except Exception as e:
                    logger.warning(f"Error processing {file_path}: {e}")
                    continue

        return files

    async def save_repository_files(
        self,
        repository_id: UUID,
        files: List[Dict],
    ) -> int:
        """Save repository files to database."""
        saved_count = 0

        for file_data in files:
            repo_file = RepositoryFile(
                repository_id=repository_id,
                path=file_data["path"],
                language=file_data.get("language"),
                size_bytes=file_data.get("size_bytes", 0),
                content_hash=file_data.get("content_hash", ""),
                content=file_data.get("content"),
                metadata=file_data.get("metadata", {}),
            )
            self.db.add(repo_file)
            saved_count += 1

        await self.db.commit()
        return saved_count

    async def update_repository_indexing_status(
        self,
        repository_id: UUID,
        status: str,
        error: Optional[str] = None,
    ):
        """Update repository indexing status."""
        result = await self.db.execute(
            select(Repository).where(Repository.id == repository_id)
        )
        repo = result.scalar_one_or_none()
        if repo:
            repo.indexing_status = status
            repo.indexing_error = error
            if status == "completed":
                repo.last_indexed_at = datetime.utcnow()
            await self.db.commit()

    async def ingest_repository(
        self,
        repository_id: UUID,
        repo_url: str,
        branch: str = "main",
        access_token: Optional[str] = None,
    ) -> Dict:
        """Full repository ingestion pipeline with its own DB session."""
        async with async_session_maker() as session:
            # Create a new service instance with the background session
            bg_service = RepositoryIngestionService(session)

            # Update status
            await bg_service.update_repository_indexing_status(repository_id, "in_progress")

            temp_dir = None
            try:
                # Clone
                temp_dir = await bg_service.clone_repository(repo_url, branch, access_token)

                # Scan
                files = bg_service.scan_repository(temp_dir)

                # Save
                saved = await bg_service.save_repository_files(repository_id, files)

                # Update status
                await bg_service.update_repository_indexing_status(repository_id, "completed")

                # Generate embeddings (creates Document + DocumentChunk records)
                try:
                    emb_service = EmbeddingService(session)
                    embed_result = await emb_service.embed_and_store_repository_files(repository_id)
                    await session.commit()
                except Exception as e:
                    logger.warning(f"Embedding generation failed (non-fatal): {e}")

                # Invalidate RepositoryIntelligence cache so next agent call gets fresh data
                RepositoryIntelligence.invalidate(repository_id)

                return {
                    "status": "completed",
                    "files_processed": saved,
                    "languages": list(set(f["language"] for f in files if f["language"])),
                }

            except Exception as e:
                await bg_service.update_repository_indexing_status(repository_id, "failed", str(e))
                raise
            finally:
                if temp_dir:
                    shutil.rmtree(temp_dir, ignore_errors=True)


async def get_ingestion_service(db: AsyncSession = Depends(get_db_session)) -> RepositoryIngestionService:
    return RepositoryIngestionService(db)