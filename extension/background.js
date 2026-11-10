// Profile data is readable only by trusted extension pages, not content scripts.
const restrictStorage = () => chrome.storage.local.setAccessLevel({accessLevel: 'TRUSTED_CONTEXTS'});
chrome.runtime.onInstalled.addListener(restrictStorage);
chrome.runtime.onStartup.addListener(restrictStorage);
restrictStorage();
