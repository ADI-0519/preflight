// Readiness only: no client creation, credential values or trace upload.
require.resolve('@langfuse/client');
const required = ['LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY', 'LANGFUSE_BASE_URL'];
const missing = required.filter(key => !process.env[key]);
console.log('Langfuse SDK installed. No telemetry was sent.');
if (missing.length) {
  console.log(`Account configuration still needed: ${missing.join(', ')}`);
  process.exitCode = 2;
} else {
  console.log('Configuration names present; connectivity and trace masking are unverified.');
}
