// Path-param validator for case IDs — Story 3.6 § Pitfall #9.
// Mirrors `contracts.cases._CASE_ID_PATTERN` in Python.

const CASE_ID_PATTERN = /^case_[0-9A-HJKMNP-TV-Z]{26}$/;

export function isValidCaseId(value: string): boolean {
  return CASE_ID_PATTERN.test(value);
}
