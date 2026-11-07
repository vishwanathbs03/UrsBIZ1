import { formatINR, formatDate, formatDSO, formatRelativeTime } from '../lib/formatters';

// 1. Zero handling
if (formatINR(0, { compact: true }) !== '₹0') throw new Error('Zero compact failed');
if (formatINR(0) !== '₹0.00') throw new Error('Zero full failed');
if (formatINR(-0) !== '₹0.00') throw new Error('Negative zero failed');

// 2. Negative numbers
if (formatINR(-12345.67) !== '-₹12,345.67') throw new Error('Negative INR failed');
if (formatINR(-15000000, { compact: true }) !== '-₹1.5 Cr') throw new Error('Negative compact failed');

// 3. Multi-crore
if (formatINR(150000000, { compact: true }) !== '₹15.0 Cr') throw new Error('Multi-crore Cr failed');
if (formatINR(150000000, { compact: true, language: 'kn' }) !== '₹15.0 ಕೋಟಿ') throw new Error('Multi-crore Kannada failed');

// 4. Timezone-safe date-only parsing
if (formatDate('2026-05-15') !== '15-05-2026') throw new Error('Date-only format failed');
if (formatDate('invalid') !== '—') throw new Error('Invalid date fallback failed');
if (formatDate(null) !== '—') throw new Error('Null date fallback failed');
if (formatDate(undefined) !== '—') throw new Error('Undefined date fallback failed');

// 5. Grammatical singular vs plural
if (formatDSO(1, 'kn') !== '1 ದಿನ') throw new Error('DSO singular Kannada failed');
if (formatDSO(45, 'kn') !== '45 ದಿನಗಳು') throw new Error('DSO plural Kannada failed');
if (formatDSO(1, 'en') !== '1 day') throw new Error('DSO singular English failed');
if (formatDSO(45, 'en') !== '45 days') throw new Error('DSO plural English failed');

// 6. Relative time Kannada declensions
const now = Date.now();
if (formatRelativeTime(new Date(now - 60 * 1000), 'kn') !== '1 ನಿಮಿಷದ ಹಿಂದೆ') throw new Error('1m Kannada singular failed');
if (formatRelativeTime(new Date(now - 5 * 60 * 1000), 'kn') !== '5 ನಿಮಿಷಗಳ ಹಿಂದೆ') throw new Error('5m Kannada plural failed');
if (formatRelativeTime(new Date(now - 60 * 60 * 1000), 'kn') !== '1 ಗಂಟೆಯ ಹಿಂದೆ') throw new Error('1h Kannada singular failed');
if (formatRelativeTime(new Date(now - 3 * 60 * 60 * 1000), 'kn') !== '3 ಗಂಟೆಗಳ ಹಿಂದೆ') throw new Error('3h Kannada plural failed');
if (formatRelativeTime(new Date(now - 24 * 60 * 60 * 1000), 'kn') !== 'ನಿನ್ನೆ') throw new Error('1d Kannada failed');
if (formatRelativeTime(new Date(now - 4 * 24 * 60 * 60 * 1000), 'kn') !== '4 ದಿನಗಳ ಹಿಂದೆ') throw new Error('4d Kannada plural failed');

console.log('ALL_FORMATTER_RUNTIME_CHECKS_PASSED');
