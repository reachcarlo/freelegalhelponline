"""Tests for the content cleaner."""

from employee_help.processing.cleaner import clean


class TestWhitespaceNormalization:
    def test_collapses_multiple_spaces(self) -> None:
        assert clean("hello    world") == "hello world"

    def test_collapses_excessive_blank_lines(self) -> None:
        result = clean("line 1\n\n\n\n\nline 2")
        assert "\n\n\n" not in result
        assert "line 1" in result
        assert "line 2" in result

    def test_strips_leading_trailing_whitespace(self) -> None:
        assert clean("  hello  ") == "hello"

    def test_preserves_single_blank_lines(self) -> None:
        result = clean("paragraph 1\n\nparagraph 2")
        assert "paragraph 1\n\nparagraph 2" == result


class TestBoilerplateRemoval:
    def test_removes_skip_to_content(self) -> None:
        assert "Skip" not in clean("Skip to Main Content\n# Title")
        assert "Skip" not in clean("Skip to Content\n# Title")

    def test_removes_standalone_menu_search(self) -> None:
        result = clean("# Title\nSearch\nContent here\nMenu\nMore content")
        assert "Search" not in result.split("\n")  # "Search" as a standalone line removed
        assert "Menu" not in result.split("\n")  # "Menu" as a standalone line removed
        assert "Content here" in result


class TestUnicodeCleanup:
    def test_normalizes_smart_quotes(self) -> None:
        result = clean("\u201cHello\u201d and \u2018world\u2019")
        assert '"Hello"' in result
        assert "'world'" in result

    def test_normalizes_dashes(self) -> None:
        result = clean("em\u2014dash and en\u2013dash")
        assert "em - dash" in result
        assert "en-dash" in result

    def test_removes_zero_width_spaces(self) -> None:
        result = clean("hello\u200bworld")
        assert result == "helloworld"

    def test_normalizes_non_breaking_spaces(self) -> None:
        result = clean("hello\u00a0world")
        assert result == "hello world"

    def test_fixes_encoding_artifacts(self) -> None:
        result = clean("it\u00e2\u0080\u0099s great")
        # Should handle gracefully — at minimum not crash
        assert isinstance(result, str)


class TestMarkdownPreservation:
    def test_preserves_heading_markers(self) -> None:
        text = "# Title\n\n## Section\n\nContent"
        result = clean(text)
        assert "# Title" in result
        assert "## Section" in result

    def test_preserves_list_markers(self) -> None:
        text = "Items:\n- First\n- Second\n- Third"
        result = clean(text)
        assert "- First" in result
        assert "- Second" in result

    def test_preserves_numbered_lists(self) -> None:
        text = "Steps:\n1. First step\n2. Second step"
        result = clean(text)
        assert "1. First step" in result

    def test_preserves_table_rows(self) -> None:
        text = "| Col 1 | Col 2 |\n| --- | --- |\n| A | B |"
        result = clean(text)
        assert "| Col 1 | Col 2 |" in result

    def test_empty_input(self) -> None:
        assert clean("") == ""
        assert clean("   ") == ""
