/**
 * Check if a content type represents binary data that needs special handling.
 * Binary types include images (except SVG) and PDFs.
 */
export function isBinaryContentType(contentType?: string): boolean {
	if (!contentType) return false;

	// Images (except SVG which is text-based)
	if (contentType.startsWith("image/") && contentType !== "image/svg+xml") {
		return true;
	}

	// PDF
	if (contentType === "application/pdf") {
		return true;
	}

	return false;
}

/**
 * Convert an ArrayBuffer to a base64 string.
 */
export function arrayBufferToBase64(buffer: ArrayBuffer): string {
	const bytes = new Uint8Array(buffer);
	const binary = Array.from(bytes, (byte) => String.fromCharCode(byte)).join(
		"",
	);
	return btoa(binary);
}
