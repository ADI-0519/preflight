// Offline plumbing test only. This provider does not call or evaluate a model.
module.exports = class IdentityProvider {
  id() { return 'preflight-offline-plumbing'; }
  async callApi(prompt) { return { output: prompt }; }
};
