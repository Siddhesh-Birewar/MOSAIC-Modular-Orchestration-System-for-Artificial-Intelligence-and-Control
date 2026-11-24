"""Read-only filesystem tools with configured-root and descriptor checks."""

import os
from pathlib import Path
import stat
from datetime import datetime, timezone

from app.security.permissions import PermissionRequirement
from app.tools.base import RiskLevel, Tool, ToolContext
from app.tools.schemas import ObjectOutput, PathInput, SearchInput


SENSITIVE_NAMES = {
    ".ssh", ".aws", ".gnupg", ".azure", ".kube", ".docker", ".config", "keychains",
    "login data", "cookies", "credentials", "credentials.json", ".git-credentials",
    ".authinfo", ".password-store", ".netrc", ".npmrc", ".pypirc", "secrets", "secret", "tokens", "token",
}


def is_sensitive_component(name: str) -> bool:
    lowered = name.casefold()
    return (
        lowered in SENSITIVE_NAMES
        or lowered.startswith(".env")
        or lowered.startswith("id_")
        or "credential" in lowered
        or "secret" in lowered
        or "private_key" in lowered
        or lowered.endswith((".pem", ".key", ".p8", ".p12", ".pfx", ".mobileprovision", ".token"))
    )


class FileAccess:
    def __init__(self, configured_roots: tuple[str, ...], max_file_bytes: int = 256_000) -> None:
        roots: list[Path] = []
        identities: dict[Path, tuple[int, int]] = {}
        for raw in configured_roots:
            try:
                root = Path(raw).expanduser().resolve(strict=True)
                info = root.stat()
                if root.is_dir() and not root.is_symlink():
                    roots.append(root)
                    identities[root] = (info.st_dev, info.st_ino)
            except OSError:
                continue
        self.roots = tuple(roots)
        self._identities = identities
        self.max_file_bytes = max_file_bytes

    def authorized_root_for_path(self, value: str) -> Path | None:
        try:
            raw = Path(value).expanduser()
            if not raw.is_absolute() or ".." in raw.parts:
                return None
            canonical = raw.resolve(strict=False)
            for root in self.roots:
                try:
                    canonical.relative_to(root)
                    raw.relative_to(root)
                    if any(is_sensitive_component(part) for part in raw.parts):
                        return None
                    return root
                except ValueError:
                    continue
        except (OSError, RuntimeError):
            return None
        return None

    def _open(self, value: str) -> tuple[int, Path]:
        root = self.authorized_root_for_path(value)
        if root is None:
            raise PermissionError("Path is outside authorized roots or is sensitive")
        raw = Path(value).expanduser()
        relative = raw.relative_to(root)
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        root_fd = os.open(root, flags | getattr(os, "O_DIRECTORY", 0))
        info = os.fstat(root_fd)
        if (info.st_dev, info.st_ino) != self._identities[root]:
            os.close(root_fd)
            raise PermissionError("Authorized root changed")
        current_fd = root_fd
        try:
            for index, part in enumerate(relative.parts):
                if part in ("", ".", "..") or is_sensitive_component(part):
                    raise PermissionError("Path component is not allowed")
                last = index == len(relative.parts) - 1
                next_flags = flags
                if not last:
                    next_flags |= getattr(os, "O_DIRECTORY", 0)
                else:
                    next_flags |= getattr(os, "O_NONBLOCK", 0)
                next_fd = os.open(part, next_flags, dir_fd=current_fd)
                if current_fd != root_fd:
                    os.close(current_fd)
                current_fd = next_fd
            if current_fd != root_fd:
                os.close(root_fd)
            return current_fd, root
        except BaseException:
            if current_fd != root_fd:
                os.close(current_fd)
            os.close(root_fd)
            raise

    def list_directory(self, path: str) -> list[dict]:
        fd, _ = self._open(path)
        try:
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError("Path is not a directory")
            names: list[str] = []
            with os.scandir(fd) as children:
                for child in children:
                    if len(names) >= 2000:
                        break
                    names.append(child.name)
            entries = []
            for name in sorted(names, key=str.casefold):
                if is_sensitive_component(name):
                    continue
                try:
                    item = os.stat(name, dir_fd=fd, follow_symlinks=False)
                except OSError:
                    continue
                kind = "directory" if stat.S_ISDIR(item.st_mode) else "file" if stat.S_ISREG(item.st_mode) else "other"
                entries.append({"name": name, "kind": kind})
            return entries[:200]
        finally:
            os.close(fd)

    def read_text(self, path: str) -> dict:
        fd, _ = self._open(path)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Only regular files can be read")
            if info.st_size > self.max_file_bytes:
                raise ValueError("File exceeds the configured size limit")
            chunks = bytearray()
            while len(chunks) <= self.max_file_bytes:
                part = os.read(fd, min(64_000, self.max_file_bytes + 1 - len(chunks)))
                if not part:
                    break
                chunks.extend(part)
            if len(chunks) > self.max_file_bytes:
                raise ValueError("File exceeds the configured size limit")
            return {"name": Path(path).name, "content": chunks.decode("utf-8", errors="strict")}
        finally:
            os.close(fd)

    def metadata(self, path: str) -> dict:
        fd, _ = self._open(path)
        try:
            info = os.fstat(fd)
            if stat.S_ISREG(info.st_mode):
                kind = "file"
            elif stat.S_ISDIR(info.st_mode):
                kind = "directory"
            else:
                raise ValueError("Special files are not supported")
            return {
                "name": Path(path).name,
                "kind": kind,
                "size_bytes": info.st_size,
                "modified_at": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(),
            }
        finally:
            os.close(fd)

    def search(self, root_path: str, query: str, limit: int) -> list[str]:
        root_fd, root = self._open(root_path)
        try:
            if not stat.S_ISDIR(os.fstat(root_fd).st_mode):
                raise ValueError("Search root is not a directory")
            found: list[str] = []
            visited = 0

            def walk(directory_fd: int, relative: Path, depth: int) -> None:
                nonlocal visited
                if depth > 12 or visited >= 2000 or len(found) >= limit:
                    return
                with os.scandir(directory_fd) as children:
                    for child in children:
                        if len(found) >= limit or visited >= 2000:
                            return
                        name = child.name
                        visited += 1
                        if is_sensitive_component(name):
                            continue
                        child_relative = relative / name
                        try:
                            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                        except OSError:
                            continue
                        if query.casefold() in name.casefold():
                            found.append(str(root / child_relative))
                        if stat.S_ISDIR(info.st_mode):
                            try:
                                child_fd = os.open(
                                    name,
                                    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                                    dir_fd=directory_fd,
                                )
                            except OSError:
                                continue
                            try:
                                walk(child_fd, child_relative, depth + 1)
                            finally:
                                os.close(child_fd)

            walk(root_fd, Path(), 0)
            return found
        finally:
            os.close(root_fd)


