"""ExtractorRegistry maps MIME type + extension to extractor instances."""

from __future__ import annotations

from employee_help.casefile.extractors.base import FileExtractor


class ExtractorRegistry:
    """Resolves MIME type + extension to the appropriate FileExtractor.

    New formats are added by implementing FileExtractor and calling
    ``register()`` — zero changes to existing code (OCP).
    """

    def __init__(self) -> None:
        self._extractors: list[FileExtractor] = []

    def register(self, extractor: FileExtractor) -> None:
        """Register an extractor instance."""
        self._extractors.append(extractor)

    def get_extractor(self, mime_type: str, extension: str) -> FileExtractor | None:
        """Return the first extractor that can handle the given type, or None."""
        ext = extension.lower().lstrip(".")
        mime = mime_type.lower()
        for extractor in self._extractors:
            if extractor.can_extract(mime, ext):
                return extractor
        return None

    def resolve(self, mime_type: str, extension: str) -> FileExtractor:
        """Return the extractor for the given type, or raise ValueError."""
        extractor = self.get_extractor(mime_type, extension)
        if extractor is None:
            raise ValueError(
                f"No extractor registered for mime_type={mime_type!r}, "
                f"extension={extension!r}"
            )
        return extractor

    @property
    def registered_extensions(self) -> set[str]:
        """Return the union of all supported extensions across registered extractors."""
        result: set[str] = set()
        for extractor in self._extractors:
            result.update(extractor.supported_extensions)
        return result
