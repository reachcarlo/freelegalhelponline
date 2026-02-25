# Markdown Generation Rules

When generating or editing Markdown files, follow these rules to produce lint-free output that passes markdownlint validation.

## Code Blocks (CRITICAL)

### MD040: Always Specify Language

Every fenced code block MUST have a language identifier.

Correct — specify language after opening backticks:

```javascript
function hello() {
  console.log("Hello");
}
```

```bash
npm install
```

```text
numo/
├── src/
└── README.md
```

Wrong — using triple backticks without a language identifier after them causes MD040.

### Common Language Identifiers

| Content Type | Use |
| ------------ | --- |
| JavaScript | `javascript` or `js` |
| TypeScript | `typescript` or `ts` |
| Rust | `rust` |
| Shell commands | `bash` or `shell` |
| JSON | `json` |
| TOML | `toml` |
| YAML | `yaml` |
| Directory trees | `text` |
| ASCII flowcharts/pipelines | `text` |
| Plain text/output | `text` |
| Markdown examples | `markdown` or `md` |
| Diffs | `diff` |
| SQL | `sql` |
| HTML | `html` |
| CSS | `css` |

### MD031: Blank Lines Around Code Blocks

Fenced code blocks MUST have blank lines before and after.

Correct structure:

1. Paragraph text
2. Blank line
3. Opening fence with language
4. Code content
5. Closing fence
6. Blank line
7. More paragraph text

Wrong — placing a code fence immediately after a paragraph with no blank line, or immediately before text with no blank line, causes MD031.

### MD046: Consistent Code Block Style

Always use fenced code blocks (triple backticks), never indented code blocks (4 spaces).

Correct — fenced style:

```javascript
const x = 1;
```

Wrong — indented style (4 spaces) is not allowed. Even when showing "bad" examples, use fenced blocks with a language like `text` or `markdown`.

### MD048: Consistent Fence Style

