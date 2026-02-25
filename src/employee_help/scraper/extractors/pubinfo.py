"""PUBINFO database loader for California statutory codes.

Downloads and parses the official PUBINFO MySQL dump from
downloads.leginfo.legislature.ca.gov, which contains all California
statutory codes as tab-delimited .dat files with HTML content in
companion .lob sidecar files.

This is the PRIMARY statutory data source. The web scraper
(statute.py) is retained as a fallback/validation tool.

Reference: The PUBINFO archive contains LAW_SECTION_TBL.dat with
18 columns (tab-delimited, backtick-quoted):
  id, law_code, section_num, op_statues, op_chapter, op_section,
  effective_date, law_section_version_id, division, title, part,
  chapter, article, history, lob_file, active_flg, trans_uid, trans_update
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import structlog
from bs4 import BeautifulSoup

from employee_help.scraper.extractors.statute import (
    BASE_URL,
    HierarchyPath,
    StatuteSection,
    build_citation,
)

logger = structlog.get_logger(__name__)

# Column indices in LAW_SECTION_TBL.dat (0-based)
_COL_ID = 0
_COL_LAW_CODE = 1
_COL_SECTION_NUM = 2
_COL_EFFECTIVE_DATE = 6
_COL_DIVISION = 8
_COL_TITLE = 9
_COL_PART = 10
_COL_CHAPTER = 11
_COL_ARTICLE = 12
_COL_HISTORY = 13
_COL_LOB_FILE = 14
_COL_ACTIVE_FLG = 15

_EXPECTED_COLUMNS = 18

# Regex for subdivision markers
_SUBDIVISION_RE = re.compile(r"^\s*\(([a-z]|\d+|[A-Z])\)")


@dataclass
class PubinfoSection:
    """Raw row from LAW_SECTION_TBL with resolved LOB content."""

    id: str
    law_code: str
    section_num: str
    effective_date: str | None
    division: str | None
    title: str | None
    part: str | None
    chapter: str | None
    article: str | None
    history: str | None
    content_html: str
    active_flg: str  # "Y" or "N"


def _unquote(value: str) -> str | None:
    """Remove backtick quoting and handle NULL literals."""
    stripped = value.strip()
    if stripped == "NULL":
        return None
    if stripped.startswith("`") and stripped.endswith("`"):
        return stripped[1:-1]
    return stripped


def _unquote_required(value: str) -> str:
    """Unquote a value that should never be NULL."""
    result = _unquote(value)
    return result if result is not None else ""


def html_to_text(html: str) -> str:
    """Convert HTML content from .lob files to plain text."""
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text(separator="\n", strip=True)


class PubinfoLoader:
    """Parses the PUBINFO ZIP archive to extract statutory code sections.

    Usage:
        loader = PubinfoLoader(Path("data/pubinfo/pubinfo_2025.zip"))
        sections = loader.parse_law_sections()
        filtered = loader.filter_sections(sections, ["LAB"], ["2."])
        statute_sections = loader.to_statute_sections(filtered)
    """

    def __init__(self, zip_path: Path) -> None:
        self.zip_path = zip_path

    def parse_law_sections(self) -> list[PubinfoSection]:
        """Parse LAW_SECTION_TBL.dat + .lob files from the PUBINFO ZIP.

        Opens the ZIP, reads all .lob files into memory keyed by filename,
        then parses the .dat file line by line, resolving each row's lob_file
        column to the corresponding HTML content.

        Returns:
            List of PubinfoSection objects with resolved HTML content.
        """
        logger.info("parsing_pubinfo_zip", path=str(self.zip_path))

        with zipfile.ZipFile(self.zip_path, "r") as zf:
            # Build index of .lob files (filename → content)
            lob_files: dict[str, str] = {}
            dat_path: str | None = None

            for name in zf.namelist():
                lower = name.lower()
                if lower.endswith(".lob"):
                    # Key by the basename only (lob_file column uses basename)
                    basename = name.rsplit("/", 1)[-1] if "/" in name else name
                    try:
                        lob_files[basename] = zf.read(name).decode("utf-8", errors="replace")
                    except Exception as e:
                        logger.warning("lob_read_error", file=name, error=str(e))
                elif lower.endswith("law_section_tbl.dat"):
                    dat_path = name

            if dat_path is None:
                raise FileNotFoundError(
                    "LAW_SECTION_TBL.dat not found in ZIP archive"
                )

            logger.info(
                "pubinfo_index_built",
                lob_files=len(lob_files),
                dat_file=dat_path,
            )

            # Parse the .dat file
            dat_bytes = zf.read(dat_path)
            dat_text = dat_bytes.decode("utf-8", errors="replace")

        return self._parse_dat(dat_text, lob_files)

    def _parse_dat(
        self, dat_text: str, lob_files: dict[str, str]
    ) -> list[PubinfoSection]:
        """Parse the tab-delimited LAW_SECTION_TBL.dat content."""
        sections: list[PubinfoSection] = []
        lob_miss_count = 0

        for line_num, line in enumerate(dat_text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue

            columns = line.split("\t")
            if len(columns) < _EXPECTED_COLUMNS:
                logger.debug(
                    "skipping_short_row",
                    line_num=line_num,
                    columns=len(columns),
                )
                continue

            # Resolve the .lob file reference
            lob_filename = _unquote(columns[_COL_LOB_FILE])
            content_html = ""
            if lob_filename:
                content_html = lob_files.get(lob_filename, "")
                if not content_html:
                    lob_miss_count += 1

            sections.append(
                PubinfoSection(
                    id=_unquote_required(columns[_COL_ID]),
                    law_code=_unquote_required(columns[_COL_LAW_CODE]),
                    section_num=_unquote_required(columns[_COL_SECTION_NUM]),
                    effective_date=_unquote(columns[_COL_EFFECTIVE_DATE]),
                    division=_unquote(columns[_COL_DIVISION]),
                    title=_unquote(columns[_COL_TITLE]),
                    part=_unquote(columns[_COL_PART]),
                    chapter=_unquote(columns[_COL_CHAPTER]),
                    article=_unquote(columns[_COL_ARTICLE]),
                    history=_unquote(columns[_COL_HISTORY]),
                    content_html=content_html,
                    active_flg=_unquote_required(columns[_COL_ACTIVE_FLG]),
                )
            )

        if lob_miss_count:
            logger.warning("lob_files_missing", count=lob_miss_count)

        logger.info("dat_parsed", total_sections=len(sections))
        return sections

    def filter_sections(
        self,
        sections: list[PubinfoSection],
        target_codes: list[str],
        target_divisions: list[str] | None = None,
        active_only: bool = True,
    ) -> list[PubinfoSection]:
        """Filter sections by law_code, division, and active flag.

        Args:
            sections: Parsed sections from parse_law_sections().
            target_codes: Law code abbreviations to include (e.g., ["LAB"]).
            target_divisions: If provided, only include sections in these
                divisions (e.g., ["2.", "3."]). Division values are matched
                with trailing dot normalization.
            active_only: If True, exclude sections with active_flg != "Y".

        Returns:
            Filtered list of PubinfoSection.
        """
        code_set = {c.upper() for c in target_codes}
        result: list[PubinfoSection] = []

        for s in sections:
            if s.law_code.upper() not in code_set:
                continue

            if active_only and s.active_flg.upper() != "Y":
                continue

            if target_divisions:
                div = s.division or ""
                # Normalize: add trailing dot if not present
                div_normalized = div if div.endswith(".") else f"{div}."
                if div_normalized not in target_divisions and div not in target_divisions:
                    continue

            result.append(s)

        logger.info(
            "sections_filtered",
            input_count=len(sections),
            output_count=len(result),
            codes=list(code_set),
            divisions=target_divisions,
        )
        return result

    def to_statute_sections(
        self, sections: list[PubinfoSection]
    ) -> list[StatuteSection]:
        """Convert PubinfoSection objects to StatuteSection (reuse existing model).

        Builds citations, hierarchy paths, extracts plain text from HTML,
        and identifies subdivision markers.
        """
        result: list[StatuteSection] = []

        for s in sections:
            text = html_to_text(s.content_html)
            if not text.strip():
                continue

            citation = build_citation(s.law_code, s.section_num)

            hierarchy = HierarchyPath(
                code_name=s.law_code,
                division=f"Division {s.division}" if s.division else "",
                title=f"Title {s.title}" if s.title else "",
                part=f"Part {s.part}" if s.part else "",
                chapter=f"Chapter {s.chapter}" if s.chapter else "",
                article=f"Article {s.article}" if s.article else "",
            )

            subdivisions = _find_subdivisions(text)

            source_url = (
                f"{BASE_URL}/faces/codes_displaySection.xhtml"
                f"?lawCode={s.law_code}&sectionNum={s.section_num}"
            )

            # Parse amendment info from history field
            amendment_info = s.history if s.history else None

            result.append(
                StatuteSection(
                    section_number=s.section_num,
                    code_abbreviation=s.law_code,
                    text=text,
                    citation=citation,
                    hierarchy=hierarchy,
                    effective_date=s.effective_date,
                    amendment_info=amendment_info,
                    subdivisions=subdivisions,
                    source_url=source_url,
                )
            )

        logger.info(
            "converted_to_statute_sections",
            input_count=len(sections),
            output_count=len(result),
            skipped_empty=len(sections) - len(result),
        )
        return result


def _find_subdivisions(text: str) -> list[str]:
    """Find top-level subdivision markers in section text."""
    subdivisions: list[str] = []
    for line in text.split("\n"):
        match = _SUBDIVISION_RE.match(line)
        if match:
            marker = match.group(1)
            if marker not in subdivisions:
                subdivisions.append(marker)
    return subdivisions


def download_pubinfo(
    dest_dir: Path,
    year: int | None = None,
    force: bool = False,
) -> Path:
    """Download the PUBINFO ZIP archive from leginfo.

    The PUBINFO full archive is updated daily and contains all California
    statutory codes. Daily delta ZIPs (pubinfo_Mon.zip through pubinfo_Sat.zip)
    exist but only contain bill-related tables, NOT law_section_tbl. Therefore,
    the recommended update strategy is weekly re-download of the full archive
    using ``force=True``.

    Args:
        dest_dir: Directory to save the downloaded ZIP.
        year: Year of the full archive (e.g., 2025). If None, uses current year.
        force: If True, re-download even if the file already exists. Use for
            weekly refreshes to pick up statutory code updates.

    Returns:
        Path to the downloaded ZIP file.
    """
    if year is None:
        from datetime import datetime, timezone

        year = datetime.now(tz=timezone.utc).year

    filename = f"pubinfo_{year}.zip"
    url = f"https://downloads.leginfo.legislature.ca.gov/{filename}"
    dest_path = dest_dir / filename

    dest_dir.mkdir(parents=True, exist_ok=True)

    if dest_path.exists() and not force:
        logger.info("pubinfo_zip_exists", path=str(dest_path))
        return dest_path

    if dest_path.exists() and force:
        logger.info("pubinfo_force_redownload", path=str(dest_path))
        dest_path.unlink()

    logger.info("downloading_pubinfo", url=url, dest=str(dest_path))

    with httpx.stream("GET", url, timeout=600.0, follow_redirects=True) as response:
        response.raise_for_status()

        total = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(dest_path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = (downloaded / total) * 100
                    logger.info(
                        "download_progress",
                        percent=f"{pct:.1f}%",
                        mb=f"{downloaded / 1024 / 1024:.1f}",
                    )

    logger.info("pubinfo_downloaded", path=str(dest_path), size_mb=f"{dest_path.stat().st_size / 1024 / 1024:.1f}")
    return dest_path