READ_PERMISSION = (PermissionRequirement("filesystem", "read"),)


class ListDirectoryTool(Tool):
    tool_id = "filesystem_list_directory"
    description = "List names and basic file types in an explicitly authorized directory."
    input_model = PathInput
    output_model = ObjectOutput
    risk = RiskLevel.LOW
    required_permissions = READ_PERMISSION
    timeout_seconds = 4

    async def execute(self, arguments, context: ToolContext) -> ObjectOutput:
        return ObjectOutput(result={"entries": context.services["file_access"].list_directory(arguments.path)})


class SearchFilesTool(Tool):
    tool_id = "filesystem_search_filenames"
    description = "Search filenames under an explicitly authorized directory; file contents are not searched."
    input_model = SearchInput
    output_model = ObjectOutput
    risk = RiskLevel.LOW
    required_permissions = READ_PERMISSION
    timeout_seconds = 8

    async def execute(self, arguments, context: ToolContext) -> ObjectOutput:
        results = context.services["file_access"].search(arguments.root, arguments.query, arguments.limit)
        return ObjectOutput(result={"matches": results})


class ReadTextFileTool(Tool):
    tool_id = "filesystem_read_text_file"
    description = "Read a small UTF-8 text file from an explicitly authorized directory."
    input_model = PathInput
    output_model = ObjectOutput
    risk = RiskLevel.MEDIUM
    required_permissions = READ_PERMISSION
    timeout_seconds = 4

    async def execute(self, arguments, context: ToolContext) -> ObjectOutput:
        return ObjectOutput(result=context.services["file_access"].read_text(arguments.path))


class FileMetadataTool(Tool):
    tool_id = "filesystem_file_metadata"
    description = "Read basic metadata for a regular file or directory in an authorized root."
    input_model = PathInput
    output_model = ObjectOutput
    risk = RiskLevel.LOW
    required_permissions = READ_PERMISSION
    timeout_seconds = 4

    async def execute(self, arguments, context: ToolContext) -> ObjectOutput:
        return ObjectOutput(result=context.services["file_access"].metadata(arguments.path))
