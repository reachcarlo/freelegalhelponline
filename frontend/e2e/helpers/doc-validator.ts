/**
 * Shared helpers for validating PDF and DOCX content in E2E tests.
 */

import JSZip from "jszip";
import { PDFDocument } from "pdf-lib";

/**
 * Validate that a buffer is a valid PDF and check form field values.
 *
 * Uses pdf-lib to read AcroForm field values directly. The PDFs are
 * editable (not flattened), so field values live in the form dictionary
 * rather than the text content stream.
 */
export async function validatePdfContent(
  buffer: Buffer,
  expectations: {
    containsText?: string[];
    doesNotContainText?: string[];
  } = {}
): Promise<void> {
  const pdfDoc = await PDFDocument.load(buffer);
  const form = pdfDoc.getForm();
  const fields = form.getFields();

  // Collect all field values into a single string for text searching
  const allValues = fields
    .map((f) => {
      try {
        const tf = form.getTextField(f.getName());
        return tf.getText() ?? "";
      } catch {
        return "";
      }
    })
    .join(" ");

  if (expectations.containsText) {
    for (const expected of expectations.containsText) {
      if (!allValues.includes(expected)) {
        throw new Error(
          `PDF form fields do not contain expected text: "${expected}"\n` +
            `All field values: ${allValues.slice(0, 500)}`
        );
      }
    }
  }

  if (expectations.doesNotContainText) {
    for (const unexpected of expectations.doesNotContainText) {
      if (allValues.includes(unexpected)) {
        throw new Error(
          `PDF form fields unexpectedly contain text: "${unexpected}"`
        );
      }
    }
  }
}

/**
 * Validate that a buffer is a valid DOCX and optionally check its text content.
 *
 * Reads word/document.xml from the ZIP archive and checks for text.
 */
export async function validateDocxContent(
  buffer: Buffer,
  expectations: {
    containsText?: string[];
    doesNotContainText?: string[];
  } = {}
): Promise<void> {
  const zip = await JSZip.loadAsync(buffer);

  const docXml = zip.file("word/document.xml");
  if (!docXml) {
    throw new Error("DOCX does not contain word/document.xml");
  }

  const xmlContent = await docXml.async("text");

  if (expectations.containsText) {
    for (const expected of expectations.containsText) {
      if (!xmlContent.includes(expected)) {
        throw new Error(
          `DOCX does not contain expected text: "${expected}"\n` +
            `First 500 chars of document.xml: ${xmlContent.slice(0, 500)}`
        );
      }
    }
  }

  if (expectations.doesNotContainText) {
    for (const unexpected of expectations.doesNotContainText) {
      if (xmlContent.includes(unexpected)) {
        throw new Error(
          `DOCX unexpectedly contains text: "${unexpected}"`
        );
      }
    }
  }
}

/**
 * Return a map of PDF AcroForm field names to their text values.
 *
 * Field names are keyed by both the full qualified path (e.g.
 * "DISC-001[0].Page1[0].Table[0].AttyPartyInfo[0].Name[0]") and the
 * leaf segment (e.g. "Name[0]"). When multiple fields share a leaf name,
 * the first non-empty value wins.
 */
export async function getPdfFieldMap(
  buffer: Buffer
): Promise<Record<string, string>> {
  const pdfDoc = await PDFDocument.load(buffer);
  const form = pdfDoc.getForm();
  const result: Record<string, string> = {};
  for (const field of form.getFields()) {
    try {
      const fullName = field.getName();
      const tf = form.getTextField(fullName);
      const value = tf.getText() ?? "";
      // Store under full qualified name
      result[fullName] = value;
      // Also store under leaf name (last dot-separated segment)
      const leaf = fullName.split(".").pop() ?? fullName;
      if (!(leaf in result) || (value && !result[leaf])) {
        result[leaf] = value;
      }
    } catch {
      // Skip non-text fields (checkboxes, etc.)
    }
  }
  return result;
}

/**
 * Return the leaf names of all checked checkbox fields in a PDF.
 */
export async function getPdfCheckboxes(buffer: Buffer): Promise<string[]> {
  const pdfDoc = await PDFDocument.load(buffer);
  const form = pdfDoc.getForm();
  const checked: string[] = [];
  for (const field of form.getFields()) {
    try {
      const cb = form.getCheckBox(field.getName());
      if (cb.isChecked()) {
        const fullName = field.getName();
        const leaf = fullName.split(".").pop() ?? fullName;
        checked.push(leaf);
      }
    } catch {
      // Not a checkbox
    }
  }
  return checked;
}

/**
 * Extract plain text from a DOCX by stripping XML tags from word/document.xml.
 *
 * This solves the problem where text is split across XML tags (e.g.
 * `<w:t>Test</w:t><w:t> Attorney</w:t>`), making substring searches fail
 * on the raw XML.
 */
export async function getDocxPlainText(buffer: Buffer): Promise<string> {
  const zip = await JSZip.loadAsync(buffer);
  const docXml = zip.file("word/document.xml");
  if (!docXml) {
    throw new Error("DOCX does not contain word/document.xml");
  }
  const xmlContent = await docXml.async("text");
  // Strip all XML tags and collapse whitespace
  return xmlContent.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

/**
 * Validate DOCX content using stripped plain text (tag-agnostic).
 * Same API as `validateDocxContent` but operates on text with tags removed.
 */
export async function validateDocxPlainText(
  buffer: Buffer,
  expectations: {
    containsText?: string[];
    doesNotContainText?: string[];
  } = {}
): Promise<void> {
  const text = await getDocxPlainText(buffer);

  if (expectations.containsText) {
    for (const expected of expectations.containsText) {
      if (!text.includes(expected)) {
        throw new Error(
          `DOCX plain text does not contain expected text: "${expected}"\n` +
            `First 500 chars: ${text.slice(0, 500)}`
        );
      }
    }
  }

  if (expectations.doesNotContainText) {
    for (const unexpected of expectations.doesNotContainText) {
      if (text.includes(unexpected)) {
        throw new Error(
          `DOCX plain text unexpectedly contains text: "${unexpected}"`
        );
      }
    }
  }
}

/**
 * Validate that a buffer starts with the PDF magic bytes.
 */
export function isPdf(buffer: Buffer): boolean {
  return buffer.slice(0, 5).toString("ascii") === "%PDF-";
}

/**
 * Validate that a buffer is a valid ZIP (DOCX format).
 */
export function isDocx(buffer: Buffer): boolean {
  // ZIP files start with PK\x03\x04
  return (
    buffer.length > 4 &&
    buffer[0] === 0x50 &&
    buffer[1] === 0x4b &&
    buffer[2] === 0x03 &&
    buffer[3] === 0x04
  );
}
