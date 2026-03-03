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
