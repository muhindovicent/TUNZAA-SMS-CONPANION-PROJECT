/**
 * Tunza front-end bootstrap. No framework, no build step and no runtime CDN.
 * @module tunza/app
 */

export const APP_NAME = "Tunza";

/**
 * @typedef {{ name: string, version: string }} AppInfo
 */

/** @type {AppInfo} */
export const APP_INFO = Object.freeze({ name: APP_NAME, version: "0.1.0" });

/**
 * @param {string} value
 * @returns {string}
 */
export function normaliseLabel(value) {
  return value.trim().replace(/\s+/gu, " ");
}
