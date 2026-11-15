export const VRN_CORE_RE = /^([A-Z]{2})(\d{1,3})([A-Z]{1,4})(\d{1,4})$/;
export const VRN_DASHED_RE = /^[A-Z]{2}-\d{1,3}-[A-Z]{1,4}-\d{1,4}$/;

/** Strip all non-alphanumeric characters and uppercase. */
export function normalizeVrnRaw(raw: string): string {
  return raw.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
}

/**
 * Auto-format a raw VRN to `AS-01-AB-1234` on blur.
 * Strips non-alphanumerics, uppercases, then applies the structural regex.
 * If the structure doesn't match, returns the stripped/uppercased value as-is.
 */
export function formatVrn(raw: string): string {
  const stripped = normalizeVrnRaw(raw);
  const match = VRN_CORE_RE.exec(stripped);
  if (!match) return stripped;
  return `${match[1]}-${match[2]}-${match[3]}-${match[4]}`;
}

/** Normalized (no separator) form used by the backend, e.g. `AS01AB1234`. */
export function vrnToNormalized(raw: string): string {
  return normalizeVrnRaw(raw);
}

/** True when the value (dashed or plain) matches the VRN structure. */
export function isValidVrn(raw: string): boolean {
  const stripped = normalizeVrnRaw(raw);
  return VRN_CORE_RE.test(stripped);
}
