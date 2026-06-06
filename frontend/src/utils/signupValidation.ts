export const PHONE_DIGIT_COUNT = 11;
export const CNIC_DIGIT_COUNT = 13;
export const POSTAL_CODE_DIGIT_COUNT = 5;
export const MIN_PASSWORD_LENGTH = 8;

export const PHONE_REGEX = /^\d{4}-\d{7}$/;
export const CNIC_REGEX = /^\d{5}-\d{7}-\d$/;
export const POSTAL_CODE_REGEX = /^\d{5}$/;
export const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function onlyDigits(value: string): string {
  return value.replace(/\D/g, "");
}

export function formatPhoneInput(value: string): string {
  const digits = onlyDigits(value).slice(0, PHONE_DIGIT_COUNT);
  if (digits.length <= 4) {
    return digits;
  }
  return `${digits.slice(0, 4)}-${digits.slice(4)}`;
}

export function formatCnicInput(value: string): string {
  const digits = onlyDigits(value).slice(0, CNIC_DIGIT_COUNT);

  if (digits.length <= 5) {
    return digits;
  }
  if (digits.length <= 12) {
    return `${digits.slice(0, 5)}-${digits.slice(5)}`;
  }
  return `${digits.slice(0, 5)}-${digits.slice(5, 12)}-${digits.slice(12)}`;
}

export function formatPostalCodeInput(value: string): string {
  return onlyDigits(value).slice(0, POSTAL_CODE_DIGIT_COUNT);
}

export function isValidEmail(value: string): boolean {
  return EMAIL_REGEX.test(value.trim());
}

export function isValidPhone(value: string): boolean {
  return PHONE_REGEX.test(value.trim());
}

export function isValidCnic(value: string): boolean {
  return CNIC_REGEX.test(value.trim());
}

export function isValidPostalCode(value: string): boolean {
  return POSTAL_CODE_REGEX.test(value.trim());
}