Always use backticks (`` ``` ``), never tildes (`~~~`). Mixing styles causes MD048.

### Nested Code Blocks

When showing markdown examples that contain code fences, use 4 backticks for the outer fence:

`````markdown
````markdown
```rust
fn main() {}
```
````
`````

This prevents the inner triple backticks from closing the outer block.

## Tables (CRITICAL)

### MD060: Consistent Table Spacing (Compact Style)

All table cells MUST have consistent spacing around pipes. Use exactly ONE space after the opening pipe and before the closing pipe. Do NOT add extra padding to align columns — the linter enforces "compact" style.

Correct (compact — no extra padding):

```markdown
| Column 1 | Column 2 | Column 3 |
| -------- | -------- | -------- |
| Short | Medium text | Longer content here |
```

Wrong — missing spaces (causes MD060):

```markdown
|Column 1|Column 2|Column 3|
|--------|--------|--------|
```

Wrong — extra padding to align columns (causes MD060 "extra space"):

```markdown
| Column 1 | Column 2    | Column 3            |
| -------- | ----------- | ------------------- |
| Short    | Medium text | Longer content here |
```

### MD055-MD058: Table Structure

- Every row must have the same number of columns
- Header separator row must exist with dashes
- Use pipe-space at start and space-pipe at end of each row
- Separator row format: `| --- | --- |` with spaces around dashes

Table template:

```markdown
| Header 1 | Header 2 | Header 3 |
| -------- | -------- | -------- |
| Cell 1   | Cell 2   | Cell 3   |
```

## Headings

### MD001: Heading Increment

Headings must increment by one level at a time. Never skip levels.

Correct: `#` then `##` then `###`

Wrong: `#` then `###` (skipped h2)

### MD003: Consistent Heading Style

Use ATX-style headings (with `#`) consistently. Never mix with setext style (underlines).

### MD018/MD019: Space After Hash

Exactly one space after `#` symbols.

Correct: `## Heading`

Wrong: `##Heading` or `##  Heading`

### MD022: Blank Lines Around Headings

Headings must have blank lines before and after (except at document start).

### MD024: No Duplicate Headings

Avoid headings with identical text at the same level in the same document. When you need similar headings (e.g., format names in different sections), add context to make them unique:

Wrong — duplicate `### PDF` headings in same document:

```markdown
## Output Format
### PDF
...
## Processing Details
### PDF
```

Correct — add context to differentiate:

```markdown
## Output Format
### PDF
...
## Processing Details
### PDF Processing
```

### MD025: Single Top-Level Heading

Only one `# Title` per document.

### MD026: No Trailing Punctuation

Headings should not end with punctuation like `.` or `:` (question marks `?` are allowed).

Correct: `## What is this?` and `## Overview`

Wrong: `## Overview.` and `## Features:`

## Lists

### MD004: Consistent List Markers

Use `-` for unordered lists consistently. Never mix `-`, `*`, and `+`.

Correct:

```markdown
- Item 1
- Item 2
  - Nested item
```

### MD005/MD007: List Indentation

Use 2 spaces for nested list indentation.

Correct: 2 spaces for first nesting level, 4 for second

Wrong: 4 spaces for first nesting level

### MD029: Ordered List Prefix

Use `1.` for all ordered list items. Let the renderer handle numbering.

Correct:

```markdown
1. First item
1. Second item
1. Third item
```

### MD030: Space After List Markers

Exactly one space after list markers.

Correct: `- Item` and `1. Item`

Wrong: `-Item` or `-  Item` or `1.Item`

### MD032: Blank Lines Around Lists

Lists must have blank lines before and after.

## Spacing and Whitespace

### MD009: No Trailing Spaces

Lines must not end with trailing whitespace.

### MD010: No Hard Tabs

Use spaces, not tabs for indentation.

### MD012: No Multiple Blank Lines

Maximum one consecutive blank line between content.

### MD047: Single Trailing Newline

Files must end with exactly one newline character.

## Links and Images

### MD034: No Bare URLs

URLs must be wrapped in angle brackets or formatted as links.

Correct: `<https://example.com>` or `[Example](https://example.com)`

Wrong: `https://example.com` as plain text

### MD039: No Spaces in Link Text

Link text must not have leading or trailing spaces.

Correct: `[link text](url)`

Wrong: `[ link text ](url)`

### MD042: No Empty Links

Links must have a destination. Never use `[link]()` or `[link](#)`.

### MD045: Images Need Alt Text

All images must have descriptive alt text.

Correct: `![Description of image](image.png)`

Wrong: `![](image.png)`

## Emphasis and Code Spans

### MD037: No Spaces in Emphasis

Emphasis markers must not have adjacent spaces.

Correct: `**bold**` and `*italic*`

Wrong: `** bold **` and `* italic *`

### MD038: No Spaces in Code Spans

Inline code must not have leading or trailing spaces inside backticks.

Correct: `` `command` ``

Wrong: `` ` command ` `` (spaces inside backticks)

### MD049/MD050: Consistent Emphasis Style

Use `*` for italic and `**` for bold consistently throughout the document.

### MD036: No Emphasis as Heading (CRITICAL)

NEVER use bold or italic text as a substitute for headings. This is a very common AI mistake.

Wrong — using bold as a pseudo-heading:

```markdown
**Good Examples**

Some content here.

**Bad Examples**

More content.
```

Correct — use actual heading levels:

```markdown
#### Good Examples

Some content here.

#### Bad Examples

More content.
```

If you need labeled sections within a subsection, use the next heading level down (h4, h5, etc.) rather than bold text.

## Blockquotes

### MD027: Single Space After Blockquote

One space after the `>` symbol.

Correct: `> Quote text here.`

Wrong: `>Quote text` or `>  Quote text`

## Quick Reference Checklist

When generating Markdown, verify:

1. All code blocks have language identifiers (MD040)
1. All code blocks use fenced style, not indented (MD046)
1. Tables have proper spacing around pipes (MD060)
1. Headings increment by one level only (MD001)
1. Blank lines around headings, lists, and code blocks (MD022, MD031, MD032)
1. No bold/italic used as headings — use real headings (MD036)
1. Links and images are properly formatted (MD034, MD039, MD042, MD045)
1. File ends with single newline (MD047)
1. No trailing whitespace or multiple blank lines (MD009, MD012)
1. Consistent use of `-` for unordered lists (MD004)
1. Consistent use of `1.` for ordered lists (MD029)
1. No bare URLs (MD034)
