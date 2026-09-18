const state = window.HermiMeetingState.attach({
  token: localStorage.getItem("hermi_owner_token") || "",
  conversationId: null,
  initialConversationSelectionDone: false,
  user: null,
  pendingFiles: [],
  chatMode: localStorage.getItem("hermi_chat_mode") || "chat",
  activeSend: null,
  inflightByConversation: {},
  finalizedRunsByConversation: {},
  assistantActorsByConversation: {},
  activeRunPoll: null,
  pendingConfirm: null,
  roomId: null,
  meetingRunId: null,
  meetingPoll: null,
  traceRenderQueue: [],
  traceRenderFrame: null,
  messageLoadSequence: 0,
  usagePeriod: "7d",
  usageUserId: "",
  usageLoadSequence: 0,
  mySummaryLoadSequence: 0,
  mySummaryDirty: false,
  accountSummary: null,
  symbiosisOpen: false,
  symbiosisTab: "notes",
  editingEvolutionBlueprintId: "",
  exceptionOpen: false,
  exceptionTab: "monitor",
  editingEvolutionNoteId: "",
  evolutionNoteSelection: { start: 0, end: 0 },
  proposalOpinionViews: {},
  evolutionUpdateNoticeForUser: "",
  evolutionUpdateDismissedForUser: "",
  pendingEvolutionUpdateAt: 0,
  pendingAccountNotices: [],
  activeAccountNotice: null,
  editingUserProfileId: "",
  userProfileLoadSequence: 0,
  selectedSkillCapability: null,
});

const tokenForm = document.querySelector("#token-form");
const tokenInput = document.querySelector("#token-input");
const accountMenuButton = document.querySelector("#account-menu-button");
const accountDisplayName = document.querySelector("#account-display-name");
const accountMenu = document.querySelector("#account-menu");
const accountQuotaButton = document.querySelector("#account-quota-button");
const accountQuotaLabel = document.querySelector("#account-quota-label");
const accountQuotaReset = document.querySelector("#account-quota-reset");
const accountSettingsButton = document.querySelector("#account-settings-button");
const accountLogoutButton = document.querySelector("#account-logout-button");
const appDownloadButton = document.querySelector("#app-download-button");
const accountSettingsModal = document.querySelector("#account-settings-modal");
const accountSettingsSummary = document.querySelector("#account-settings-summary");
const accountRequestQuotaButton = document.querySelector("#account-request-quota-button");
const accountSettingsClose = document.querySelector("#account-settings-close");
const accountLanguageButton = document.querySelector("#account-language-button");
const accountLanguageOptions = document.querySelector("#account-language-options");
const accountLanguageMenu = accountLanguageButton.closest(".account-language-menu");
const ACCOUNT_LANGUAGE_OPTIONS_CLOSE_DELAY_MS = 320;
const userInfoModal = document.querySelector("#user-info-modal");
const userInfoTitle = document.querySelector("#user-info-title");
const userInfoSubtitle = document.querySelector("#user-info-subtitle");
const userInfoRelationship = document.querySelector("#user-info-relationship");
const userInfoPreferences = document.querySelector("#user-info-preferences");
const userInfoRecentFocus = document.querySelector("#user-info-recent-focus");
const userInfoStatus = document.querySelector("#user-info-status");
const leftPanelToggle = document.querySelector("#left-panel-toggle");
const rightPanelToggle = document.querySelector("#right-panel-toggle");
const displayModeToggle = document.querySelector("#display-mode-toggle");
const conversationPanel = document.querySelector("#conversation-panel");
const approvalPanel = document.querySelector("#approval-panel");
const approvalToolsButton = document.querySelector("#approval-tools-button");
const approvalToolsView = document.querySelector("#approval-tools-view");
const rightPanelEyebrow = document.querySelector("#right-panel-eyebrow");
const rightPanelTitle = document.querySelector("#right-panel-title");
const drawerBackdrop = document.querySelector("#drawer-backdrop");
const conversationList = document.querySelector("#conversation-list");
const hermiConversationList = document.querySelector("#hermi-conversation-list");
const hermiConversationGroups = document.querySelector("#hermi-conversation-groups");
const otherConversationList = document.querySelector("#other-conversation-list");
const otherConversationSection = document.querySelector("#other-conversation-section");
const apiConversationList = document.querySelector("#api-conversation-list");
const apiConversationSection = document.querySelector("#api-conversation-section");
const roomList = document.querySelector("#room-list");
const roomNavSection = document.querySelector("#room-nav-section");
const newMeetingButton = document.querySelector("#new-meeting");
const messageList = document.querySelector("#message-list");
const messageWrap = document.querySelector("#message-wrap");
const composerPrivacyBar = document.querySelector("#composer-privacy-bar");
const composerPrivacyInfoWrap = document.querySelector("#composer-privacy-info-wrap");
const composerPrivacyInfo = document.querySelector("#composer-privacy-info");
const symbiosisWorkspace = document.querySelector("#symbiosis-workspace");
const symbiosisTopTitle = document.querySelector("#symbiosis-top-title");
const symbiosisTopEyebrow = document.querySelector("#symbiosis-top-eyebrow");
const symbiosisTopHeading = document.querySelector("#symbiosis-top-heading");
const symbiosisReturn = document.querySelector("#symbiosis-return");
const evolutionNotesTab = document.querySelector("#evolution-notes-tab");
const evolutionBlueprintsTab = document.querySelector("#evolution-blueprints-tab");
const featureProposalsTab = document.querySelector("#feature-proposals-tab");
const evolutionNotesView = document.querySelector("#evolution-notes-view");
const evolutionBlueprintsView = document.querySelector("#evolution-blueprints-view");
const featureProposalsView = document.querySelector("#feature-proposals-view");
const evolutionNotesList = document.querySelector("#evolution-notes-list");
const evolutionBlueprintsList = document.querySelector("#evolution-blueprints-list");
const featureProposalsList = document.querySelector("#feature-proposals-list");
const evolutionNoteForm = document.querySelector("#evolution-note-form");
const evolutionNoteToolbar = document.querySelector("#evolution-note-toolbar");
const evolutionNoteInput = document.querySelector("#evolution-note-input");
const evolutionNotePublish = document.querySelector("#evolution-note-publish");
const evolutionNoteCancel = document.querySelector("#evolution-note-cancel");
const evolutionBlueprintForm = document.querySelector("#evolution-blueprint-form");
const evolutionBlueprintToolbar = document.querySelector("#evolution-blueprint-toolbar");
const evolutionBlueprintInput = document.querySelector("#evolution-blueprint-input");
const evolutionBlueprintPublish = document.querySelector("#evolution-blueprint-publish");
const evolutionBlueprintCancel = document.querySelector("#evolution-blueprint-cancel");
const featureProposalForm = document.querySelector("#feature-proposal-form");
const featureProposalType = document.querySelector("#feature-proposal-type");
const featureProposalSupportFields = document.querySelector("#feature-proposal-support-fields");
const featureProposalPollFields = document.querySelector("#feature-proposal-poll-fields");
const featureProposalTitle = document.querySelector("#feature-proposal-title");
const featureProposalInput = document.querySelector("#feature-proposal-input");
const featureProposalQuestion = document.querySelector("#feature-proposal-question");
const featureProposalOptions = document.querySelector("#feature-proposal-options");
const featureProposalAddOption = document.querySelector("#feature-proposal-add-option");
const exceptionWorkspace = document.querySelector("#exception-workspace");
const exceptionReturn = document.querySelector("#exception-return");
const exceptionMonitorTab = document.querySelector("#exception-monitor-tab");
const exceptionArchiveTab = document.querySelector("#exception-archive-tab");
const exceptionMonitorView = document.querySelector("#exception-monitor-view");
const exceptionArchiveView = document.querySelector("#exception-archive-view");
const dropZone = document.querySelector(".chat");
const scrollBottomButton = document.querySelector("#scroll-bottom");
const approvalList = document.querySelector("#approval-list");
const settingsToolsButton = document.querySelector("#settings-tools-button");
const settingsToolsModal = document.querySelector("#settings-tools-modal");
const temporaryToolsButton = document.querySelector("#temporary-tools-button");
const temporaryToolsModal = document.querySelector("#temporary-tools-modal");
const meetingToolsButton = document.querySelector("#meeting-tools-button");
const meetingToolsView = document.querySelector("#meeting-tools-view");
const rightPanelTabs = document.querySelector("#right-panel-tabs");
const rightPanelTabPrev = document.querySelector("#right-panel-tab-prev");
const rightPanelTabNext = document.querySelector("#right-panel-tab-next");
const meetingForm = document.querySelector("#meeting-form");
const meetingPanelHeading = document.querySelector("#meeting-panel-heading");
const meetingName = document.querySelector("#meeting-name");
const meetingMode = document.querySelector("#meeting-mode");
const meetingRounds = document.querySelector("#meeting-rounds");
const meetingPermission = document.querySelector("#meeting-permission");
const meetingMemberList = document.querySelector("#meeting-member-list");
const meetingSave = document.querySelector("#meeting-save");
const meetingRunControls = document.querySelector("#meeting-run-controls");
const meetingRunStatus = document.querySelector("#meeting-run-status");
const meetingStop = document.querySelector("#meeting-stop");
const meetingResume = document.querySelector("#meeting-resume");
const meetingCancel = document.querySelector("#meeting-cancel");
const profileNameList = document.querySelector("#profile-name-list");
const confirmModal = document.querySelector("#confirm-modal");
const confirmTitle = document.querySelector("#confirm-title");
const confirmMessage = document.querySelector("#confirm-message");
const confirmCancel = document.querySelector("#confirm-cancel");
const confirmOk = document.querySelector("#confirm-ok");
const accountNoticeModal = document.querySelector("#account-notice-modal");
const accountNoticeTitle = document.querySelector("#account-notice-title");
const accountNoticeMessage = document.querySelector("#account-notice-message");
const accountNoticeConfirm = document.querySelector("#account-notice-confirm");
const evolutionUpdateModal = document.querySelector("#evolution-update-modal");
const evolutionUpdateSummary = document.querySelector("#evolution-update-summary");
const evolutionUpdateList = document.querySelector("#evolution-update-list");
const evolutionUpdateClose = document.querySelector("#evolution-update-close");
const usageGuideModal = document.querySelector("#usage-guide-modal");
const usageGuideConfirm = document.querySelector("#usage-guide-confirm");
const usageGuideDismiss = document.querySelector("#usage-guide-dismiss");
const newConversationButton = document.querySelector("#new-conversation");
const newConversationModal = document.querySelector("#new-conversation-modal");
const newConversationVera = document.querySelector("#new-conversation-vera");
const newConversationVeda = document.querySelector("#new-conversation-veda");
const newConversationEmber = document.querySelector("#new-conversation-ember");
const newConversationChoices = document.querySelectorAll(".profile-choice[data-profile-id]");
const newConversationCancel = document.querySelector("#new-conversation-cancel");
const newConversationDismiss = document.querySelector("#new-conversation-dismiss");
const newConversationConfirm = document.querySelector("#new-conversation-confirm");
const selectedProfileName = document.querySelector("#selected-profile-name");
const selectedProfileState = document.querySelector("#selected-profile-state");
const selectedProfileNotice = document.querySelector("#selected-profile-notice");
const connection = document.querySelector("#connection");
const title = document.querySelector("#conversation-title");
const messageInput = document.querySelector("#message-input");
const messageForm = document.querySelector("#message-form");
const sendButton = document.querySelector("#send-button");
const fileForm = document.querySelector("#file-form");
const fileInput = document.querySelector("#file-input");
const uploadTrigger = document.querySelector("#upload-trigger");
const fileList = document.querySelector("#file-list");
const adminSection = document.querySelector("#admin-section");
const usageSection = document.querySelector("#usage-section");
const taskSection = document.querySelector("#task-section");
const adminUserForm = document.querySelector("#admin-user-form");
const adminUserId = document.querySelector("#admin-user-id");
const adminDisplayName = document.querySelector("#admin-display-name");
const adminToken = document.querySelector("#admin-token");
const adminRole = document.querySelector("#admin-role");
const adminUserList = document.querySelector("#admin-user-list");
const usageList = document.querySelector("#usage-list");
const usageTotalTokens = document.querySelector("#usage-total-tokens");
const usagePeriodFilters = document.querySelector("#usage-period-filters");
const taskList = document.querySelector("#task-list");
const contextSection = document.querySelector("#context-section");
const contextSummary = document.querySelector("#context-summary");
const profileSection = document.querySelector("#profile-section");
const profileList = document.querySelector("#profile-list");
const profileNameSection = document.querySelector("#profile-name-section");
const meetingPresetSection = document.querySelector("#meeting-preset-section");
const meetingPresetList = document.querySelector("#meeting-preset-list");
const brainSection = document.querySelector("#brain-section");
const brainStatusList = document.querySelector("#brain-status-list");
const promptSection = document.querySelector("#prompt-section");
const promptBindingList = document.querySelector("#prompt-binding-list");
const capabilitySection = document.querySelector("#capability-section");
const capabilityList = document.querySelector("#capability-list");
const selectedSkillCapability = document.querySelector("#selected-skill-capability");
const actionValidateForm = document.querySelector("#action-validate-form");
const actionValidateInput = document.querySelector("#action-validate-input");
const actionValidateResult = document.querySelector("#action-validate-result");

setDisplayMode(state.chatMode);

initializePanels();
window.HermiPermissionsPanel.init({ api, afterSave: loadUsers });
window.HermiScheduledJobs.init({ api, confirmAction, getUser: () => state.user, afterChange: loadTasks });

tokenForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submittedToken = tokenInput.value.trim();
  if (submittedToken) {
    state.token = submittedToken;
    localStorage.setItem("hermi_owner_token", state.token);
  }
  if (!state.token) {
    setConnectionState(false);
    return;
  }
  tokenInput.value = "";
  state.conversationId = null;
  state.initialConversationSelectionDone = false;
  await refresh();
  if (isCompactViewport() && state.user) closeDrawers();
  messageInput.focus();
});

leftPanelToggle.addEventListener("click", () => togglePanel("conversations"));
rightPanelToggle.addEventListener("click", () => togglePanel("approvals"));
displayModeToggle.addEventListener("click", () => {
  setDisplayMode(state.chatMode === "chat" ? "professional" : "chat");
});
document.querySelector("#close-approvals").addEventListener("click", closeDrawers);
drawerBackdrop.addEventListener("click", closeDrawers);
approvalToolsButton.addEventListener("click", () => switchRightPanelView("approvals"));
settingsToolsButton.addEventListener("click", openSettingsTools);
temporaryToolsButton.addEventListener("click", openTemporaryTools);
rightPanelTabPrev.addEventListener("click", () => rightPanelTabs.scrollBy({ left: -160, behavior: "smooth" }));
rightPanelTabNext.addEventListener("click", () => rightPanelTabs.scrollBy({ left: 160, behavior: "smooth" }));
rightPanelTabs.addEventListener("scroll", syncRightPanelTabNavigation, { passive: true });
window.addEventListener("resize", syncRightPanelTabNavigation);
meetingToolsButton.addEventListener("click", () => {
  if (!state.roomId && !meetingMemberList.childElementCount) {
    meetingName.value = meetingName.value.trim() || "会议室";
    loadMeetingMembers();
  }
  syncMeetingModeControl();
  switchRightPanelView("meeting");
  setPanelOpen("approvals", true);
});

accountMenuButton.addEventListener("click", toggleAccountMenu);
document.addEventListener("click", closeAccountMenuOnOutsideClick);
composerPrivacyInfo?.addEventListener("click", (event) => {
  event.stopPropagation();
  toggleComposerPrivacyTooltip(!composerPrivacyInfoWrap?.classList.contains("is-open"));
});
document.addEventListener("click", (event) => {
  if (!composerPrivacyInfoWrap?.contains(event.target)) toggleComposerPrivacyTooltip(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") toggleComposerPrivacyTooltip(false);
});
accountSettingsButton.addEventListener("click", openAccountSettings);
accountRequestQuotaButton.addEventListener("click", requestTemporaryQuota);
accountLanguageButton.addEventListener("click", () => {
  setAccountLanguageOptionsOpen(!isAccountLanguageOptionsOpen());
});
accountLanguageButton.addEventListener("mouseenter", () => setAccountLanguageOptionsOpen(true));
accountLanguageButton.addEventListener("focus", () => setAccountLanguageOptionsOpen(true));
accountLanguageOptions.addEventListener("focusin", () => setAccountLanguageOptionsOpen(true));
accountLanguageMenu.addEventListener("focusout", () => {
  window.setTimeout(() => {
    if (!accountLanguageMenu.contains(document.activeElement)) setAccountLanguageOptionsOpen(false);
  }, 0);
});
document.addEventListener("pointermove", handleAccountLanguagePointerMove, { passive: true });
window.addEventListener("resize", positionAccountLanguageOptions);
window.addEventListener("scroll", positionAccountLanguageOptions, true);
accountLanguageOptions.querySelectorAll("[data-interface-locale]").forEach((button) => {
  button.addEventListener("click", () => setInterfaceLocale(button.dataset.interfaceLocale));
});
accountLogoutButton.addEventListener("click", logout);
accountSettingsClose.addEventListener("click", closeAccountSettings);
accountSettingsModal.addEventListener("click", (event) => {
  if (event.target === accountSettingsModal) closeAccountSettings();
});
userInfoModal.addEventListener("click", (event) => {
  if (event.target === userInfoModal) closeUserInfoModal();
});
userInfoModal.querySelectorAll("[data-user-profile-field]").forEach((button) => {
  button.addEventListener("click", () => saveUserInfoField(button.dataset.userProfileField));
});
appDownloadButton.addEventListener("click", async () => {
  await showInfoNotice({
    title: "下载 Hermi APP",
    message: "APP 入口正在预留中，当前可以继续使用网页版。",
  });
});
document.querySelectorAll("[data-symbiosis-entry]").forEach((button) => {
  button.addEventListener("click", () => openSymbiosisWorkspace(button.dataset.symbiosisEntry));
});
document.querySelectorAll("[data-efficiency-placeholder]").forEach((button) => {
  button.addEventListener("click", async () => {
    await showInfoNotice({
      title: button.dataset.efficiencyPlaceholder || "共生网络",
      message: "~施工中ing~ (ง •_•)ง 这里正在慢慢搭起来。",
    });
  });
});
document.querySelectorAll("[data-exception-entry]").forEach((button) => {
  button.addEventListener("click", openExceptionWorkspace);
});
symbiosisReturn.addEventListener("click", () => closeSymbiosisWorkspace());
exceptionReturn.addEventListener("click", () => closeSymbiosisWorkspace());
evolutionNotesTab.addEventListener("click", () => setSymbiosisTab("notes"));
evolutionBlueprintsTab.addEventListener("click", () => setSymbiosisTab("blueprints"));
featureProposalsTab.addEventListener("click", () => setSymbiosisTab("proposals"));
exceptionMonitorTab.addEventListener("click", () => setExceptionTab("monitor"));
exceptionArchiveTab.addEventListener("click", () => setExceptionTab("archive"));
evolutionNoteCancel.addEventListener("click", resetEvolutionNoteEditor);
evolutionNoteForm.addEventListener("submit", publishEvolutionNote);
evolutionBlueprintCancel.addEventListener("click", resetEvolutionBlueprintEditor);
evolutionBlueprintForm.addEventListener("submit", publishEvolutionBlueprint);
evolutionUpdateClose.addEventListener("click", closeEvolutionUpdateNotice);
usageGuideConfirm.addEventListener("click", () => closeUsageGuide(false));
usageGuideDismiss.addEventListener("click", () => closeUsageGuide(true));
capabilityList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-skill-capability-id]");
  if (button) selectSkillCapability(button.dataset.skillCapabilityId, button.dataset.skillCapabilityTitle);
});
function rememberEvolutionNoteSelection() {
  state.evolutionNoteSelection = {
    start: evolutionNoteInput.selectionStart,
    end: evolutionNoteInput.selectionEnd,
  };
}
evolutionNoteInput.addEventListener("select", rememberEvolutionNoteSelection);
evolutionNoteInput.addEventListener("keyup", rememberEvolutionNoteSelection);
evolutionNoteInput.addEventListener("keydown", () => queueMicrotask(rememberEvolutionNoteSelection));
evolutionNoteInput.addEventListener("mouseup", rememberEvolutionNoteSelection);
evolutionNoteInput.addEventListener("input", rememberEvolutionNoteSelection);
evolutionNoteToolbar.addEventListener("mousedown", (event) => {
  if (event.target.closest("button[data-note-format]")) {
    rememberEvolutionNoteSelection();
    event.preventDefault();
  }
});
evolutionBlueprintToolbar.addEventListener("mousedown", (event) => {
  if (event.target.closest("button[data-blueprint-format]")) event.preventDefault();
});
evolutionNoteToolbar.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-note-format]");
  if (button) formatEvolutionNoteSelection(button.dataset.noteFormat);
});
evolutionBlueprintToolbar.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-blueprint-format]");
  if (button) formatEvolutionBlueprintSelection(button.dataset.blueprintFormat);
});
featureProposalForm.addEventListener("submit", publishFeatureProposal);
featureProposalType.addEventListener("change", syncFeatureProposalForm);
featureProposalAddOption.addEventListener("click", () => addFeatureProposalOption());
featureProposalOptions.addEventListener("click", (event) => {
  const button = event.target.closest(".feature-proposal-remove-option");
  if (button) removeFeatureProposalOption(button.closest(".feature-proposal-option-row"));
});

function logout() {
  if (state.activeSend) cancelActiveSend();
  state.token = "";
  state.user = null;
  state.conversationId = null;
  state.initialConversationSelectionDone = false;
  state.inflightByConversation = {};
  state.finalizedRunsByConversation = {};
  state.assistantActorsByConversation = {};
  state.accountSummary = null;
  state.symbiosisOpen = false;
  state.editingEvolutionNoteId = "";
  closeSymbiosisWorkspace({ reload: false });
  localStorage.removeItem("hermi_owner_token");
  document.body.dataset.auth = "bad";
  document.body.dataset.role = "";
  accountMenuButton.hidden = true;
  accountMenu.hidden = true;
  accountMenuButton.setAttribute("aria-expanded", "false");
  accountDisplayName.textContent = "";
  closeAccountSettings();
  tokenForm.hidden = false;
  toggleOwnerPanels(false);
  hermiConversationList.innerHTML = "";
  hermiConversationGroups.innerHTML = "";
  otherConversationList.innerHTML = "";
  apiConversationList.innerHTML = "";
  roomList.innerHTML = "";
  messageList.innerHTML = "";
  setConnectionState(false);
  tokenInput.value = "";
  tokenInput.focus();
}

function setConnectionState(connected) {
  connection.textContent = connected ? uiText("connected", "已连接") : uiText("disconnected", "链接中断");
  connection.dataset.state = connected ? "ok" : "warn";
}

function uiText(key, fallback, values = {}) {
  return window.HermiI18n?.t(key, values) || fallback;
}

function applyInterfaceLocale(locale) {
  window.HermiI18n?.setLocale(locale, { owner: state.user?.role === "owner" });
  setAccountLanguageOptionsOpen(false);
  if (state.user) setConnectionState(connection.dataset.state === "ok");
  setDisplayMode(state.chatMode);
  const activeRightView = !temporaryToolsModal.hidden
    ? "temporary"
    : !meetingToolsView.hidden
      ? "meeting"
      : !settingsToolsModal.hidden
        ? "settings"
        : "approvals";
  switchRightPanelView(activeRightView);
  if (state.accountSummary) loadMySummary({ force: true });
}

async function setInterfaceLocale(locale) {
  const updated = await api("/my/locale", {
    method: "PATCH",
    body: JSON.stringify({ locale }),
  });
  state.user.locale = updated.locale;
  applyInterfaceLocale(updated.locale);
  accountMenu.hidden = true;
  accountMenuButton.setAttribute("aria-expanded", "false");
  setAccountLanguageOptionsOpen(false);
}

function isSymbiosisOwner() {
  return state.user?.role === "owner";
}

function openSymbiosisWorkspace(entry) {
  if (entry !== "evolution" || !state.user) return;
  state.symbiosisOpen = true;
  state.exceptionOpen = false;
  syncSymbiosisHeader();
  messageWrap.hidden = true;
  composerPrivacyBar.hidden = true;
  messageForm.hidden = true;
  scrollBottomButton.hidden = true;
  symbiosisWorkspace.hidden = false;
  exceptionWorkspace.hidden = true;
  setSymbiosisTab(state.symbiosisTab || "notes", { load: false });
  if (isCompactViewport()) closeDrawers();
  void loadSymbiosisWorkspace();
}

function openExceptionWorkspace() {
  if (!state.user) return;
  state.symbiosisOpen = false;
  state.exceptionOpen = true;
  syncSymbiosisHeader();
  messageWrap.hidden = true;
  composerPrivacyBar.hidden = true;
  messageForm.hidden = true;
  scrollBottomButton.hidden = true;
  symbiosisWorkspace.hidden = true;
  exceptionWorkspace.hidden = false;
  setExceptionTab(state.exceptionTab || "monitor");
  if (isCompactViewport()) closeDrawers();
}

function closeSymbiosisWorkspace({ reload = true } = {}) {
  state.symbiosisOpen = false;
  state.exceptionOpen = false;
  syncSymbiosisHeader();
  symbiosisWorkspace.hidden = true;
  exceptionWorkspace.hidden = true;
  messageWrap.hidden = false;
  composerPrivacyBar.hidden = false;
  messageForm.hidden = false;
  if (reload && state.token) {
    void loadConversations();
  }
}

function syncSymbiosisHeader() {
  const isOpen = state.symbiosisOpen || state.exceptionOpen;
  displayModeToggle.hidden = isOpen;
  title.hidden = isOpen;
  symbiosisTopTitle.hidden = !isOpen;
  symbiosisTopEyebrow.textContent = uiText("symbiosis_network", "共生网络");
  symbiosisTopHeading.textContent = state.exceptionOpen
    ? uiText("exception_center", "异常处理中心")
    : uiText("evolution_station", "演化观测站");
}

function setSymbiosisTab(tab, { load = true } = {}) {
  state.symbiosisTab = ["notes", "blueprints", "proposals"].includes(tab) ? tab : "notes";
  const isNotes = state.symbiosisTab === "notes";
  const isBlueprints = state.symbiosisTab === "blueprints";
  evolutionNotesTab.classList.toggle("active", isNotes);
  evolutionNotesTab.setAttribute("aria-selected", String(isNotes));
  evolutionBlueprintsTab.classList.toggle("active", isBlueprints);
  evolutionBlueprintsTab.setAttribute("aria-selected", String(isBlueprints));
  featureProposalsTab.classList.toggle("active", state.symbiosisTab === "proposals");
  featureProposalsTab.setAttribute("aria-selected", String(state.symbiosisTab === "proposals"));
  evolutionNotesView.hidden = !isNotes;
  evolutionBlueprintsView.hidden = !isBlueprints;
  featureProposalsView.hidden = state.symbiosisTab !== "proposals";
  if (load && state.symbiosisOpen) {
    void (isNotes ? loadEvolutionNotes() : isBlueprints ? loadEvolutionBlueprints() : loadFeatureProposals());
  }
}

function setExceptionTab(tab) {
  state.exceptionTab = tab === "archive" ? "archive" : "monitor";
  const isMonitor = state.exceptionTab === "monitor";
  exceptionMonitorTab.classList.toggle("active", isMonitor);
  exceptionMonitorTab.setAttribute("aria-selected", String(isMonitor));
  exceptionArchiveTab.classList.toggle("active", !isMonitor);
  exceptionArchiveTab.setAttribute("aria-selected", String(!isMonitor));
  exceptionMonitorView.hidden = !isMonitor;
  exceptionArchiveView.hidden = isMonitor;
}

async function loadSymbiosisWorkspace() {
  if (!state.token) return;
  await Promise.all([loadEvolutionNotes(), loadEvolutionBlueprints(), loadFeatureProposals()]);
}

function symbiosisEmpty(text) {
  const empty = document.createElement("p");
  empty.className = "symbiosis-empty";
  empty.textContent = text;
  return empty;
}

async function loadEvolutionNotes() {
  if (!state.token) return;
  const data = await api("/symbiosis/notes");
  evolutionNotesList.replaceChildren();
  const notes = Array.isArray(data.notes) ? data.notes : [];
  if (!notes.length) evolutionNotesList.append(symbiosisEmpty("还没有演化纪要。"));
  for (const note of notes) evolutionNotesList.append(renderEvolutionNote(note));
  evolutionNoteForm.hidden = !isSymbiosisOwner();
}

async function loadEvolutionBlueprints() {
  if (!state.token) return;
  const data = await api("/symbiosis/blueprints");
  evolutionBlueprintsList.replaceChildren();
  const blueprints = Array.isArray(data.blueprints) ? data.blueprints : [];
  if (!blueprints.length) evolutionBlueprintsList.append(symbiosisEmpty("还没有演化蓝图。"));
  for (const blueprint of blueprints) evolutionBlueprintsList.append(renderEvolutionNote(blueprint, { kind: "blueprint" }));
  evolutionBlueprintForm.hidden = !isSymbiosisOwner();
}

function evolutionUpdateStorageKey() {
  return `hermi_seen_evolution_update:${state.user?.user_id || "anonymous"}`;
}

function evolutionUpdateTitle(note) {
  const firstLine = String(note.content || "").split(/\r?\n/).find((line) => line.trim()) || "演化纪要";
  return firstLine.replace(/^#+\s*/, "").replace(/\*\*/g, "").trim() || "演化纪要";
}

function closeEvolutionUpdateNotice() {
  state.evolutionUpdateDismissedForUser = state.user?.user_id || "";
  if (state.pendingEvolutionUpdateAt) {
    localStorage.setItem(evolutionUpdateStorageKey(), String(state.pendingEvolutionUpdateAt));
    state.pendingEvolutionUpdateAt = 0;
  }
  evolutionUpdateModal.hidden = true;
  showPendingAccountNotice();
}

function hasBlockingCenterModal() {
  return Array.from(document.querySelectorAll(".modal-backdrop")).some((modal) => (
    modal !== evolutionUpdateModal && !modal.hidden
  ));
}

function showPendingEvolutionUpdateNotice() {
  const userId = state.user?.user_id;
  if (
    !userId
    || !state.pendingEvolutionUpdateAt
    || state.evolutionUpdateDismissedForUser === userId
    || hasBlockingCenterModal()
  ) return;
  evolutionUpdateModal.hidden = false;
  evolutionUpdateClose.focus();
}

async function loadAccountNotices() {
  if (!state.token || !state.user) return;
  const data = await api("/my/notices");
  state.pendingAccountNotices = Array.isArray(data.notices) ? data.notices : [];
  showPendingAccountNotice();
}

function showPendingAccountNotice() {
  if (!accountNoticeModal.hidden || state.activeAccountNotice || hasBlockingCenterModal()) return;
  const notice = state.pendingAccountNotices[0];
  if (!notice) return;
  state.activeAccountNotice = notice;
  accountNoticeTitle.textContent = notice.title || "账户通知";
  accountNoticeMessage.textContent = notice.message || "你的账户状态有更新。";
  accountNoticeModal.hidden = false;
  accountNoticeConfirm.focus();
}

async function dismissActiveAccountNotice() {
  const notice = state.activeAccountNotice;
  if (!notice) return;
  accountNoticeConfirm.disabled = true;
  try {
    await api(`/my/notices/${notice.notice_id}/read`, { method: "POST" });
    state.pendingAccountNotices = state.pendingAccountNotices.filter((item) => item.notice_id !== notice.notice_id);
    state.activeAccountNotice = null;
    accountNoticeModal.hidden = true;
    showPendingAccountNotice();
  } finally {
    accountNoticeConfirm.disabled = false;
  }
}

async function checkEvolutionUpdates() {
  const userId = state.user?.user_id;
  if (!state.token || !userId || state.evolutionUpdateNoticeForUser === userId) return;
  state.evolutionUpdateNoticeForUser = userId;
  const data = await api("/symbiosis/notes");
  const seenAt = Number(localStorage.getItem(evolutionUpdateStorageKey()) || 0);
  const recentCutoff = Date.now() / 1000 - 30 * 24 * 60 * 60;
  const updates = (Array.isArray(data.notes) ? data.notes : []).filter((note) => {
    const updatedAt = Number(note.updated_at || note.created_at || 0);
    return updatedAt > seenAt && updatedAt >= recentCutoff;
  });
  if (!updates.length) return;
  state.pendingEvolutionUpdateAt = Math.max(...updates.map((note) => Number(note.updated_at || note.created_at || 0)));
  if (state.evolutionUpdateDismissedForUser === userId) {
    localStorage.setItem(evolutionUpdateStorageKey(), String(state.pendingEvolutionUpdateAt));
    state.pendingEvolutionUpdateAt = 0;
    return;
  }
  evolutionUpdateSummary.textContent = `最近有 ${updates.length} 条演化纪要更新。`;
  evolutionUpdateList.replaceChildren();
  for (const note of updates.slice(0, 3)) {
    const item = document.createElement("div");
    item.className = "evolution-update-item";
    const heading = document.createElement("strong");
    heading.textContent = evolutionUpdateTitle(note);
    const time = document.createElement("span");
    time.textContent = formatClock(note.updated_at || note.created_at);
    item.append(heading, time);
    evolutionUpdateList.append(item);
  }
  showPendingEvolutionUpdateNotice();
}

function renderEvolutionNote(note, { kind = "note" } = {}) {
  const article = document.createElement("article");
  article.className = "symbiosis-record evolution-note";
  article.classList.toggle("is-pinned", Boolean(note.is_pinned));
  const meta = document.createElement("header");
  meta.className = "symbiosis-record-meta";
  const timestamp = document.createElement("time");
  timestamp.dateTime = new Date(Number(note.created_at || 0) * 1000).toISOString();
  timestamp.textContent = evolutionNoteTimestamp(note);
  const author = document.createElement("span");
  author.className = "symbiosis-author";
  author.textContent = `作者：${note.author_display_name || note.created_by || "Owner"}`;
  meta.append(timestamp, author);
  if (isSymbiosisOwner()) {
    const actions = document.createElement("div");
    actions.className = "symbiosis-record-actions";
    const pin = document.createElement("button");
    pin.type = "button";
    pin.className = "text-button";
    pin.textContent = note.is_pinned ? "取消置顶" : "置顶";
    pin.addEventListener("click", () => (kind === "blueprint" ? toggleEvolutionBlueprintPin(note) : toggleEvolutionNotePin(note)));
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "text-button";
    edit.textContent = "编辑";
    edit.addEventListener("click", () => (kind === "blueprint" ? startEvolutionBlueprintEdit(note) : startEvolutionNoteEdit(note)));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "text-button danger-text-button";
    remove.textContent = "删除";
    remove.addEventListener("click", () => (kind === "blueprint" ? deleteEvolutionBlueprint(note) : deleteEvolutionNote(note)));
    actions.append(pin, edit, remove);
    meta.append(actions);
  }
  const content = document.createElement("div");
  content.className = "symbiosis-markdown";
  content.innerHTML = renderMarkdown(note.content || "");
  article.append(meta, content);
  return article;
}

function evolutionNoteTimestamp(note) {
  const createdAt = Number(note.created_at || 0);
  const updatedAt = Number(note.updated_at || createdAt);
  const published = formatClock(createdAt);
  if (updatedAt <= createdAt + 0.001) return published;
  const elapsedSeconds = Math.max(0, Math.floor(Date.now() / 1000 - updatedAt));
  if (elapsedSeconds < 3600) return `${published}（${Math.max(1, Math.floor(elapsedSeconds / 60))}分钟前编辑）`;
  if (elapsedSeconds < 86400) return `${published}（${Math.floor(elapsedSeconds / 3600)}小时前编辑）`;
  return `${published}（${Math.floor(elapsedSeconds / 86400)}天前编辑）`;
}

function startEvolutionNoteEdit(note) {
  state.editingEvolutionNoteId = note.note_id;
  evolutionNoteInput.value = note.content || "";
  evolutionNotePublish.textContent = "保存修改";
  evolutionNoteCancel.hidden = false;
  evolutionNoteInput.focus();
}

function resetEvolutionNoteEditor() {
  state.editingEvolutionNoteId = "";
  evolutionNoteForm.reset();
  evolutionNotePublish.textContent = "发布";
  evolutionNoteCancel.hidden = true;
}

function startEvolutionBlueprintEdit(blueprint) {
  state.editingEvolutionBlueprintId = blueprint.note_id;
  evolutionBlueprintInput.value = blueprint.content || "";
  evolutionBlueprintPublish.textContent = "保存修改";
  evolutionBlueprintCancel.hidden = false;
  evolutionBlueprintInput.focus();
}

function resetEvolutionBlueprintEditor() {
  state.editingEvolutionBlueprintId = "";
  evolutionBlueprintForm.reset();
  evolutionBlueprintPublish.textContent = "发布蓝图";
  evolutionBlueprintCancel.hidden = true;
}

function formatEvolutionNoteSelection(format) {
  formatMarkdownSelection(evolutionNoteInput, format, state.evolutionNoteSelection);
}

function formatEvolutionBlueprintSelection(format) {
  formatMarkdownSelection(evolutionBlueprintInput, format, {
    start: evolutionBlueprintInput.selectionStart,
    end: evolutionBlueprintInput.selectionEnd,
  });
}

function formatMarkdownSelection(input, format, { start, end }) {
  const selected = input.value.slice(start, end) || "文字";
  const formatters = {
    heading: (text) => `## ${text}`,
    bold: (text) => `**${text}**`,
    italic: (text) => `*${text}*`,
    list: (text) => text.split("\n").map((line) => `- ${line || "项目"}`).join("\n"),
    "ordered-list": (text) => text.split("\n").map((line, index) => `${index + 1}. ${line || "项目"}`).join("\n"),
    quote: (text) => text.split("\n").map((line) => `> ${line || "引用"}`).join("\n"),
    code: (text) => `\`${text}\``,
    strike: (text) => `~~${text}~~`,
    divider: () => "\n\n---\n\n",
  };
  const replacement = formatters[format]?.(selected);
  if (!replacement) return;
  input.setRangeText(replacement, start, end, "select");
  input.focus();
}

async function publishEvolutionNote(event) {
  event.preventDefault();
  const content = evolutionNoteInput.value.trim();
  if (!content) return;
  const editingId = state.editingEvolutionNoteId;
  await api(editingId ? `/symbiosis/notes/${editingId}` : "/symbiosis/notes", {
    method: editingId ? "PATCH" : "POST",
    body: JSON.stringify({ content }),
  });
  resetEvolutionNoteEditor();
  await loadEvolutionNotes();
}

async function deleteEvolutionNote(note) {
  if (!(await confirmAction({ title: "删除演化纪要", message: "删除这条演化纪要？" }))) return;
  await api(`/symbiosis/notes/${note.note_id}`, { method: "DELETE" });
  if (state.editingEvolutionNoteId === note.note_id) resetEvolutionNoteEditor();
  await loadEvolutionNotes();
}

async function toggleEvolutionNotePin(note) {
  await api(`/symbiosis/notes/${note.note_id}/pin`, {
    method: "PUT",
    body: JSON.stringify({ pinned: !note.is_pinned }),
  });
  await loadEvolutionNotes();
}

async function publishEvolutionBlueprint(event) {
  event.preventDefault();
  const content = evolutionBlueprintInput.value.trim();
  if (!content) return;
  const editingId = state.editingEvolutionBlueprintId;
  await api(editingId ? `/symbiosis/blueprints/${editingId}` : "/symbiosis/blueprints", {
    method: editingId ? "PATCH" : "POST",
    body: JSON.stringify({ content }),
  });
  resetEvolutionBlueprintEditor();
  await loadEvolutionBlueprints();
}

async function deleteEvolutionBlueprint(blueprint) {
  if (!(await confirmAction({ title: "删除演化蓝图", message: "删除这条演化蓝图？" }))) return;
  await api(`/symbiosis/blueprints/${blueprint.note_id}`, { method: "DELETE" });
  if (state.editingEvolutionBlueprintId === blueprint.note_id) resetEvolutionBlueprintEditor();
  await loadEvolutionBlueprints();
}

async function toggleEvolutionBlueprintPin(blueprint) {
  await api(`/symbiosis/blueprints/${blueprint.note_id}/pin`, {
    method: "PUT",
    body: JSON.stringify({ pinned: !blueprint.is_pinned }),
  });
  await loadEvolutionBlueprints();
}

async function loadFeatureProposals({ force = false } = {}) {
  if (!state.token) return;
  if (!force && (featureProposalsList.contains(document.activeElement) || featureProposalForm.contains(document.activeElement))) return;
  const data = await api("/symbiosis/proposals");
  featureProposalsList.replaceChildren();
  const proposals = Array.isArray(data.proposals) ? data.proposals : [];
  if (!proposals.length) featureProposalsList.append(symbiosisEmpty("还没有功能议案。"));
  for (const proposal of proposals) featureProposalsList.append(renderFeatureProposal(proposal));
  featureProposalForm.hidden = !isSymbiosisOwner();
}

function renderFeatureProposal(proposal) {
  const article = document.createElement("article");
  article.className = "symbiosis-record feature-proposal";
  const isPoll = proposal.proposal_type === "poll";
  const meta = document.createElement("header");
  meta.className = "symbiosis-record-meta";
  const heading = document.createElement("h3");
  heading.textContent = proposal.title || "未命名议案";
  const time = document.createElement("time");
  time.dateTime = new Date(Number(proposal.updated_at || proposal.created_at || 0) * 1000).toISOString();
  time.textContent = formatClock(proposal.updated_at || proposal.created_at);
  const headingBlock = document.createElement("div");
  const author = document.createElement("span");
  author.className = "symbiosis-author";
  author.textContent = `作者：${proposal.author_display_name || proposal.created_by || "Owner"}`;
  headingBlock.append(heading, time, author);
  meta.append(headingBlock);
  if (isSymbiosisOwner()) {
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "text-button danger-text-button";
    remove.textContent = "删除";
    remove.addEventListener("click", () => deleteFeatureProposal(proposal));
    meta.append(remove);
  }
  const content = document.createElement("div");
  content.className = "symbiosis-markdown";
  content.innerHTML = renderMarkdown(proposal.content || "");
  const votes = proposal.vote_summary || {};
  const summary = document.createElement("p");
  summary.className = "proposal-vote-summary";
  const choices = isPoll
    ? (proposal.options || []).map((option) => [option, option])
    : [["support", "赞成"], ["neutral", "保留"], ["oppose", "反对"]];
  summary.textContent = proposal.can_view_vote_summary
    ? choices.map(([choice, label]) => `${label} ${Number(votes[choice] || 0)}`).join(" · ")
    : "选定后点击确认，即可查看当前票数。";
  const controls = document.createElement("div");
  controls.className = "proposal-vote-controls";
  const isOwner = isSymbiosisOwner();
  const canEditVote = isOwner || (!proposal.viewer_locked && !proposal.viewer_vote_confirmed);
  const canEditComment = isOwner || !proposal.viewer_locked;
  for (const [choice, label] of choices) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "vote-button";
    button.textContent = label;
    button.setAttribute("aria-pressed", String(proposal.viewer_vote === choice));
    button.classList.toggle("selected", proposal.viewer_vote === choice);
    button.disabled = !canEditVote;
    button.addEventListener("click", async () => {
      if (proposal.viewer_vote === choice) {
        await api(`/symbiosis/proposals/${proposal.proposal_id}/vote`, { method: "DELETE" });
      } else {
        await api(`/symbiosis/proposals/${proposal.proposal_id}/vote`, {
          method: "POST",
          body: JSON.stringify({ choice }),
        });
      }
      await loadFeatureProposals({ force: true });
    });
    controls.append(button);
  }
  if (!isOwner && proposal.viewer_vote && !proposal.viewer_vote_confirmed && !proposal.viewer_locked) {
    const confirmVote = document.createElement("button");
    confirmVote.type = "button";
    confirmVote.className = "text-button proposal-vote-confirm";
    confirmVote.textContent = "确认投票";
    confirmVote.addEventListener("click", async () => {
      confirmVote.disabled = true;
      try {
        await api(`/symbiosis/proposals/${proposal.proposal_id}/confirm-vote`, { method: "POST" });
        await loadFeatureProposals({ force: true });
      } finally {
        confirmVote.disabled = false;
      }
    });
    controls.append(confirmVote);
  }
  const participation = document.createElement("section");
  participation.className = "proposal-opinion-controls";
  let commentEditor = document.createDocumentFragment();
  if (proposal.viewer_vote || isOwner) {
    const participationLabel = document.createElement("p");
    participationLabel.className = "proposal-section-label";
    participationLabel.textContent = "查看大家的意见";
    const opinionActions = document.createElement("div");
    opinionActions.className = "proposal-opinion-actions";
    const reveal = document.createElement("button");
    reveal.type = "button";
    reveal.className = "secondary-button";
    reveal.textContent = proposal.can_view_opinions ? "查看意见" : "查看意见并锁定";
    reveal.addEventListener("click", async () => {
      if (!isOwner && !proposal.viewer_locked) {
        const confirmed = await confirmAction({
          title: "查看意见",
          message: "查看其他人的意见后，将不能修改本次支持、投票或评论。",
        });
        if (!confirmed) return;
        await api(`/symbiosis/proposals/${proposal.proposal_id}/reveal-opinions`, { method: "POST" });
      }
      const data = await api(`/symbiosis/proposals/${proposal.proposal_id}/opinions`);
      state.proposalOpinionViews[proposal.proposal_id] = data.opinions || [];
      await loadFeatureProposals({ force: true });
    });
    opinionActions.append(reveal);
    participation.append(participationLabel, opinionActions);
    if (Object.hasOwn(state.proposalOpinionViews, proposal.proposal_id)) {
      participation.append(buildProposalOpinions(state.proposalOpinionViews[proposal.proposal_id]));
    }
    commentEditor = document.createElement("section");
    commentEditor.className = "proposal-comment-editor";
    const commentLabel = document.createElement("p");
    commentLabel.className = "proposal-section-label";
    commentLabel.textContent = "我的建议";
    const commentInput = document.createElement("textarea");
    commentInput.className = "proposal-comment-input";
    commentInput.rows = 3;
    commentInput.maxLength = 2000;
    commentInput.placeholder = "写下你的意见（可选）";
    commentInput.value = proposal.viewer_comment || "";
    commentInput.disabled = !canEditComment;
    const saveCommentButton = document.createElement("button");
    saveCommentButton.type = "button";
    saveCommentButton.className = "text-button";
    saveCommentButton.textContent = "保存意见";
    saveCommentButton.disabled = !canEditComment;
    saveCommentButton.addEventListener("click", async () => {
      const content = commentInput.value.trim();
      if (!content) return;
      saveCommentButton.disabled = true;
      try {
        await api(`/symbiosis/proposals/${proposal.proposal_id}/comment`, {
          method: "POST",
          body: JSON.stringify({ content }),
        });
        await loadFeatureProposals({ force: true });
      } finally {
        saveCommentButton.disabled = !canEditComment;
      }
    });
    commentEditor.append(commentLabel, commentInput, saveCommentButton);
    if (proposal.viewer_comment && canEditComment) {
      const deleteComment = document.createElement("button");
      deleteComment.type = "button";
      deleteComment.className = "text-button danger-text-button";
      deleteComment.textContent = "删除我的意见";
      deleteComment.addEventListener("click", async () => {
        await api(`/symbiosis/proposals/${proposal.proposal_id}/comment`, { method: "DELETE" });
        await loadFeatureProposals({ force: true });
      });
      commentEditor.append(deleteComment);
    }
  }
  if (proposal.content) article.append(meta, content, controls, summary, participation, commentEditor);
  else article.append(meta, controls, summary, participation, commentEditor);
  return article;
}

function buildProposalOpinions(opinions) {
  const list = document.createElement("div");
  list.className = "proposal-opinion-list";
  if (!opinions.length) {
    const empty = document.createElement("p");
    empty.className = "proposal-opinion-empty";
    empty.textContent = "暂时还没有人留下意见。";
    list.append(empty);
  } else {
    for (const opinion of opinions) {
      const item = document.createElement("article");
      item.className = "proposal-opinion-item";
      const author = document.createElement("strong");
      author.textContent = opinion.display_name || opinion.user_id || "用户";
      const choice = document.createElement("span");
      choice.textContent = opinion.choice ? ` · ${opinion.choice}` : "";
      const content = document.createElement("p");
      content.textContent = opinion.comment || "";
      item.append(author, choice, content);
      list.append(item);
    }
  }
  return list;
}

function syncFeatureProposalForm() {
  const isPoll = featureProposalType.value === "poll";
  featureProposalSupportFields.hidden = isPoll;
  featureProposalPollFields.hidden = !isPoll;
  if (isPoll) ensureFeatureProposalOptionMinimum();
}

function featureProposalOptionInputs() {
  return [...featureProposalOptions.querySelectorAll("[data-feature-proposal-option]")];
}

function ensureFeatureProposalOptionMinimum() {
  while (featureProposalOptionInputs().length < 2) addFeatureProposalOption();
}

function addFeatureProposalOption(value = "") {
  const inputs = featureProposalOptionInputs();
  if (inputs.length >= 8) return;
  const row = document.createElement("div");
  row.className = "feature-proposal-option-row";
  const input = document.createElement("input");
  input.maxLength = 140;
  input.placeholder = `投票选项 ${inputs.length + 1}`;
  input.value = value;
  input.dataset.featureProposalOption = "";
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "feature-proposal-remove-option";
  remove.setAttribute("aria-label", "删除投票选项");
  remove.title = "删除选项";
  remove.textContent = "×";
  row.append(input, remove);
  featureProposalOptions.append(row);
  syncFeatureProposalOptionRows();
}

function removeFeatureProposalOption(row) {
  if (!row || featureProposalOptionInputs().length <= 2) return;
  row.remove();
  syncFeatureProposalOptionRows();
}

function syncFeatureProposalOptionRows() {
  featureProposalOptionInputs().forEach((input, index) => {
    input.placeholder = `投票选项 ${index + 1}`;
  });
  featureProposalOptions.querySelectorAll(".feature-proposal-remove-option").forEach((button) => {
    const disabled = featureProposalOptionInputs().length <= 2;
    button.disabled = disabled;
    button.title = disabled ? "至少保留两个选项" : "删除选项";
  });
}

function resetFeatureProposalForm() {
  featureProposalForm.reset();
  const rows = [...featureProposalOptions.querySelectorAll(".feature-proposal-option-row")];
  for (const row of rows.slice(2)) row.remove();
  featureProposalOptionInputs().forEach((input, index) => {
    input.value = "";
    input.placeholder = `投票选项 ${index + 1}`;
  });
  syncFeatureProposalOptionRows();
  syncFeatureProposalForm();
}

async function publishFeatureProposal(event) {
  event.preventDefault();
  const isPoll = featureProposalType.value === "poll";
  const titleValue = isPoll ? featureProposalQuestion.value.trim() : featureProposalTitle.value.trim();
  const content = isPoll ? "" : featureProposalInput.value.trim();
  const options = isPoll
    ? featureProposalOptionInputs().map((input) => input.value.trim()).filter(Boolean)
    : [];
  if (!titleValue || (!isPoll && !content) || (isPoll && options.length < 2)) return;
  await api("/symbiosis/proposals", {
    method: "POST",
    body: JSON.stringify({
      title: titleValue,
      content,
      proposal_type: isPoll ? "poll" : "support",
      options,
    }),
  });
  resetFeatureProposalForm();
  await loadFeatureProposals({ force: true });
}

async function deleteFeatureProposal(proposal) {
  if (!(await confirmAction({ title: "删除功能议案", message: `删除议案「${proposal.title || "未命名议案"}」？` }))) return;
  await api(`/symbiosis/proposals/${proposal.proposal_id}`, { method: "DELETE" });
  await loadFeatureProposals({ force: true });
}

function isConversationFinalized(conversationId) {
  return Boolean(conversationId && state.finalizedRunsByConversation[conversationId]);
}

function markConversationFinalized(conversationId) {
  if (!conversationId) return;
  const existing = state.finalizedRunsByConversation[conversationId] || {};
  const inflight = state.inflightByConversation[conversationId] || {};
  state.finalizedRunsByConversation[conversationId] = {
    runId: existing.runId || inflight.runId || "",
    finishedAt: Date.now(),
  };
}
meetingMode.addEventListener("change", syncMeetingModeControl);

function syncMeetingModeControl() {
  const single = meetingMode.value === "auto_single";
  meetingRounds.disabled = single;
  if (single) meetingRounds.value = "1";
  else if (Number(meetingRounds.value) < 2) meetingRounds.value = "2";
}
confirmModal.addEventListener("click", (event) => {
  if (event.target === confirmModal) resolveConfirm(false);
});
confirmCancel.addEventListener("click", () => resolveConfirm(false));
confirmOk.addEventListener("click", () => resolveConfirm(true));
accountNoticeConfirm.addEventListener("click", dismissActiveAccountNotice);
newConversationButton.addEventListener("click", openNewConversationPicker);
newConversationVera.addEventListener("click", () => selectConversationProfile("maid"));
newConversationVeda.addEventListener("click", () => selectConversationProfile("trainee"));
newConversationEmber.addEventListener("click", () => selectConversationProfile("imouto"));
newConversationCancel.addEventListener("click", closeNewConversationPicker);
newConversationDismiss.addEventListener("click", closeNewConversationPicker);
newConversationConfirm.addEventListener("click", createSelectedConversation);
newConversationModal.addEventListener("click", (event) => {
  if (event.target === newConversationModal) closeNewConversationPicker();
});
newMeetingButton.addEventListener("click", startNewMeeting);
meetingForm.addEventListener("submit", saveMeetingRoom);
meetingStop.addEventListener("click", () => changeMeetingRunState("stop"));
meetingResume.addEventListener("click", () => changeMeetingRunState("resume"));
meetingCancel.addEventListener("click", () => changeMeetingRunState("cancel"));

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !isMobileComposer()) {
    event.preventDefault();
    messageForm.requestSubmit();
  }
});

messageForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.roomId) {
    await submitMeetingTopic();
    return;
  }
  if (isCurrentConversationSending()) {
    cancelActiveSend();
    return;
  }
  if (state.activeSend && !isCurrentConversationSending()) {
    void showInfoNotice({ title: "会话正在回复", message: "另一个会话正在回复，等它结束后再发送。" });
    return;
  }
  const content = messageInput.value.trim();
  if (!content && !state.pendingFiles.length) return;
  if (!state.conversationId) {
    const created = await api("/conversations", {
      method: "POST",
      body: JSON.stringify({ title: content.slice(0, 24) || "新会话" }),
    });
    state.conversationId = created.conversation_id;
    state.assistantActorsByConversation[created.conversation_id] = assistantActorForConversation(created);
  }
  const sendConversationId = state.conversationId;
  const selectedSkillCapabilityId = state.selectedSkillCapability?.id || "";
  const pendingFiles = [...state.pendingFiles];
  const pendingText = content || `发送 ${pendingFiles.length} 个文件`;
  const pendingId = renderPendingUser(pendingText, pendingFiles.map(fileToPendingAttachment));
  state.inflightByConversation[sendConversationId] = {
    pendingId,
    content: pendingText,
    startedAt: Date.now(),
    trace: [],
    runId: "",
  };
  delete state.finalizedRunsByConversation[sendConversationId];
  messageInput.value = "";
  autosizeComposer();
  clearThoughtPanel();
  renderInflightForCurrentConversation();
  const controller = new AbortController();
  state.activeSend = { controller, pendingId, startedAt: Date.now(), conversationId: sendConversationId };
  syncComposerState();
  try {
    const uploadedFiles = await uploadPendingFiles();
    const result = await sendMessageStream(sendConversationId, content, uploadedFiles, controller.signal, selectedSkillCapabilityId);
    if (selectedSkillCapabilityId) clearSelectedSkillCapability();
    const userKey = window.HermiMessageUI.messageKey(sendConversationId, result.user?.message_id || "");
    window.HermiMessageUI.reconcilePendingMessage(messageList, pendingId, userKey);
    const assistantId = result.assistant?.message_id || "";
    const assistantKey = window.HermiMessageUI.messageKey(sendConversationId, assistantId);
    const tracePanel = window.HermiTraceUI.reconcileLiveTrace(messageList, assistantId);
    if (tracePanel) window.HermiTraceUI.appendTraceTime(messageList, assistantId, result.assistant?.created_at, messageTime);
    const finalizedTracePanel = finalizeTraceForAssistant(assistantId, result.assistant, tracePanel);
    markConversationFinalized(sendConversationId);
    delete state.inflightByConversation[sendConversationId];
    if (state.conversationId === sendConversationId) {
      if (!window.HermiMessageUI.hasMessage(messageList, assistantKey)) {
        animateAssistant(
          result.assistant?.content || "",
          result.assistant?.created_at,
          actorForMessage(result.assistant || { role: "assistant" }),
          assistantId,
          messageAttachments(result.assistant || {}),
        );
      }
      if (finalizedTracePanel) {
        arrangeTraceForAssistant(
          assistantId,
          messageList.querySelector(`[data-message-key="${assistantKey}"]`),
          actorForMessage(result.assistant || { role: "assistant" }),
        );
      }
    }
    await loadConversations();
    if (state.user?.can_approve) {
      loadApprovals();
      loadUsage();
      loadTasks();
      window.HermiScheduledJobs.load();
      loadConversationContext();
      loadProfiles();
      loadMeetingPresets();
      loadBrainStatus();
      loadPromptBindings();
      loadCapabilities();
    } else {
      loadApprovals();
      loadConversationContext();
      loadCapabilities();
    }
  } catch (error) {
    if (error.name === "AbortError") {
      markPendingCancelled(pendingId);
      delete state.inflightByConversation[sendConversationId];
    } else if (isQuotaSendError(error)) {
      markPendingFailed(pendingId, error);
      await showInfoNotice({ title: "额度已用尽", message: error.message || "当前额度已用尽。" });
    } else if (document.hidden || isMobileComposer()) {
      await recoverBackgroundSend(pendingId, error);
    } else {
      markPendingFailed(pendingId, error);
    }
  } finally {
    if (state.activeSend?.pendingId === pendingId) state.activeSend = null;
    syncComposerState();
    messageInput.focus();
  }
});

messageInput.addEventListener("input", autosizeComposer);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    syncComposerState();
    refreshVisibleState();
  }
});
messageList.addEventListener("scroll", updateScrollButton, { passive: true });
scrollBottomButton.addEventListener("click", () => scrollMessages(true));
fileForm.addEventListener("submit", (event) => event.preventDefault());
uploadTrigger.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", stageSelectedFiles);
dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("drop-active");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drop-active"));
dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("drop-active");
  stageFiles(event.dataTransfer?.files);
});
adminUserForm.addEventListener("submit", createAdminUser);
actionValidateForm.addEventListener("submit", validateActionDraft);
usagePeriodFilters.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-period]");
  if (!button || button.dataset.period === state.usagePeriod) return;
  state.usagePeriod = button.dataset.period;
  await loadUsage(state.usageUserId);
});

let selectedConversationProfileId = "maid";

const conversationProfileLabels = {
  maid: "薇拉(Vera)",
  trainee: "薇达(Veda)",
  imouto: "小墨(Ember)",
};

function openNewConversationPicker() {
  selectConversationProfile("maid");
  newConversationModal.hidden = false;
  newConversationConfirm.focus();
}

function closeNewConversationPicker() {
  newConversationModal.hidden = true;
  showPendingEvolutionUpdateNotice();
}

function selectConversationProfile(profileId) {
  selectedConversationProfileId = profileId;
  const available = isConversationProfileAvailable(profileId);
  for (const choice of newConversationChoices) {
    choice.setAttribute("aria-selected", String(choice.dataset.profileId === profileId));
  }
  selectedProfileName.textContent = conversationProfileLabels[profileId] || "角色";
  selectedProfileState.textContent = available ? "可创建" : "建设中";
  selectedProfileState.dataset.available = String(available);
  selectedProfileNotice.textContent = available ? "" : "~ 该角色会话正在施工中 (ง •̀_•́)ง ~";
  newConversationConfirm.disabled = !available;
}

function isConversationProfileAvailable(profileId) {
  return profileId === "maid";
}

async function createSelectedConversation() {
  if (!isConversationProfileAvailable(selectedConversationProfileId)) return;
  newConversationConfirm.disabled = true;
  try {
    await createNewConversation(selectedConversationProfileId);
    closeNewConversationPicker();
  } finally {
    newConversationConfirm.disabled = false;
  }
}

async function createNewConversation(profileId = "maid") {
  closeSymbiosisWorkspace({ reload: false });
  clearMeetingSelection();
  const created = await api("/conversations", {
    method: "POST",
    body: JSON.stringify({ title: "新会话", profile_id: profileId }),
  });
  state.conversationId = created.conversation_id;
  state.assistantActorsByConversation[created.conversation_id] = assistantActorForConversation(created);
  title.textContent = created.title || "新会话";
  messageList.innerHTML = `<p class="empty">新会话已创建。</p>`;
  if (isCompactViewport()) closeDrawers();
  await loadConversations();
  if (state.user?.can_approve) {
    await Promise.all([
      loadApprovals(),
      loadUsage(),
      loadTasks(),
      window.HermiScheduledJobs.load(),
      loadConversationContext(),
      loadProfiles(),
      loadMeetingPresets(),
      loadBrainStatus(),
      loadPromptBindings(),
      loadCapabilities(),
    ]);
  } else {
    await Promise.all([loadConversationContext(), loadCapabilities()]);
  }
}

async function refresh() {
  try {
    state.user = await api("/me");
    applyInterfaceLocale(state.user.locale || "auto");
    document.body.dataset.auth = "ok";
    document.body.dataset.role = state.user.role || "";
    setConnectionState(true);
    accountMenuButton.hidden = false;
    tokenForm.hidden = true;
    if (!isCompactViewport()) setPanelOpen("conversations", true);
    toggleOwnerPanels(Boolean(state.user.can_approve));
    const ownerTasks = state.user.can_approve
      ? [
          loadApprovals(),
          loadUsers(),
          loadUsage(),
          loadTasks(),
          loadConversationContext(),
          loadProfiles(),
          loadMeetingPresets(),
          loadBrainStatus(),
          loadPromptBindings(),
          loadCapabilities(),
          loadRooms(),
        ]
      : [loadConversationContext(), loadCapabilities()];
    await loadConversations();
    await Promise.allSettled([loadFiles(), loadMySummary(), loadAccountNotices(), window.HermiScheduledJobs.load(), loadApprovals(), ...ownerTasks]);
    showUsageGuideIfNeeded();
    void checkEvolutionUpdates();
  } catch (error) {
    if (state.token && error instanceof TypeError) {
      setConnectionState(false);
      return;
    }
    state.user = null;
    document.body.dataset.auth = "bad";
    document.body.dataset.role = "";
    toggleOwnerPanels(false);
    setConnectionState(false);
    accountMenuButton.hidden = true;
    accountMenu.hidden = true;
    tokenForm.hidden = false;
  }
}

async function loadConversations() {
  const data = await api("/conversations");
  state.assistantActorsByConversation = Object.fromEntries(
    data.conversations.map((conversation) => [
      conversation.conversation_id,
      assistantActorForConversation(conversation),
    ]),
  );
  let initialConversation = null;
  if (!state.initialConversationSelectionDone) {
    state.initialConversationSelectionDone = true;
    initialConversation = data.conversations.find(
      (conversation) => isHermiConversation(conversation) && !isOtherConversation(conversation)
    ) || data.conversations[0];
    if (!state.roomId && !state.conversationId && initialConversation) {
      state.conversationId = initialConversation.conversation_id;
      if (!state.symbiosisOpen) title.textContent = conversationDisplayTitle(initialConversation);
    }
  }
  const current = data.conversations.find((conversation) => conversation.conversation_id === state.conversationId);
  if (current && !state.symbiosisOpen) title.textContent = conversationDisplayTitle(current);
  if (hasActiveInlineConversationRename()) return;
  const otherConversations = data.conversations.filter(isOtherConversation);
  const hermiConversations = data.conversations.filter(
    (conversation) => isHermiConversation(conversation) && !isOtherConversation(conversation)
  );
  const apiConversations = data.conversations.filter(
    (conversation) => !isHermiConversation(conversation) && !isOtherConversation(conversation)
  );
  renderProfileConversationGroups(hermiConversations);
  renderConversationSection(otherConversationList, otherConversations);
  renderConversationSection(apiConversationList, apiConversations);
  if (!data.conversations.length) {
    messageList.innerHTML = `<p class="empty">新建会话，或直接在下方发消息。</p>`;
  }
  if (initialConversation && state.conversationId === initialConversation.conversation_id) {
    await loadMessages();
  }
}

function hasActiveInlineConversationRename() {
  return Boolean(document.querySelector(".conversation-item.is-renaming .conversation-rename-input"));
}

function isHermiConversation(conversation) {
  return (conversation.channel || "hermi-native") === "hermi-native";
}

function isOtherConversation(conversation) {
  return Boolean(
    state.user?.can_approve
      && isHermiConversation(conversation)
      && conversation.owner_user_id
      && conversation.owner_user_id !== state.user.user_id
  );
}

function conversationDisplayTitle(conversation) {
  return conversationTitleWithoutProfile(conversation);
}

function conversationSidebarTitle(conversation) {
  if (isOtherConversation(conversation)) {
    const username = String(conversation?.owner_display_name || conversation?.owner_user_id || "").trim();
    const role = String(conversation?.target_profile || conversation?.profile_name || "").trim();
    return [username, role].filter(Boolean).join(" ");
  }
  return conversationTitleWithoutProfile(conversation);
}

function conversationTitleWithoutProfile(conversation) {
  const rawTitle = String(conversation?.title || "新会话").trim() || "新会话";
  const role = String(conversation?.target_profile || conversation?.profile_name || "默认人格").trim() || "默认人格";
  if (rawTitle.startsWith(`${role} · `)) return rawTitle.slice(role.length + 3).trim() || "新会话";
  if (rawTitle.startsWith(`${role} `)) return rawTitle.slice(role.length).trim() || "新会话";
  return rawTitle;
}

function renderProfileConversationGroups(conversations) {
  hermiConversationGroups.innerHTML = "";
  if (!conversations.length) {
    hermiConversationGroups.innerHTML = `<p class="nav-empty">暂无会话</p>`;
    return;
  }
  const groups = new Map();
  for (const conversation of conversations) {
    const profile = String(conversation.target_profile || conversation.profile_name || "默认人格").trim() || "默认人格";
    if (!groups.has(profile)) groups.set(profile, []);
    groups.get(profile).push(conversation);
  }
  for (const [profile, profileConversations] of groups) {
    const group = document.createElement("section");
    group.className = "nav-profile-group";
    const heading = document.createElement("h3");
    heading.className = "nav-section-title";
    heading.textContent = profile;
    const list = document.createElement("div");
    list.className = "nav-section-list";
    renderConversationSection(list, profileConversations, { titleFor: conversationTitleWithoutProfile });
    group.append(heading, list);
    hermiConversationGroups.append(group);
  }
}

function renderConversationSection(target, conversations, { titleFor = conversationSidebarTitle } = {}) {
  target.innerHTML = "";
  if (!conversations.length) {
    target.innerHTML = `<p class="nav-empty">暂无</p>`;
    return;
  }
  for (const conversation of conversations) {
    const displayTitle = titleFor(conversation);
    const item = document.createElement("div");
    item.className = `conversation-item${conversation.conversation_id === state.conversationId ? " active" : ""}`;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = displayTitle;
    button.className = `conversation-open ${conversation.conversation_id === state.conversationId ? "active" : ""}`.trim();
    button.addEventListener("click", () => selectConversation(conversation));
    const rename = document.createElement("button");
    rename.type = "button";
    rename.className = "conversation-rename";
    rename.textContent = "改";
    rename.setAttribute("aria-label", `改名会话 ${displayTitle}`);
    rename.title = "改名";
    rename.addEventListener("click", (event) => {
      event.stopPropagation();
      startInlineConversationRename(conversation, item, button, actions);
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "conversation-delete";
    remove.textContent = "删除";
    remove.setAttribute("aria-label", `删除会话 ${displayTitle}`);
    remove.title = "删除";
    remove.addEventListener("click", async (event) => {
      event.stopPropagation();
      if (!(await confirmAction({ title: "删除会话", message: `删除会话「${displayTitle}」？` }))) return;
      await api(`/conversations/${conversation.conversation_id}`, { method: "DELETE" });
      if (state.conversationId === conversation.conversation_id) {
        state.conversationId = null;
        title.textContent = "Hermi";
        messageList.innerHTML = `<p class="empty">新建会话，或直接在下方发消息。</p>`;
      }
      await loadConversations();
    });
    const actions = document.createElement("div");
    actions.className = "conversation-item-actions";
    if (!isOtherConversation(conversation)) actions.append(rename);
    actions.append(remove);
    item.append(button, actions);
    target.append(item);
  }
}

async function selectConversation(conversation) {
  closeSymbiosisWorkspace({ reload: false });
  clearMeetingSelection();
  state.conversationId = conversation.conversation_id;
  title.textContent = conversationDisplayTitle(conversation);
  syncComposerState();
  if (isCompactViewport()) closeDrawers();
  await loadMessages();
  await loadConversations();
  await loadConversationContext();
}

function clearMeetingSelection() {
  window.HermiMeetingState.clear(state);
  fileForm.hidden = false;
  messageInput.placeholder = uiText("send_message", "给 Hermi 发消息");
}

async function startNewMeeting() {
  if (!state.user?.can_approve) {
    await showInfoNotice({
      title: "会议功能测试中",
      message: "~会议功能测试中~ (´• ω •`) 现在只对 Owner 开放哦。",
    });
    return;
  }
  closeSymbiosisWorkspace({ reload: false });
  state.roomId = null;
  state.meetingRunId = null;
  meetingForm.reset();
  meetingName.value = "会议室";
  meetingMode.value = "auto_single";
  meetingRounds.value = "1";
  meetingPermission.value = "smart";
  meetingPanelHeading.textContent = "新会议";
  meetingSave.textContent = "创建会议室";
  meetingRunControls.hidden = true;
  syncMeetingModeControl();
  loadMeetingMembers();
  switchRightPanelView("meeting");
  setPanelOpen("approvals", true);
}

async function loadRooms() {
  if (!state.user?.can_approve) {
    roomList.innerHTML = "";
    return;
  }
  const data = await window.HermiMeetingAPI.listRooms(api);
  roomList.innerHTML = "";
  if (!(data.rooms || []).length) {
    roomList.innerHTML = `<p class="nav-empty">暂无</p>`;
    return;
  }
  for (const room of data.rooms) {
    const item = document.createElement("div");
    item.className = "conversation-item room-item";
    const button = document.createElement("button");
    button.type = "button";
    button.className = `room-open ${room.room_id === state.roomId ? "active" : ""}`.trim();
    button.textContent = room.name || "会议室";
    button.addEventListener("click", () => selectRoom(room.room_id));
    const rename = document.createElement("button");
    rename.type = "button";
    rename.className = "conversation-rename";
    rename.textContent = "改";
    rename.addEventListener("click", (event) => {
      event.stopPropagation();
      startInlineRoomRename(room, item, rename, remove);
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "conversation-delete";
    remove.setAttribute("aria-label", `删除会议室 ${room.name || "会议室"}`);
    remove.addEventListener("click", async (event) => {
      event.stopPropagation();
      if (!(await confirmAction({ title: "删除会议室", message: `删除会议室“${room.name || "会议室"}”？` }))) return;
      await api(`/rooms/${room.room_id}`, { method: "DELETE" });
      if (state.roomId === room.room_id) {
        clearMeetingSelection();
        title.textContent = "Hermi";
        messageList.innerHTML = `<p class="empty">新建会话，或直接在下方发消息。</p>`;
      }
      await loadRooms();
    });
    item.append(button, rename, remove);
    roomList.append(item);
  }
}

function startInlineConversationRename(conversation, item, button, actions) {
  if (item.querySelector(".conversation-rename-input")) return;

  const input = document.createElement("input");
  input.type = "text";
  input.className = "conversation-rename-input";
  input.value = conversation.title || "";
  input.maxLength = 120;
  input.setAttribute("aria-label", "重命名会话");

  const save = document.createElement("button");
  save.type = "button";
  save.className = "conversation-rename-save";
  save.textContent = "✓";
  save.title = "保存";
  save.setAttribute("aria-label", "保存会话名称");

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "conversation-rename-cancel";
  cancel.textContent = "×";
  cancel.title = "取消";
  cancel.setAttribute("aria-label", "取消重命名");

  const restore = () => {
    item.classList.remove("is-renaming");
    input.remove();
    save.remove();
    cancel.remove();
    button.hidden = false;
    actions.hidden = false;
  };
  const commit = async () => {
    const nextTitle = input.value.trim();
    if (!nextTitle) {
      input.focus();
      return;
    }
    save.disabled = true;
    try {
      await api(`/conversations/${conversation.conversation_id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: nextTitle }),
      });
      restore();
      await loadConversations();
    } finally {
      save.disabled = false;
    }
  };

  save.addEventListener("click", commit);
  cancel.addEventListener("click", restore);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    }
    if (event.key === "Escape") restore();
  });
  item.classList.add("is-renaming");
  button.hidden = true;
  actions.hidden = true;
  item.append(input, save, cancel);
  input.focus();
  input.select();
}

function startInlineRoomRename(room, item, renameButton, removeButton) {
  if (item.querySelector(".conversation-rename-input")) return;
  const roomButton = item.querySelector(".room-open");

  const input = document.createElement("input");
  input.type = "text";
  input.className = "conversation-rename-input";
  input.value = room.name || "";
  input.maxLength = 120;
  input.setAttribute("aria-label", "重命名会议室");

  const save = document.createElement("button");
  save.type = "button";
  save.className = "conversation-rename-save";
  save.textContent = "✓";
  save.title = "保存";
  save.setAttribute("aria-label", "保存会议室名称");

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "conversation-rename-cancel";
  cancel.textContent = "×";
  cancel.title = "取消";
  cancel.setAttribute("aria-label", "取消重命名");

  const restore = () => {
    item.classList.remove("is-renaming");
    input.remove();
    save.remove();
    cancel.remove();
    renameButton.hidden = false;
    removeButton.hidden = false;
    if (roomButton) roomButton.hidden = false;
  };
  const commit = async () => {
    const nextName = input.value.trim();
    if (!nextName) {
      input.focus();
      return;
    }
    save.disabled = true;
    try {
      await api(`/rooms/${room.room_id}`, { method: "PATCH", body: JSON.stringify({ name: nextName }) });
      await loadRooms();
      if (state.roomId === room.room_id) title.textContent = nextName;
    } finally {
      save.disabled = false;
    }
  };

  save.addEventListener("click", commit);
  cancel.addEventListener("click", restore);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    }
    if (event.key === "Escape") restore();
  });
  item.classList.add("is-renaming");
  if (roomButton) roomButton.hidden = true;
  renameButton.hidden = true;
  removeButton.hidden = true;
  item.append(input, save, cancel);
  input.focus();
  input.select();
}

async function selectRoom(roomId) {
  clearMeetingSelection();
  state.conversationId = null;
  state.roomId = roomId;
  fileForm.hidden = true;
  messageInput.placeholder = uiText("meeting_topic", "输入会议议题");
  const room = await window.HermiMeetingAPI.getRoom(api, roomId);
  title.textContent = room.name || "会议室";
  await Promise.all([loadRooms(), loadMeetingPanel(room), loadRoomRun(room)]);
  switchRightPanelView("meeting");
  if (isCompactViewport()) closeDrawers();
}

async function loadMeetingMembers(selectedIds = null) {
  const data = await api("/profiles");
  const selected = selectedIds ? new Set(selectedIds) : new Set((data.profiles || []).map((item) => item.profile_id));
  meetingMemberList.innerHTML = "";
  for (const profile of data.profiles || []) {
    const label = document.createElement("label");
    label.className = "meeting-member-option";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = profile.profile_id;
    input.checked = selected.has(profile.profile_id);
    if (profile.profile_id === "maid") {
      input.checked = true;
      input.disabled = true;
    }
    const text = document.createElement("span");
    text.textContent = `${profile.display_name || profile.name} · ${profile.model || "未配置模型"}${profile.profile_id === "maid" ? " · 主持" : ""}`;
    label.append(input, text);
    meetingMemberList.append(label);
  }
}

async function loadMeetingPanel(room = null) {
  if (!room && state.roomId) room = await api(`/rooms/${state.roomId}`);
  if (!room) {
    await loadMeetingMembers();
    return;
  }
  meetingPanelHeading.textContent = room.name || "会议室";
  meetingName.value = room.name || "会议室";
  meetingMode.value = room.mode || "auto_single";
  meetingRounds.value = room.max_turns || 2;
  meetingPermission.value = room.permission_level || "smart";
  meetingSave.textContent = "保存会议设置";
  syncMeetingModeControl();
  await loadMeetingMembers((room.members || []).map((item) => String(item.agent_id || "").replace(/^profile:/, "")));
}

function selectedMeetingProfiles() {
  return Array.from(meetingMemberList.querySelectorAll('input[type="checkbox"]'))
    .filter((input) => input.checked)
    .map((input) => input.value);
}

async function saveMeetingRoom(event) {
  event.preventDefault();
  const profiles = selectedMeetingProfiles();
  const participants = profiles.filter((id) => id !== "maid");
  if (meetingMode.value === "pair_review" && participants.length !== 2) {
    meetingRunStatus.textContent = "双人挑错需要恰好两名非主持 AI。";
    meetingRunControls.hidden = false;
    return;
  }
  const payload = {
    name: meetingName.value.trim() || "会议室",
    mode: meetingMode.value,
    permission_level: meetingPermission.value,
    history_policy: "adaptive",
    max_turns: meetingMode.value === "auto_single" ? 1 : Number(meetingRounds.value || 2),
  };
  let room;
  if (state.roomId) {
    room = await api(`/rooms/${state.roomId}`, { method: "PATCH", body: JSON.stringify(payload) });
    const detail = await api(`/rooms/${state.roomId}`);
    const current = new Set((detail.members || []).map((item) => String(item.agent_id || "").replace(/^profile:/, "")));
    for (const profileId of profiles) {
      if (!current.has(profileId)) {
        await api(`/rooms/${state.roomId}/members`, {
          method: "POST",
          body: JSON.stringify({ agent_id: `profile:${profileId}`, role: profileId === "maid" ? "host" : "participant" }),
        });
      }
    }
    for (const profileId of current) {
      if (profileId !== "maid" && !profiles.includes(profileId)) {
        await api(`/rooms/${state.roomId}/members/profile:${profileId}`, { method: "DELETE" });
      }
    }
  } else {
    room = await api("/rooms", { method: "POST", body: JSON.stringify(payload) });
    state.roomId = room.room_id;
    for (const profileId of participants) {
      await api(`/rooms/${room.room_id}/members`, {
        method: "POST",
        body: JSON.stringify({ agent_id: `profile:${profileId}`, role: "participant" }),
      });
    }
  }
  await selectRoom(room.room_id);
  setPanelOpen("approvals", true);
}

async function submitMeetingTopic() {
  const topic = messageInput.value.trim();
  if (!topic || !state.roomId) return;
  messageInput.value = "";
  autosizeComposer();
  const room = await api(`/rooms/${state.roomId}`);
  messageList.innerHTML = "";
  messageList.append(messageBubble("user", topic, Date.now() / 1000, []));
  const run = await api(`/rooms/${state.roomId}/workflows`, {
    method: "POST",
    body: JSON.stringify({
      mode: room.mode,
      topic,
      max_turns: room.mode === "auto_single" ? 1 : room.max_turns,
      background: true,
    }),
  });
  state.meetingRunId = run.run_id;
  meetingRunControls.hidden = false;
  await pollMeetingRun();
}

async function loadRoomRun(room = null) {
  if (!room && state.roomId) room = await api(`/rooms/${state.roomId}`);
  const run = room?.latest_run;
  if (!run) {
    state.meetingRunId = null;
    messageList.innerHTML = `<p class="empty">输入议题后开始会议。</p>`;
    meetingRunControls.hidden = true;
    return;
  }
  state.meetingRunId = run.run_id;
  meetingRunControls.hidden = false;
  await renderMeetingRun(run);
}

async function renderMeetingRun(run) {
  const steps = await window.HermiMeetingAPI.getSteps(api, run.run_id);
  syncMeetingMessages(run, steps.steps || []);
  meetingRunStatus.textContent = formatMeetingRunStatus(run, steps.steps || []);
  window.HermiMeetingUI.syncRunButtons(run, { stop: meetingStop, resume: meetingResume, cancel: meetingCancel });
  scrollMessages();
}

function formatMeetingRunStatus(run, steps) {
  return window.HermiMeetingUI.runStatus(run, steps);
}

function syncMeetingMessages(run, steps) {
  const viewKey = `meeting:${run.run_id}`;
  if (messageList.dataset.viewKey !== viewKey) {
    messageList.replaceChildren();
    messageList.dataset.viewKey = viewKey;
  }
  appendMessageOnce(
    `${viewKey}:topic`,
    "user",
    run.topic || "会议议题",
    run.created_at,
    [],
    currentUserActor(),
  );
  for (const step of steps) {
    const actor = step.actor || { actor_id: step.agent_id || "system", display_name: step.role || "会议成员", actor_type: "ai", avatar: "" };
    if (Array.isArray(step.trace) && step.trace.length && !messageList.querySelector(`[data-trace-for="${step.step_id}"]`)) {
      window.HermiTraceUI.appendTraceTime(messageList, step.step_id, step.created_at, messageTime);
      const panel = renderTracePanel(step.trace, true, { messageId: step.step_id });
      panel.dataset.traceFor = step.step_id;
      messageList.append(panel);
    }
    const stepBubble = appendMessageOnce(
      `${viewKey}:step:${step.step_id}`,
      step.role === "error" ? "system" : "assistant",
      step.content,
      step.created_at,
      [],
      actor,
    );
    if (Array.isArray(step.trace) && step.trace.length) stepBubble?.querySelector(".message-time-divider")?.remove();
  }
}

async function pollMeetingRun() {
  if (!state.meetingRunId || !state.roomId) return;
  const runId = state.meetingRunId;
  const run = await api(`/workflow-runs/${runId}`);
  if (runId !== state.meetingRunId) return;
  await renderMeetingRun(run);
  if (run.status === "running") {
    state.meetingPoll = window.setTimeout(pollMeetingRun, 800);
  }
}

async function changeMeetingRunState(action) {
  if (!state.meetingRunId) return;
  const run = await window.HermiMeetingAPI.changeRunState(api, state.meetingRunId, action);
  await renderMeetingRun(run);
  if (run.status === "running") pollMeetingRun();
}

async function loadMessages(options = {}) {
  if (!state.conversationId) {
    messageList.innerHTML = `<p class="empty">新建会话，或直接在下方发消息。</p>`;
    return;
  }
  const conversationId = state.conversationId;
  const requestSequence = ++state.messageLoadSequence;
  const data = await api(`/conversations/${conversationId}/messages`);
  if (requestSequence !== state.messageLoadSequence) return;
  if (state.conversationId !== conversationId) return;
  const viewKey = `conversation:${conversationId}`;
  if (messageList.dataset.viewKey !== viewKey) {
    messageList.replaceChildren();
    messageList.dataset.viewKey = viewKey;
  }
  for (const message of data.messages) {
    if (isUploadSystemMessage(message)) continue;
    reconcilePersistedUserMessage(message, viewKey);
    const trace = messageTrace(message);
    const presentationRole = presentationRoleForMessage(message);
    const completesInflightRun = messageCompletesInflightRun(message, conversationId);
    if (completesInflightRun) {
      markConversationFinalized(conversationId);
      delete state.inflightByConversation[conversationId];
    }
    let tracePanel = trace.length ? messageList.querySelector(`[data-trace-for="${message.message_id}"]`) : null;
    if (trace.length && !tracePanel) {
      const liveTrace = window.HermiTraceUI.reconcileLiveTrace(messageList, message.message_id);
      window.HermiTraceUI.appendTraceTime(messageList, message.message_id, message.created_at, messageTime);
      tracePanel = liveTrace || renderTracePanel(trace, true, { messageId: message.message_id, ...messageTraceTiming(message) });
      tracePanel.dataset.traceFor = message.message_id;
      replaceTraceLines(tracePanel, trace);
      setTracePanelTiming(tracePanel, messageTraceTiming(message));
      if (!tracePanel.parentElement) messageList.append(tracePanel);
    }
    const splitParts = qqSplitParts(message);
    if (splitParts.length > 1) {
      for (const [index, part] of splitParts.entries()) {
        appendMessageOnce(
          `${viewKey}:${message.message_id}:${index}`,
          presentationRole,
          part,
          message.created_at,
          messageAttachments(message),
          actorForMessage(message),
        );
      }
      continue;
    }
    const bubble = appendMessageOnce(
      `${viewKey}:${message.message_id}`,
      presentationRole,
      message.content,
      message.created_at,
      messageAttachments(message),
      actorForMessage(message),
    );
    if (tracePanel) {
      bubble?.querySelector(".message-time-divider")?.remove();
      arrangeTraceForAssistant(message.message_id, bubble, actorForMessage(message));
    } else if (completesInflightRun) {
      finalizeTraceForAssistant(message.message_id, message);
    }
  }
  await loadActiveRun();
  renderInflightForCurrentConversation();
  if (!options.preserveScroll) scrollMessages();
}

function traceCompletesInflightRun(message, conversationId) {
  const inflight = state.inflightByConversation[conversationId];
  if (!inflight || message?.role !== "assistant") return false;
  // Hermes API history can contain progress/intermediate assistant records.
  // They are not the final event for Hermi's active SSE request.
  if (message?.source_channel === "hermes-api") return false;
  const finishedAt = Number(message.created_at || 0) * 1000;
  const startedAt = Number(inflight.startedAt || 0);
  return Boolean(finishedAt && (!startedAt || finishedAt >= startedAt - 1000));
}

function messageCompletesInflightRun(message, conversationId) {
  return traceCompletesInflightRun(message, conversationId);
}

async function loadActiveRun() {
  if (!state.conversationId) return;
  if (state.activeRunPoll) {
    window.clearTimeout(state.activeRunPoll);
    state.activeRunPoll = null;
  }
  const conversationId = state.conversationId;
  if (isConversationFinalized(conversationId)) return;
  const data = await api(`/conversations/${conversationId}/runs/active`);
  if (state.conversationId !== conversationId) return;
  if (!data.run) {
    if (!state.activeSend || state.activeSend.conversationId !== conversationId) {
      delete state.inflightByConversation[conversationId];
    }
    return;
  }
  if (isConversationFinalized(conversationId)) return;
  const existing = state.inflightByConversation[conversationId] || {};
  state.inflightByConversation[conversationId] = {
    ...existing,
    runId: data.run.run_id,
    pendingId: existing.pendingId || data.run.run_id,
    content: existing.content || "",
    startedAt: Number(data.run.created_at || Date.now() / 1000) * 1000,
    trace: existing.trace?.length ? existing.trace : runTrace(data.run),
  };
  state.activeRunPoll = window.setTimeout(() => {
    if (state.conversationId === conversationId) refreshActiveRunState(conversationId);
  }, 1200);
}

async function refreshActiveRunState(conversationId) {
  if (!conversationId || state.conversationId !== conversationId) return;
  try {
    await loadActiveRun();
    renderInflightForCurrentConversation();
  } catch {
    updateScrollButton();
  }
}

async function uploadSelectedFile(event) {
  event?.preventDefault();
  const file = fileInput.files?.[0];
  if (!file) return;
  uploadTrigger.textContent = "…";
  uploadTrigger.disabled = true;
  if (!state.conversationId) {
    const created = await api("/conversations", {
      method: "POST",
      body: JSON.stringify({ title: file.name.slice(0, 24) || "文件上传" }),
    });
    state.conversationId = created.conversation_id;
  }
  const form = new FormData();
  form.append("upload", file);
  form.append("conversation_id", state.conversationId);
  form.append("visibility", "private");
  try {
    await api("/files", { method: "POST", body: form });
    fileInput.value = "";
    await Promise.all([loadFiles(), loadMessages(), loadConversations(), state.user?.can_approve ? loadUsage() : Promise.resolve()]);
  } catch (error) {
    showFileUploadError(error);
    throw error;
  } finally {
    uploadTrigger.textContent = "+";
    uploadTrigger.disabled = false;
  }
}

function stageSelectedFiles(event) {
  event?.preventDefault();
  stageFiles(fileInput.files);
  fileInput.value = "";
}

function canUploadFiles() {
  if (state.user?.role === "owner") return true;
  const media = state.user?.permissions?.media;
  const mode = typeof media === "object" && media ? media.mode : media;
  return mode !== "deny" && mode !== "owner_only" && mode !== "approval";
}

function showFileUploadError(error = null) {
  const detail = String(error?.message || "");
  void showInfoNotice({
    title: "文件上传未完成",
    message: detail.includes("permission_approval_required:media")
      ? "文件上传需要 Owner 审批，目前不能上传。"
      : "文件上传已被 Owner 禁止。",
  });
}

function stageFiles(fileListLike) {
  const files = Array.from(fileListLike || []);
  if (!files.length) return;
  if (!canUploadFiles()) {
    showFileUploadError();
    return;
  }
  state.pendingFiles.push(...files);
  renderPendingFiles();
}

function renderPendingFiles() {
  fileList.innerHTML = "";
  for (const file of state.pendingFiles) {
    const item = fileCard(fileToPendingAttachment(file), { compact: true });
    item.classList.add("pending-file");
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "chip-delete";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `移除文件 ${file.name}`);
    remove.addEventListener("click", () => {
      state.pendingFiles = state.pendingFiles.filter((pending) => pending !== file);
      renderPendingFiles();
    });
    item.append(remove);
    fileList.append(item);
  }
}

async function uploadPendingFiles() {
  if (!state.pendingFiles.length) return [];
  uploadTrigger.textContent = "…";
  uploadTrigger.disabled = true;
  try {
    const uploaded = [];
    for (const file of state.pendingFiles) {
      const form = new FormData();
      form.append("upload", file);
      form.append("conversation_id", state.conversationId);
      form.append("visibility", "private");
      uploaded.push(await api("/files", { method: "POST", body: form }));
    }
    state.pendingFiles = [];
    renderPendingFiles();
    await Promise.all([loadFiles(), loadConversations(), state.user?.can_approve ? loadUsage() : Promise.resolve()]);
    return uploaded;
  } catch (error) {
    showFileUploadError(error);
    throw error;
  } finally {
    uploadTrigger.textContent = "+";
    uploadTrigger.disabled = false;
  }
}

async function loadFiles() {
  await api("/files");
}

async function deleteFile(fileId) {
  await api(`/files/${fileId}`, { method: "DELETE" });
  await loadFiles();
}

function renderPendingUser(content, attachments = []) {
  const pendingId = `pending-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  messageList.querySelector(".empty")?.remove();
  const pending = messageBubble("user pending-user", content, Date.now() / 1000, attachments);
  pending.dataset.pendingId = pendingId;
  messageList.append(pending);
  scrollMessages();
  return pendingId;
}

function markUserSent(pendingId, messageId = "") {
  const pending = messageList.querySelector(`[data-pending-id="${pendingId}"]`);
  if (!pending) return;
  pending.classList.remove("pending-user");
  pending.removeAttribute("data-pending-id");
  if (messageId) pending.dataset.messageKey = `conversation:${state.conversationId}:${messageId}`;
}

function reconcilePersistedUserMessage(message, viewKey) {
  if (message.role !== "user") return;
  const inflight = state.inflightByConversation[state.conversationId];
  if (!inflight || !inflight.pendingId) return;
  const actorId = String(message.actor?.actor_id || "");
  if (actorId && actorId !== String(state.user?.user_id || "")) return;
  if (Number(message.created_at || 0) * 1000 < Number(inflight.startedAt || 0) - 5000) return;
  const key = `${viewKey}:${message.message_id}`;
  window.HermiMessageUI.reconcilePendingMessage(messageList, inflight.pendingId, key);
}

function setSendingState(isSending) {
  sendButton.textContent = isSending ? uiText("stop", "停止") : uiText("send", "发送");
  sendButton.classList.toggle("danger", Boolean(isSending));
  uploadTrigger.disabled = Boolean(isSending);
}

function isCurrentConversationSending() {
  return Boolean(
    (state.activeSend && state.activeSend.conversationId === state.conversationId)
    || state.inflightByConversation[state.conversationId]
  );
}

function syncComposerState() {
  setSendingState(isCurrentConversationSending());
}

function cancelActiveSend() {
  const active = state.activeSend;
  const conversationId = active?.conversationId || state.conversationId;
  if (!conversationId) return;
  fetch(`/conversations/${conversationId}/runs/cancel`, {
    method: "POST",
    headers: { Authorization: `Bearer ${state.token}` },
  }).finally(() => {
    delete state.inflightByConversation[conversationId];
    syncComposerState();
  });
  active?.controller?.abort();
}

function markPendingFailed(pendingId, error) {
  const pending = messageList.querySelector(`[data-pending-id="${pendingId}"]`);
  if (!pending) return;
  pending.className = "message assistant failed";
  pending.textContent = `发送失败：${error.message || error}`;
}

function markPendingCancelled(pendingId) {
  const pending = messageList.querySelector(`[data-pending-id="${pendingId}"]`);
  if (!pending) return;
  pending.className = "message assistant failed";
  pending.textContent = "已停止。";
}

async function recoverBackgroundSend(pendingId, error) {
  await new Promise((resolve) => window.setTimeout(resolve, 900));
  try {
    await loadMessages({ preserveScroll: true });
    await loadConversations();
    markUserSent(pendingId);
    setConnectionState(true);
  } catch {
    markUserSent(pendingId);
    setConnectionState(true);
  }
}

async function refreshVisibleState() {
  if (!state.token) return;
  syncComposerState();
  try {
    if (state.conversationId) await loadMessages({ preserveScroll: true });
    await loadConversations();
    await window.HermiScheduledJobs.load();
    if (state.symbiosisOpen) await loadSymbiosisWorkspace();
    await loadMySummary();
    await loadAccountNotices();
    if (state.user?.can_approve) {
      await Promise.all([
        loadApprovals(),
        loadUsage(state.usageUserId),
        loadTasks(),
        loadConversationContext(),
        loadCapabilities(),
      ]);
    } else {
      await loadApprovals();
      await Promise.all([loadConversationContext(), loadCapabilities()]);
    }
  } catch {
    updateScrollButton();
  }
}

async function sendMessageStream(conversationId, content, files = [], signal = null, capabilityId = "") {
  const response = await fetch(`/conversations/${conversationId}/messages/stream`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${state.token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ content, attachments: files.map(fileToMessageAttachment), capability_id: capabilityId }),
    signal,
  });
  if (!response.ok) throw new Error(await responseErrorMessage(response));
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalPayload = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";
    for (const rawEvent of events) {
      const parsed = parseSse(rawEvent);
      if (!parsed) continue;
      if ((parsed.event === "thought" || parsed.event === "tool") && !isConversationFinalized(conversationId)) {
        const content = parsed.data?.content || parsed.data?.status || "";
        rememberInflightTrace(conversationId, parsed.event, content);
        if (state.conversationId === conversationId) renderThoughtPanel(content, parsed.event);
      }
      if (parsed.event === "status") {
        const inflight = state.inflightByConversation[conversationId];
        if (inflight) {
          if (parsed.data?.run_id) inflight.runId = parsed.data.run_id;
          const traceStartedAt = Number(parsed.data?.trace_started_at || 0) * 1000;
          if (traceStartedAt) inflight.startedAt = traceStartedAt;
          if (state.conversationId === conversationId) renderInflightForCurrentConversation();
        }
      }
      if (parsed.event === "final") {
        finalPayload = parsed.data;
        markConversationFinalized(conversationId);
        removeFinalReplyEchoTrace(conversationId, finalPayload?.assistant);
      }
    }
  }
  return finalPayload || {};
}

function renderInflightForCurrentConversation() {
  if (isConversationFinalized(state.conversationId)) return;
  const inflight = state.inflightByConversation[state.conversationId];
  if (!inflight) return;
  const trace = Array.isArray(inflight.trace) ? inflight.trace : [];
  const panel = messageList.querySelector(".thought-panel.live-thought-panel");
  if (panel) {
    replaceTraceLines(panel, trace);
    return;
  }
  const startedAt = Number(inflight.startedAt || Date.now());
  window.HermiTraceUI.appendTraceTime(messageList, "", startedAt / 1000, messageTime, true);
  const livePanel = renderTracePanel(trace, false, { live: true, startedAt });
  messageList.append(livePanel);
  arrangeTraceForAssistant("", null, defaultAssistantActor());
}

function runTrace(run) {
  return (run.events || [])
    .filter((item) => item.event === "thought" || item.event === "tool")
    .map((item) => ({ event: item.event, content: item.data?.content || item.data?.status || "" }))
    .filter((item) => item.content && !isInternalActionTrace(item.content));
}

function isQuotaSendError(error) {
  return String(error?.message || error || "").includes("本额度窗口已超额");
}

function rememberInflightTrace(conversationId, event, content) {
  if (isConversationFinalized(conversationId)) return;
  const inflight = state.inflightByConversation[conversationId];
  if (!inflight || !content || isInternalActionTrace(content)) return;
  if (!Array.isArray(inflight.trace)) inflight.trace = [];
  inflight.trace.push({ event, content });
}

function normalizedTraceText(content) {
  return String(content || "").trim().replace(/\s+/g, " ");
}

function removeFinalReplyEchoTrace(conversationId, assistant) {
  const finalText = normalizedTraceText(assistant?.content);
  if (!finalText) return;
  const inflight = state.inflightByConversation[conversationId];
  if (!inflight?.trace) return;
  inflight.trace = inflight.trace.filter((item) => normalizedTraceText(item.content) !== finalText);
  if (state.conversationId !== conversationId) return;
  const panel = messageList.querySelector(".thought-panel.live-thought-panel");
  if (!panel) return;
  if (!inflight.trace.length) {
    panel.remove();
    messageList.querySelector("[data-live-trace-time]")?.remove();
    messageList.querySelector("[data-live-trace-actor]")?.remove();
    return;
  }
  replaceTraceLines(panel, inflight.trace);
}

function finalizeTraceForAssistant(messageId, assistant, existingPanel = null) {
  if (!messageId) return null;
  const trace = messageTrace(assistant);
  let panel = existingPanel || window.HermiTraceUI.reconcileLiveTrace(messageList, messageId);
  if (!panel && trace.length) {
    window.HermiTraceUI.appendTraceTime(messageList, messageId, assistant?.created_at, messageTime);
    panel = renderTracePanel(trace, true, { messageId, ...messageTraceTiming(assistant) });
    panel.dataset.traceFor = messageId;
    messageList.append(panel);
  }
  if (!panel) return null;
  if (!trace.length) {
    panel.remove();
    messageList.querySelector(`[data-trace-time-for="${messageId}"]`)?.remove();
    messageList.querySelector(`[data-trace-actor-for="${messageId}"]`)?.remove();
    return null;
  }
  panel.dataset.traceFor = messageId;
  replaceTraceLines(panel, trace);
  window.HermiTraceUI.appendTraceTime(messageList, messageId, assistant?.created_at, messageTime);
  setTracePanelTiming(panel, messageTraceTiming(assistant));
  return panel;
}

function parseSse(rawEvent) {
  const lines = rawEvent.split("\n");
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLine = lines.find((line) => line.startsWith("data:"));
  if (!eventLine || !dataLine) return null;
  try {
    return {
      event: eventLine.slice(6).trim(),
      data: JSON.parse(dataLine.slice(5).trim()),
    };
  } catch {
    return null;
  }
}

function renderThoughtPanel(content, event = "thought", conversationId = state.conversationId) {
  if (!content || isInternalActionTrace(content) || isConversationFinalized(conversationId)) return;
  state.traceRenderQueue.push({ content, event, conversationId });
  if (state.traceRenderFrame) return;
  state.traceRenderFrame = window.requestAnimationFrame(flushThoughtRenderQueue);
}

function flushThoughtRenderQueue() {
  const queued = state.traceRenderQueue.splice(0);
  state.traceRenderFrame = null;
  const activeQueued = queued.filter((item) => (
    item.conversationId === state.conversationId
    && !isConversationFinalized(item.conversationId)
  ));
  if (!activeQueued.length) return;
  const wasNearBottom = isMessageListNearBottom();
  let panel = messageList.querySelector(".thought-panel.live-thought-panel");
  if (!panel) {
    const inflight = state.inflightByConversation[state.conversationId];
    const startedAt = Number(inflight?.startedAt || Date.now());
    panel = createTracePanel(false, { live: true, startedAt });
    window.HermiTraceUI.appendTraceTime(messageList, "", startedAt / 1000, messageTime, true);
    messageList.append(panel);
  }
  const fragment = document.createDocumentFragment();
  for (const item of activeQueued) {
    window.HermiTraceUI.appendUniqueLine(panel, item.event, item.content, () => {
      const line = document.createElement("div");
      line.className = `thought-line ${item.event === "tool" ? "tool" : "thought"}`;
      line.innerHTML = renderMarkdown(translateThoughtContent(item.content));
      return line;
    });
  }
  panel.querySelector(".thought-lines").append(fragment);
  arrangeTraceForAssistant("", null, defaultAssistantActor());
  if (wasNearBottom) scrollMessages(true);
  else updateScrollButton();
}

function collapseThoughtPanel() {
  const panel = messageList.querySelector(".thought-panel.live-thought-panel");
  if (panel) {
    panel.classList.add("collapsed");
    panel.classList.remove("live-thought-panel");
  }
}

function clearThoughtPanel() {
  messageList.querySelector(".thought-panel.live-thought-panel")?.remove();
  messageList.querySelector("[data-live-trace-time]")?.remove();
  messageList.querySelector("[data-live-trace-actor]")?.remove();
}

function arrangeTraceForAssistant(messageId, bubble) {
  const panelSelector = messageId
    ? `[data-trace-for="${messageId}"]`
    : ".thought-panel.live-thought-panel";
  const timeSelector = messageId
    ? `[data-trace-time-for="${messageId}"]`
    : "[data-live-trace-time]";
  const panel = messageList.querySelector(panelSelector);
  const time = messageList.querySelector(timeSelector);
  if (!panel || !time) return;
  // Legacy trace labels were independently created and moved by polling.
  // They caused the professional view's actor name to flash above the trace.
  messageList.querySelector(messageId
    ? `[data-trace-actor-for="${messageId}"]`
    : "[data-live-trace-actor]")?.remove();
  if (state.chatMode === "chat" && bubble?.classList.contains("assistant")) {
    const contentWrap = bubble.querySelector(".message-content");
    const body = bubble.querySelector(".message-body");
    if (contentWrap && body) {
      // Keep the chat transcript readable: time, actor, thought, then reply.
      // The avatar/name live in the bubble, so bind the trace below that row.
      bubble.classList.add("trace-bound");
      body.before(panel);
      bubble.before(time);
      return;
    }
  }
  if (bubble?.classList.contains("assistant")) {
    bubble.classList.remove("trace-bound");
    bubble.before(time, panel);
  } else {
    messageList.append(time, panel);
  }
}

function createTracePanel(collapsed = false, options = {}) {
  const panel = document.createElement("article");
  panel.className = `thought-panel${collapsed ? " collapsed" : ""}${options.live ? " live-thought-panel" : ""}`;
  if (options.messageId) panel.dataset.messageId = options.messageId;
  panel.innerHTML = `<button type="button" class="thought-toggle">思考过程</button><div class="thought-lines"></div>`;
  panel.querySelector(".thought-toggle").addEventListener("click", () => panel.classList.toggle("collapsed"));
  setTracePanelTiming(panel, options);
  return panel;
}

function renderTracePanel(trace, collapsed = true, options = {}) {
  const panel = createTracePanel(collapsed, options);
  replaceTraceLines(panel, trace);
  return panel;
}

function messageTraceTiming(message) {
  const metadata = messageMetadata(message);
  return {
    startedAt: Number(metadata.trace_started_at || 0) * 1000 || 0,
    finishedAt: Number(metadata.trace_finished_at || 0) * 1000 || 0,
  };
}

function traceDurationText(startedAt, finishedAt = 0) {
  if (!startedAt) return "00:00";
  const elapsed = Math.max(0, Math.floor(((finishedAt || Date.now()) - startedAt) / 1000));
  return `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(elapsed % 60).padStart(2, "0")}`;
}

function setTracePanelTiming(panel, { startedAt = 0, finishedAt = 0 } = {}) {
  if (!panel) return;
  const start = Number(startedAt || panel.dataset.traceStartedAt || 0);
  const finish = Number(finishedAt || panel.dataset.traceFinishedAt || 0);
  if (start) panel.dataset.traceStartedAt = String(start);
  if (finish) panel.dataset.traceFinishedAt = String(finish);
  const toggle = panel.querySelector(".thought-toggle");
  if (toggle) toggle.textContent = `思考过程（${traceDurationText(start, finish)}）`;
}

function refreshLiveTraceDurations() {
  for (const panel of document.querySelectorAll(".thought-panel.live-thought-panel")) setTracePanelTiming(panel);
}

function replaceTraceLines(panel, trace) {
  const signature = traceRenderSignature(trace);
  if (panel.dataset.traceRenderSignature === signature) return;
  const lines = panel.querySelector(".thought-lines");
  lines.replaceChildren();
  for (const item of trace) {
    if (isInternalActionTrace(item.content)) continue;
    window.HermiTraceUI.appendUniqueLine(panel, item.event, item.content || "", () => {
      const line = document.createElement("div");
      line.className = `thought-line ${item.event === "tool" ? "tool" : "thought"}`;
      line.innerHTML = renderMarkdown(translateThoughtContent(item.content || ""));
      return line;
    });
  }
  panel.dataset.traceRenderSignature = signature;
}

function traceRenderSignature(trace) {
  return JSON.stringify((trace || [])
    .filter((item) => !isInternalActionTrace(item?.content))
    .map((item) => ({ event: item?.event || "", content: item?.content || "" })));
}

function translateThoughtContent(content) {
  const raw = String(content || "").trim();
  if (!raw) return "";
  const normalized = raw.replace(/\s+/g, " ");
  const match = normalized.match(/^([A-Za-z0-9_.-]+):\s*(?:tool\.)?(running|started|completed|failed|progress)(?:\s*-\s*(.+))?$/i);
  if (match) {
    const toolName = translateToolName(match[1]);
    const phase = {
      running: "开始",
      started: "开始",
      completed: "完成",
      failed: "失败",
      progress: "进行中",
    }[match[2].toLowerCase()] || "更新";
    const detail = String(match[3] || "").trim();
    return detail ? `${phase}：${toolName}（${detail}）` : `${phase}：${toolName}`;
  }
  return normalized
    .replace(/\btool\.started\b/gi, "工具开始")
    .replace(/\btool\.completed\b/gi, "工具完成")
    .replace(/\btool\.failed\b/gi, "工具失败")
    .replace(/\btool\.progress\b/gi, "工具进行中");
}

function translateToolName(name) {
  const key = String(name || "").toLowerCase();
  const names = {
    web_search: "联网搜索",
    web_extract: "网页提取",
    browser_navigate: "浏览器访问",
    browser_snapshot: "浏览器读取",
    browser_click: "浏览器点击",
    session_search: "会话搜索",
    terminal: "终端命令",
    skill_view: "查看技能",
    file_search: "文件搜索",
    read_file: "读取文件",
    write_file: "写入文件",
  };
  return names[key] || key.replace(/[_-]+/g, " ");
}

function animateAssistant(content, createdAt, actor = null, messageId = "", attachments = []) {
  const bubble = messageBubble("assistant typing", "", createdAt || Date.now() / 1000, attachments, actor || defaultAssistantActor());
  if (messageId) bubble.dataset.messageKey = `conversation:${state.conversationId}:${messageId}`;
  messageList.append(bubble);
  const body = bubble.querySelector(".message-body");
  let index = 0;
  const text = content || "";
  const step = () => {
    const followAssistant = isMessageListNearBottom();
    index = Math.min(index + 2, text.length);
    body.innerHTML = renderMarkdown(text.slice(0, index));
    if (followAssistant) scrollMessages(true);
    else updateScrollButton();
    if (index < text.length) {
      window.setTimeout(step, 18);
      return;
    }
    bubble.classList.remove("typing");
    bubble.classList.add("markdown-body");
    body.innerHTML = renderMarkdown(text);
  };
  step();
}

function messageBubble(role, content, createdAt, attachments = [], actor = null) {
  const bubble = document.createElement("article");
  bubble.className = `message ${role}`;
  const identity = actor || (role.includes("user") ? currentUserActor() : defaultAssistantActor());
  const line = document.createElement("div");
  line.className = "message-line";
  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = actorInitial(identity);
  avatar.title = identity.display_name || "发言者";
  const contentWrap = document.createElement("div");
  contentWrap.className = "message-content";
  const identityRow = document.createElement("div");
  identityRow.className = "message-identity";
  const displayName = document.createElement("span");
  displayName.className = "message-display-name";
  displayName.textContent = identity.display_name || "发言者";
  identityRow.append(displayName);
  const body = document.createElement("div");
  body.className = "message-body";
  if (role.includes("assistant") || role.includes("system")) {
    bubble.classList.add("markdown-body");
    body.innerHTML = renderMarkdown(content);
  } else {
    body.textContent = content;
  }
  if (attachments.length) {
    body.append(attachmentGrid(attachments));
  }
  const time = messageTime(createdAt);
  time.classList.add("message-time-divider");
  contentWrap.append(identityRow, body);
  if (!role.includes("user")) line.append(avatar);
  line.append(contentWrap);
  bubble.append(time, line);
  return bubble;
}

function appendMessageOnce(key, role, content, createdAt, attachments = [], actor = null) {
  const existing = messageList.querySelector(`[data-message-key="${key}"]`);
  const signature = messageRenderSignature(role, content, createdAt, attachments, actor);
  if (existing) {
    if (existing.dataset.renderSignature === signature) return existing;
    const refreshed = refreshMessageBubble(existing, role, content, createdAt, attachments, actor);
    refreshed.dataset.renderSignature = signature;
    return refreshed;
  }
  const bubble = messageBubble(role, content, createdAt, attachments, actor);
  bubble.dataset.messageKey = key;
  bubble.dataset.renderSignature = signature;
  messageList.append(bubble);
  return bubble;
}

function messageRenderSignature(role, content, createdAt, attachments = [], actor = null) {
  const attachmentSignature = (attachments || []).map((attachment) => ({
    file_id: attachment?.file_id || "",
    original_name: attachment?.original_name || "",
    mime_type: attachment?.mime_type || "",
    size: Number(attachment?.size || 0),
  }));
  const actorSignature = actor ? {
    actor_id: actor.actor_id || "",
    display_name: actor.display_name || "",
    actor_type: actor.actor_type || "",
  } : null;
  return JSON.stringify({
    role,
    content: String(content || ""),
    created_at: Number(createdAt || 0),
    attachments: attachmentSignature,
    actor: actorSignature,
  });
}

function refreshMessageBubble(existing, role, content, createdAt, attachments = [], actor = null) {
  const refreshed = messageBubble(role, content, createdAt, attachments, actor);
  refreshed.dataset.messageKey = existing.dataset.messageKey || "";
  existing.replaceWith(refreshed);
  return refreshed;
}

function actorForMessage(message) {
  if (message?.actor) return message.actor;
  return message?.role === "user" ? currentUserActor() : defaultAssistantActor();
}

function presentationRoleForMessage(message) {
  if (message?.role !== "user") return message?.role || "assistant";
  const actorId = String(message.actor?.actor_id || "");
  if (!state.user?.can_approve && actorId && actorId !== String(state.user?.user_id || "")) {
    return "assistant";
  }
  return "user";
}

function currentUserActor() {
  return {
    actor_id: state.user?.user_id || "owner",
    display_name: state.user?.display_name || "你",
    actor_type: "user",
    avatar: "",
  };
}

function assistantActorForConversation(conversation) {
  const profileId = String(conversation?.profile_id || "maid").trim() || "maid";
  const displayName = String(
    conversation?.target_profile
    || conversation?.profile_name
    || conversationProfileLabels[profileId]
    || "Hermi",
  ).trim() || "Hermi";
  return { actor_id: `profile:${profileId}`, display_name: displayName, actor_type: "ai", avatar: "" };
}

function defaultAssistantActor(conversationId = state.conversationId) {
  return state.assistantActorsByConversation[conversationId]
    || assistantActorForConversation({ profile_id: "maid" });
}

function actorInitial(actor) {
  const name = String(actor?.display_name || "AI").trim();
  return String(actor?.avatar || name.slice(0, 1) || "AI");
}

function fileToPendingAttachment(file) {
  return {
    original_name: file.name,
    mime: file.type || "application/octet-stream",
    size_bytes: file.size || 0,
  };
}

function fileToMessageAttachment(file) {
  return { file_id: file.file_id };
}

function messageAttachments(message) {
  try {
    const metadata = JSON.parse(message.metadata_json || "{}");
    return Array.isArray(metadata.attachments) ? metadata.attachments : [];
  } catch {
    return [];
  }
}

function messageTrace(message) {
  try {
    const metadata = JSON.parse(message.metadata_json || "{}");
    const finalText = normalizedTraceText(message.content);
    return Array.isArray(metadata.trace)
      ? metadata.trace.filter((item) => (
        !isInternalActionTrace(item?.content)
        && normalizedTraceText(item?.content) !== finalText
      ))
      : [];
  } catch {
    return [];
  }
}

function messageMetadata(message) {
  try {
    return JSON.parse(message.metadata_json || "{}");
  } catch {
    return {};
  }
}

function qqSplitParts(message) {
  if (message.role !== "assistant") return [];
  const metadata = messageMetadata(message);
  if (Array.isArray(metadata.split_parts)) {
    return metadata.split_parts.map((part) => String(part || "").trim()).filter(Boolean);
  }
  const content = String(message.content || "");
  if (content.includes("<<<QLOS_SPLIT>>>")) {
    return content.split("<<<QLOS_SPLIT>>>").map((part) => part.trim()).filter(Boolean);
  }
  return [];
}

function isUploadSystemMessage(message) {
  if (message.role !== "system") return false;
  if (!String(message.content || "").startsWith("已上传文件：")) return false;
  try {
    const metadata = JSON.parse(message.metadata_json || "{}");
    return Boolean(metadata.file_id);
  } catch {
    return true;
  }
}

function attachmentGrid(attachments) {
  const grid = document.createElement("div");
  grid.className = "attachment-grid";
  for (const attachment of attachments) {
    grid.append(fileCard(attachment));
  }
  return grid;
}

function fileCard(attachment, options = {}) {
  const item = document.createElement("span");
  item.className = options.compact ? "file-card file-card-compact" : "file-card";
  const icon = document.createElement("span");
  icon.className = "file-card-icon";
  icon.textContent = fileIcon(attachment);
  const text = document.createElement("span");
  text.className = "file-card-text";
  const name = document.createElement("span");
  name.className = "file-card-name";
  name.textContent = attachment.original_name || "文件";
  const meta = document.createElement("span");
  meta.className = "file-card-meta";
  meta.textContent = `${formatFileSize(attachment.size_bytes)} · ${fileKind(attachment.mime)}`;
  text.append(name, meta);
  item.append(icon, text);
  if (attachment.download_url) {
    item.title = "打开文件";
    item.addEventListener("click", () => openFileAttachment(attachment));
    const download = document.createElement("button");
    download.type = "button";
    download.className = "file-card-download";
    download.title = "下载文件";
    download.setAttribute("aria-label", "下载文件");
    download.textContent = "↓";
    download.addEventListener("click", (event) => {
      event.stopPropagation();
      downloadFileAttachment(attachment).catch((error) => showInfoNotice(error.message || "文件下载失败"));
    });
    item.append(download);
  }
  return item;
}

async function openFileAttachment(attachment) {
  const url = attachment.download_url || (attachment.file_id ? `/files/${attachment.file_id}/content` : "");
  if (!url) return;
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${state.token}` },
  });
  if (!response.ok) throw new Error(`文件打开失败：${response.status}`);
  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  window.open(blobUrl, "_blank", "noopener,noreferrer");
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
}

async function downloadFileAttachment(attachment) {
  const url = attachment.download_url || (attachment.file_id ? `/files/${attachment.file_id}/content` : "");
  if (!url) return;
  const response = await fetch(url, { headers: { Authorization: `Bearer ${state.token}` } });
  if (!response.ok) throw new Error(`文件下载失败：${response.status}`);
  const blobUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = attachment.original_name || "下载文件";
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
}

function fileIcon(attachment) {
  const mime = String(attachment.mime || "");
  const name = String(attachment.original_name || "").toLowerCase();
  if (mime.startsWith("image/")) return "图";
  if (name.endsWith(".pdf")) return "PDF";
  if (name.endsWith(".doc") || name.endsWith(".docx")) return "文";
  if (name.endsWith(".xls") || name.endsWith(".xlsx") || name.endsWith(".csv")) return "表";
  return "件";
}

function fileKind(mime) {
  const text = String(mime || "");
  if (!text || text === "application/octet-stream") return "文件";
  return text.split(";")[0].split("/").pop().toUpperCase();
}

function formatFileSize(value) {
  const size = Number(value || 0);
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.ceil(size / 1024)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function messageTime(createdAt) {
  const time = document.createElement("time");
  time.className = "message-meta-time";
  time.textContent = formatClock(createdAt);
  return time;
}

function formatClock(createdAt) {
  const date = createdAt ? new Date(Number(createdAt) * 1000) : new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}年${pad(date.getMonth() + 1)}月${pad(date.getDate())}日 ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function renderMarkdown(source) {
  const text = String(source || "");
  const blocks = [];
  let html = escapeHtml(text).replace(/```([a-z0-9_-]*)\n([\s\S]*?)```/gi, (_, lang, code) => {
    const index = blocks.push(`<pre><code data-lang="${lang || ""}">${code.trim()}</code></pre>`) - 1;
    return `\n@@CODE_BLOCK_${index}@@\n`;
  });
  html = renderMarkdownTables(html);
  html = html
    .replace(/^######\s+(.+)$/gm, "<h6>$1</h6>")
    .replace(/^#####\s+(.+)$/gm, "<h5>$1</h5>")
    .replace(/^####\s+(.+)$/gm, "<h4>$1</h4>")
    .replace(/^###\s+(.+)$/gm, "<h3>$1</h3>")
    .replace(/^##\s+(.+)$/gm, "<h2>$1</h2>")
    .replace(/^#\s+(.+)$/gm, "<h1>$1</h1>")
    .replace(/^---$/gm, "<hr>")
    .replace(/^>\s+(.+)$/gm, "<blockquote>$1</blockquote>")
    .replace(/^\d+\.\s+(.+)$/gm, '<li data-list="ordered">$1</li>')
    .replace(/(?:<li data-list="ordered">[\s\S]*?<\/li>\n?)+/g, (items) => `<ol>${items}</ol>`)
    .replace(/^\s*[-*]\s+(.+)$/gm, "<li>$1</li>")
    .replace(/(<li>[\s\S]*?<\/li>)(?!\n<li>)/g, "<ul>$1</ul>")
    .replace(/~~(.+?)~~/g, "<del>$1</del>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/\n{2,}/g, "</p><p>")
    .replace(/\n/g, "<br>");
  html = `<p>${html}</p>`
    .replace(/<p>(\s*<(h[1-6]|ul|pre|table)[\s\S]*?<\/\2>\s*)<\/p>/g, "$1")
    .replace(/<p><\/p>/g, "");
  blocks.forEach((block, index) => {
    html = html.replace(`@@CODE_BLOCK_${index}@@`, block);
  });
  return html;
}

function renderMarkdownTables(html) {
  return html.replace(/(^\|.+\|\n^\|[\s:-]+\|(?:[\s:-]*\|)+\n(?:^\|.+\|\n?)+)/gm, (tableText) => {
    const rows = tableText.trim().split("\n");
    const header = rows[0].split("|").slice(1, -1).map((cell) => cell.trim());
    const body = rows.slice(2).map((row) => row.split("|").slice(1, -1).map((cell) => cell.trim()));
    const headHtml = `<thead><tr>${header.map((cell) => `<th>${cell}</th>`).join("")}</tr></thead>`;
    const bodyHtml = `<tbody>${body
      .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
      .join("")}</tbody>`;
    return `<table>${headHtml}${bodyHtml}</table>`;
  });
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function scrollMessages(force = true) {
  if (force) messageList.scrollTop = messageList.scrollHeight;
  updateScrollButton();
}

function isMessageListNearBottom() {
  return messageList.scrollHeight - messageList.scrollTop - messageList.clientHeight < 96;
}

function updateScrollButton() {
  const distance = messageList.scrollHeight - messageList.scrollTop - messageList.clientHeight;
  scrollBottomButton.hidden = distance < 96;
}

async function loadApprovals() {
  const data = await api("/approvals");
  const canDecide = Boolean(state.user?.can_approve);
  approvalList.dataset.scope = canDecide ? "all" : "mine";
  approvalList.innerHTML = "";
  if (!data.approvals.length) {
    approvalList.innerHTML = `<p class="empty">${canDecide ? "暂无审批。" : "你还没有提交审批。"}</p>`;
    return;
  }
  for (const approval of data.approvals) {
    const row = document.createElement("article");
    row.className = "approval-item";
    const meta = document.createElement("div");
    meta.className = "approval-meta";
    const timestamps = [];
    if (approval.created_at) timestamps.push(`提交 ${formatClock(approval.created_at)}`);
    if (approval.decided_at) timestamps.push(`处理 ${formatClock(approval.decided_at)}`);
    meta.textContent = [
      approvalStatusLabel(approval.status),
      approval.action_type || "action",
      approval.risk_level || "risk",
      ...timestamps,
    ].join(" · ");
    const summary = document.createElement("div");
    summary.className = "approval-summary";
    summary.textContent = approval.summary;
    row.append(meta, summary);
    if (approval.status === "pending" && canDecide) {
      const actions = document.createElement("div");
      actions.className = "approval-actions";
      const approve = document.createElement("button");
      approve.type = "button";
      approve.textContent = "批准";
      const deny = document.createElement("button");
      deny.type = "button";
      deny.textContent = "拒绝";
      deny.className = "danger";
      const decide = (decision) => {
        approve.disabled = true;
        deny.disabled = true;
        decideApproval(approval.approval_id, decision);
      };
      approve.addEventListener("click", () => decide("once"));
      deny.addEventListener("click", () => decide("deny"));
      actions.append(approve, deny);
      row.append(actions);
    } else if (canDecide) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "approval-delete";
      remove.textContent = "×";
      remove.setAttribute("aria-label", `删除审批记录 ${approval.summary}`);
      remove.addEventListener("click", () => deleteApproval(approval.approval_id));
      row.append(remove);
    }
    approvalList.append(row);
  }
}

async function decideApproval(approvalId, decision) {
  await api(`/approvals/${approvalId}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
  await Promise.all([
    loadApprovals(),
    loadUsage(),
    loadTasks(),
    window.HermiScheduledJobs.load(),
    loadConversationContext(),
    loadProfiles(),
    loadMeetingPresets(),
    loadBrainStatus(),
    loadPromptBindings(),
    state.conversationId ? loadMessages() : Promise.resolve(),
  ]);
}

async function deleteApproval(approvalId) {
  await api(`/approvals/${approvalId}`, { method: "DELETE" });
  await loadApprovals();
}

function toggleOwnerPanels(show) {
  adminSection.hidden = !show;
  usageSection.hidden = !show;
  taskSection.hidden = !show;
  contextSection.hidden = false;
  profileSection.hidden = !show;
  profileNameSection.hidden = !show;
  meetingPresetSection.hidden = !show;
  brainSection.hidden = !show;
  promptSection.hidden = !show;
  capabilitySection.hidden = false;
  actionValidateForm.hidden = !show;
  approvalPanel.dataset.owner = show ? "true" : "false";
  settingsToolsButton.hidden = false;
  temporaryToolsButton.hidden = !show;
  meetingToolsButton.hidden = !show;
  newMeetingButton.hidden = false;
  newMeetingButton.disabled = false;
  newMeetingButton.title = show ? "新建会议" : "测试中，暂未向朋友开放";
  roomNavSection.hidden = !show;
  otherConversationSection.hidden = !show;
  apiConversationSection.hidden = !show;
  if (!state.user) switchRightPanelView("approvals");
}

function isInternalActionTrace(content) {
  return String(content || "").includes("<<<HERMI_ACTION");
}

async function createAdminUser(event) {
  event.preventDefault();
  const userId = adminUserId.value.trim();
  if (!userId) return;
  const role = adminRole.value || "friend";
  const payload = {
    user_id: userId,
    display_name: adminDisplayName.value.trim() || userId,
    role,
    token: adminToken.value.trim(),
    quota_policy: role === "guest" ? "guest" : "friend_free",
  };
  const created = await api("/admin/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  adminUserForm.reset();
  if (created.generated_token) {
    await showInfoNotice({ title: "已创建用户", message: `用户 token：${created.generated_token}` });
  } else {
    await showInfoNotice({ title: "已创建用户", message: `用户：${created.user_id}` });
  }
  await Promise.all([loadUsers(), loadUsage(created.user_id)]);
  await window.HermiPermissionsPanel.open(created.user_id);
}

async function loadUsers() {
  const data = await api("/admin/users");
  adminUserList.innerHTML = "";
  for (const user of data.users) {
    const row = document.createElement("article");
    row.className = "admin-user-item";
    row.dataset.userId = user.user_id;
    const main = document.createElement("button");
    main.type = "button";
    main.textContent = `${user.display_name} · ${user.role} · ${user.quota_policy}`;
    main.addEventListener("click", () => loadUsage(user.user_id));
    const meta = document.createElement("div");
    meta.className = "admin-user-meta";
    meta.textContent = user.user_id;
    const permissionSummary = document.createElement("div");
    permissionSummary.className = "permission-summary";
    const permissionLabels = { chat: "对话", cron: "定时", manage_scheduled: "任务" };
    for (const [key, value] of Object.entries(user.permission_summary || {})) {
      const badge = document.createElement("span");
      badge.className = `permission-state permission-state-${value}`;
      badge.textContent = `${permissionLabels[key] || key}：${value === "allow" ? "允许" : value === "approval" ? "审批" : "禁止"}`;
      permissionSummary.append(badge);
    }
    const actions = document.createElement("div");
    actions.className = "admin-user-actions";
    const usage = document.createElement("button");
    usage.type = "button";
    usage.className = "secondary-button";
    usage.textContent = "用量";
    usage.addEventListener("click", () => loadUsage(user.user_id));
    actions.append(usage);
    if (user.role !== "owner") {
      const perms = document.createElement("button");
      perms.type = "button";
      perms.className = "secondary-button";
      perms.textContent = "权限";
      perms.addEventListener("click", () => window.HermiPermissionsPanel.open(user.user_id));
      actions.append(perms);
    }
    const info = document.createElement("button");
    info.type = "button";
    info.className = "secondary-button";
    info.textContent = "信息";
    info.addEventListener("click", () => openUserInfoModal(user));
    actions.append(info);
    if (["friend", "guest"].includes(user.role)) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "danger-button admin-user-delete";
      remove.textContent = "删除";
      remove.addEventListener("click", () => deleteAdminUser(user));
      actions.append(remove);
    }
    row.append(main, meta);
    if (permissionSummary.childElementCount) row.append(permissionSummary);
    row.append(actions);
    adminUserList.append(row);
  }
}

function approvalStatusLabel(status) {
  const labels = {
    pending: "待审批",
    executing: "执行中",
    approved: "已同意",
    denied: "已拒绝",
    failed: "执行失败",
  };
  return labels[status] || String(status || "未知状态");
}

async function deleteAdminUser(user) {
  const ok = await confirmAction({
    title: "删除用户",
    message: `确定删除 ${user.display_name || user.user_id}？这个操作不会删除历史会话，但该 token 会立刻失效。`,
    okText: "删除",
  });
  if (!ok) return;
  await api(window.HermiAdminTools.adminUserPath(user.user_id), { method: "DELETE" });
  const row = Array.from(adminUserList.querySelectorAll(".admin-user-item"))
    .find((item) => item.dataset.userId === user.user_id);
  row?.remove();
  if (state.usageUserId === user.user_id) state.usageUserId = "";
  await Promise.all([loadUsers(), loadUsage()]);
}

async function loadUsage(userId = state.usageUserId) {
  const selectedUserId = String(userId || "");
  state.usageUserId = selectedUserId;
  const requestId = ++state.usageLoadSequence;
  const query = `?period=${encodeURIComponent(state.usagePeriod)}`;
  const data = await api(selectedUserId ? `/usage/${encodeURIComponent(selectedUserId)}${query}` : `/usage${query}`);
  if (requestId !== state.usageLoadSequence) return;
  const rows = data.usage;
  const totalTokens = rows.reduce((sum, row) => sum + Number(row.total_tokens || 0), 0);
  usageTotalTokens.textContent = `当前范围 Token ${totalTokens.toLocaleString("zh-CN")}`;
  usagePeriodFilters.querySelectorAll("button[data-period]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.period === state.usagePeriod));
  });
  usageList.innerHTML = "";
  if (data.quota_window) {
    const window = data.quota_window;
    const item = document.createElement("article");
    item.className = "usage-item quota-window-summary";
    const tokenLimit = window.token_limit == null ? "不限" : window.token_limit.toLocaleString("zh-CN");
    const fileLimit = window.file_size_limit_mb == null ? "不限" : `${window.file_size_limit_mb}MB`;
    const remainingMinutes = Math.max(0, Math.ceil((window.remaining_seconds || 0) / 60));
    const remainingTokens = window.remaining_tokens == null
      ? "不限"
      : Number(window.remaining_tokens).toLocaleString("zh-CN");
    item.textContent = `当前额度窗口 ${window.window_minutes} 分钟 · Token 剩余 ${remainingTokens}/${tokenLimit} · 文件上限 ${fileLimit} · ${remainingMinutes} 分钟后重置`;
    usageList.append(item);
  }
  if (!rows.length && !data.quota_window) {
    usageList.innerHTML = `<p class="empty">暂无用量。</p>`;
    return;
  }
  for (const row of rows) {
    const item = document.createElement("article");
    item.className = "usage-item";
    item.textContent = `${row.day} · ${row.user_id} · 文本 ${row.text_messages} · 文件 ${row.file_uploads} · token ${row.total_tokens || 0}`;
    usageList.append(item);
  }
}

function contextWindowStatus(contextWindow) {
  const totalTokens = Number(contextWindow?.total_tokens || 0);
  if (!totalTokens) return "暂无 Token 数据（模型窗口未配置）";
  return `会话累计 ${totalTokens} Token（非实时上下文；模型窗口未配置）`;
}

function cacheHitRateStatus(conversationUsage) {
  const rate = conversationUsage?.cache_hit_rate;
  return rate == null ? "未报告" : `${rate}%`;
}

async function loadConversationContext() {
  if (!state.conversationId) {
    contextSummary.innerHTML = `<p class="empty">选择会话后显示上下文。</p>`;
    return;
  }
  const data = await api(`/conversations/${state.conversationId}/context`);
  const rows = [
    ["会话", data.title || data.conversation_id],
    ["来源", data.channel || "hermi-native"],
    ["目标人格", data.target_profile || "默认"],
    ["消息", `${data.message_count || 0} 条`],
    ["附件", `${data.attachment_count || 0} 个`],
    ["思考/工具事件", `${data.trace_event_count || 0} 条`],
    ["缓存命中率", cacheHitRateStatus(data.conversation_usage)],
    ["当前会话token", `${data.conversation_usage?.total_tokens || 0}`],
    ["上下文状态", contextWindowStatus(data.context_window)],
  ];
  contextSummary.innerHTML = rows
    .map(([label, value]) => `<div class="context-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");
}

async function loadProfiles({ force = false } = {}) {
  if (!state.user?.can_approve) return;
  if (!force && profileNameList.contains(document.activeElement)) return;
  const data = await api("/profiles");
  profileList.innerHTML = "";
  profileNameList.innerHTML = "";
  for (const profile of data.profiles || []) {
    profileList.append(statusCard(
      `${profile.name}${profile.is_default ? " · 默认" : ""}`,
      `${profile.adapter} · ${profile.status}`,
      profile.description || "",
    ));
    profileNameList.append(profileNameEditor(profile));
  }
}

function formatQuotaReset(remainingSeconds) {
  const seconds = Math.max(0, Number(remainingSeconds || 0));
  const days = Math.floor(seconds / 86400);
  const hours = Math.ceil((seconds % 86400) / 3600);
  if (days > 0) return `${days}天${hours ? `${hours}小时` : ""}后重置`;
  if (hours > 0) return `${hours}小时后重置`;
  return "即将重置";
}

async function loadMySummary({ force = false } = {}) {
  if (!state.user) return;
  if (!force && state.mySummaryDirty) return;
  const requestId = ++state.mySummaryLoadSequence;
  const data = await api("/my/summary");
  if (requestId !== state.mySummaryLoadSequence || (!force && state.mySummaryDirty)) return;
  state.accountSummary = data;
  accountDisplayName.textContent = data.display_name || data.user_id || "账户";
  const quota = data.quota_window || {};
  if (quota.token_limit != null) {
    const percentage = Number(quota.remaining_percent ?? 100);
    accountQuotaLabel.textContent = `剩余额度 ${percentage}%`;
    accountQuotaReset.textContent = formatQuotaReset(quota.remaining_seconds);
  } else {
    accountQuotaLabel.textContent = "剩余额度 不限";
    accountQuotaReset.textContent = "";
  }
  accountRequestQuotaButton.hidden = quota.token_limit == null;
  renderAccountSettings(data);
}

function renderAccountSettings(data) {
  accountSettingsSummary.replaceChildren();
  const appendRow = (label, value) => {
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = value;
    accountSettingsSummary.append(term, detail);
  };
  const nameTerm = document.createElement("dt");
  nameTerm.textContent = "名称";
  const nameDetail = document.createElement("dd");
  nameDetail.className = "my-display-name-editor";
  const nameInput = document.createElement("input");
  nameInput.value = data.display_name || data.user_id || "";
  nameInput.maxLength = 40;
  nameInput.setAttribute("aria-label", "修改展示名称");
  nameInput.addEventListener("input", () => { state.mySummaryDirty = true; });
  const saveName = document.createElement("button");
  saveName.type = "button";
  saveName.className = "text-button";
  saveName.textContent = "保存";
  saveName.addEventListener("click", async () => {
    const display_name = nameInput.value.trim();
    if (!display_name) return;
    saveName.disabled = true;
    try {
      const updated = await api("/my/display-name", {
        method: "PATCH",
        body: JSON.stringify({ display_name }),
      });
      state.user.display_name = updated.display_name;
      state.mySummaryDirty = false;
      await loadMySummary({ force: true });
    } finally {
      saveName.disabled = false;
    }
  });
  nameDetail.append(nameInput, saveName);
  accountSettingsSummary.append(nameTerm, nameDetail);
  const quotaTerm = document.createElement("dt");
  quotaTerm.textContent = "额度方案";
  const quotaDetail = document.createElement("dd");
  quotaDetail.className = "account-quota-policy-row";
  const quotaPolicy = document.createElement("span");
  quotaPolicy.textContent = data.quota_policy || "-";
  quotaDetail.append(quotaPolicy);
  if (data.quota_window?.token_limit != null) quotaDetail.append(accountRequestQuotaButton);
  accountSettingsSummary.append(quotaTerm, quotaDetail);
  const rows = [
    ["身份", data.role || "-"],
    ["累计会话", `${data.conversation_count || 0} 个`],
    ["累计消息", `${data.message_count || 0} 条`],
    ["累计附件", `${data.attachment_count || 0} 个`],
    ["近7日 Token", `${data.last_7_day_tokens || 0}`],
    ["累计 Token", `${data.total_tokens || 0}`],
    ["定时任务", `${data.scheduled_job_count || 0} 个`],
    ["待处理审批", `${data.pending_approval_count || 0} 条`],
  ];
  rows.forEach(([label, value]) => appendRow(label, value));
}

function toggleComposerPrivacyTooltip(open) {
  if (!composerPrivacyInfoWrap || !composerPrivacyInfo) return;
  composerPrivacyInfoWrap.classList.toggle("is-open", Boolean(open));
  composerPrivacyInfo.setAttribute("aria-expanded", String(Boolean(open)));
}

function toggleAccountMenu() {
  const willOpen = accountMenu.hidden;
  accountMenu.hidden = !willOpen;
  accountMenuButton.setAttribute("aria-expanded", String(willOpen));
  if (!willOpen) setAccountLanguageOptionsOpen(false);
  if (willOpen) void loadMySummary();
}

function closeAccountMenuOnOutsideClick(event) {
  if (accountMenu.hidden) return;
  if (accountMenu.contains(event.target) || accountMenuButton.contains(event.target)) return;
  accountMenu.hidden = true;
  accountMenuButton.setAttribute("aria-expanded", "false");
  setAccountLanguageOptionsOpen(false);
}

async function openAccountSettings() {
  accountMenu.hidden = true;
  accountMenuButton.setAttribute("aria-expanded", "false");
  setAccountLanguageOptionsOpen(false);
  await loadMySummary();
  accountSettingsModal.hidden = false;
  accountSettingsClose.focus();
}

async function requestTemporaryQuota() {
  const confirmed = await confirmAction({
    title: "申请临时额度",
    message: "提交后会请求 Owner 审批。每次批准将在当前额度窗口增加 100,000 Token。",
    confirmText: "提交申请",
    danger: false,
  });
  if (!confirmed) return;
  accountRequestQuotaButton.disabled = true;
  try {
    await api("/my/quota-requests", { method: "POST" });
    await Promise.all([loadMySummary({ force: true }), loadApprovals()]);
    await showInfoNotice({ title: "已提交", message: "临时额度申请已提交，等待 Owner 审批。" });
  } finally {
    accountRequestQuotaButton.disabled = false;
  }
}

let accountLanguageCloseTimer = 0;

function isAccountLanguageOptionsOpen() {
  return accountLanguageMenu.classList.contains("is-open");
}

function clearAccountLanguageOptionsCloseTimer() {
  window.clearTimeout(accountLanguageCloseTimer);
  accountLanguageCloseTimer = 0;
}

function scheduleAccountLanguageOptionsClose() {
  clearAccountLanguageOptionsCloseTimer();
  accountLanguageCloseTimer = window.setTimeout(
    () => setAccountLanguageOptionsOpen(false),
    ACCOUNT_LANGUAGE_OPTIONS_CLOSE_DELAY_MS,
  );
}

function isPointWithinAccountLanguageRect(x, y, rect) {
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

function handleAccountLanguagePointerMove(event) {
  if (!isAccountLanguageOptionsOpen() || event.pointerType === "touch") return;
  const pointerIsInside = [accountLanguageButton, accountLanguageOptions].some((element) =>
    isPointWithinAccountLanguageRect(event.clientX, event.clientY, element.getBoundingClientRect()),
  );
  if (pointerIsInside) clearAccountLanguageOptionsCloseTimer();
  else scheduleAccountLanguageOptionsClose();
}

function positionAccountLanguageOptions() {
  if (!isAccountLanguageOptionsOpen()) return;
  const trigger = accountLanguageButton.getBoundingClientRect();
  const optionsWidth = accountLanguageOptions.offsetWidth || 112;
  const optionsHeight = accountLanguageOptions.offsetHeight || 112;
  const left = Math.min(window.innerWidth - optionsWidth - 8, trigger.right + 6);
  const top = Math.min(window.innerHeight - optionsHeight - 8, Math.max(8, trigger.top - 5));
  accountLanguageOptions.style.setProperty("--account-language-popover-x", `${Math.max(8, left)}px`);
  accountLanguageOptions.style.setProperty("--account-language-popover-y", `${top}px`);
}

function setAccountLanguageOptionsOpen(open) {
  clearAccountLanguageOptionsCloseTimer();
  accountLanguageMenu.classList.toggle("is-open", open);
  accountLanguageButton.setAttribute("aria-expanded", String(open));
  if (open) positionAccountLanguageOptions();
}

function closeAccountSettings() {
  state.mySummaryDirty = false;
  accountSettingsModal.hidden = true;
  showPendingAccountNotice();
  showPendingEvolutionUpdateNotice();
}

async function openUserInfoModal(user) {
  const userId = String(user?.user_id || "");
  if (!userId) return;
  state.editingUserProfileId = userId;
  const requestId = ++state.userProfileLoadSequence;
  userInfoTitle.textContent = `${user.display_name || userId}的信息`;
  userInfoSubtitle.textContent = `${userId} · ${user.role || "用户"}`;
  userInfoStatus.textContent = "加载中…";
  userInfoRelationship.value = "";
  userInfoPreferences.value = "";
  userInfoRecentFocus.value = "";
  userInfoModal.hidden = false;
  userInfoRelationship.focus();
  try {
    const profile = await api(`/admin/users/${encodeURIComponent(userId)}/profile`);
    if (requestId !== state.userProfileLoadSequence || state.editingUserProfileId !== userId) return;
    userInfoRelationship.value = profile.relationship || "";
    userInfoPreferences.value = profile.preferences || "";
    userInfoRecentFocus.value = profile.recent_focus || "";
    userInfoStatus.textContent = profile.revision ? "资料将在下次对话时同步给对应人格。" : "可按需填写，留空的项目不会进入对话上下文。";
  } catch (error) {
    if (requestId === state.userProfileLoadSequence) userInfoStatus.textContent = `加载失败：${error.message}`;
  }
}

function closeUserInfoModal() {
  state.editingUserProfileId = "";
  userInfoModal.hidden = true;
}

async function saveUserInfoField(field) {
  const userId = state.editingUserProfileId;
  if (!userId) return;
  const inputs = {
    relationship: userInfoRelationship,
    preferences: userInfoPreferences,
    recent_focus: userInfoRecentFocus,
  };
  const input = inputs[field];
  if (!input) return;
  const button = userInfoModal.querySelector(`[data-user-profile-field="${field}"]`);
  button.disabled = true;
  userInfoStatus.textContent = "保存中…";
  try {
    const profile = await api(`/admin/users/${encodeURIComponent(userId)}/profile/${encodeURIComponent(field)}`, {
      method: "PUT",
      body: JSON.stringify({ value: input.value.trim() }),
    });
    input.value = profile[field] || "";
    userInfoStatus.textContent = "已保存；下一条消息会同步更新后的资料。";
  } catch (error) {
    userInfoStatus.textContent = `保存失败：${error.message}`;
  } finally {
    button.disabled = false;
  }
}

function profileNameEditor(profile) {
  const item = document.createElement("div");
  item.className = "profile-name-item";
  const label = document.createElement("label");
  label.textContent = `${profile.profile_id}${profile.is_default ? "（当前默认）" : ""}`;
  const input = document.createElement("input");
  input.value = profile.display_name || profile.name || profile.profile_id;
  input.maxLength = 40;
  input.setAttribute("aria-label", `${profile.profile_id} 显示名`);
  const save = document.createElement("button");
  save.type = "button";
  save.className = "secondary-button";
  save.textContent = "保存";
  save.addEventListener("click", async () => {
    const displayName = input.value.trim();
    if (!displayName) return;
    save.disabled = true;
    try {
      await api(`/profiles/${encodeURIComponent(profile.profile_id)}`, {
        method: "PATCH",
        body: JSON.stringify({ display_name: displayName }),
      });
      await Promise.all([loadProfiles({ force: true }), loadConversations(), loadConversationContext()]);
      await showInfoNotice({ title: "人格显示名已更新", message: `${profile.profile_id} 已改名为 ${displayName}` });
    } finally {
      save.disabled = false;
    }
  });
  item.append(label, input, save);
  return item;
}

async function loadMeetingPresets() {
  if (!state.user?.can_approve) return;
  const data = await api("/meeting-presets");
  syncMeetingModeOptions(data.modes || []);
  meetingPresetList.innerHTML = "";
  for (const mode of data.modes || []) {
    meetingPresetList.append(statusCard(
      mode.label || mode.mode,
      `${mode.mode} · v${mode.rule_version || "1"}`,
      mode.description || "",
    ));
  }
}

function syncMeetingModeOptions(modes) {
  if (!Array.isArray(modes) || !modes.length) return;
  const selected = meetingMode.value;
  meetingMode.replaceChildren();
  for (const mode of modes) {
    const option = document.createElement("option");
    option.value = mode.mode;
    option.textContent = mode.label || mode.mode;
    option.dataset.ruleVersion = mode.rule_version || "1";
    option.dataset.orchestration = mode.orchestration || "fixed";
    meetingMode.append(option);
  }
  if (modes.some((mode) => mode.mode === selected)) meetingMode.value = selected;
  syncMeetingModeControl();
}

async function loadBrainStatus() {
  if (!state.user?.can_approve) return;
  const data = await api("/brain/status");
  brainStatusList.innerHTML = "";
  for (const adapter of data.adapters || []) {
    const setup = adapter.requires_setup ? "需配置" : "已预留";
    const stateText = adapter.available ? "可用" : "未接入";
    brainStatusList.append(statusCard(adapter.label || adapter.adapter_id, `${stateText} · ${setup}`, adapter.notes || adapter.endpoint || ""));
  }
}

async function loadPromptBindings() {
  if (!state.user?.can_approve) return;
  const data = await api("/prompt-bindings");
  promptBindingList.innerHTML = "";
  for (const binding of data.prompt_bindings || []) {
    const enabled = Number(binding.enabled) ? "启用" : "停用";
    promptBindingList.append(statusCard(
      binding.card_name || binding.card_id,
      `${binding.scope_type}:${binding.scope_id} · ${enabled} · 优先级 ${binding.priority}`,
      binding.card_type || "prompt card",
    ));
  }
  if (!promptBindingList.children.length) {
    promptBindingList.innerHTML = `<p class="empty">暂无绑定。</p>`;
  }
}

function statusCard(titleText, metaText, bodyText) {
  const item = document.createElement("article");
  item.className = "status-card";
  const titleLine = document.createElement("div");
  titleLine.className = "status-card-title";
  titleLine.textContent = titleText;
  const meta = document.createElement("div");
  meta.className = "status-card-meta";
  meta.textContent = metaText;
  const body = document.createElement("p");
  body.textContent = bodyText;
  item.append(titleLine, meta, body);
  return item;
}

async function loadCapabilities() {
  const data = await api("/capabilities");
  capabilityList.innerHTML = "";
  const skillCapabilities = Array.isArray(data.skill_capabilities) ? data.skill_capabilities : [];
  for (const capability of skillCapabilities) {
    const item = document.createElement("article");
    item.className = `capability-item skill-capability risk-${capability.risk_level || "medium"}`;
    const titleLine = document.createElement("div");
    titleLine.className = "capability-title";
    titleLine.textContent = capability.title || capability.capability_id;
    const meta = document.createElement("div");
    meta.className = "capability-meta";
    meta.textContent = capability.kind === "hermi_feature"
      ? `Hermi 功能：${(capability.skills || []).join("、") || "内置流程"}`
      : `建议技能：${(capability.skills || []).join("、") || "无"}`;
    const desc = document.createElement("p");
    desc.textContent = capability.description || "";
    const select = document.createElement("button");
    select.type = "button";
    select.className = "text-button capability-select-button";
    select.dataset.skillCapabilityId = capability.capability_id;
    select.dataset.skillCapabilityTitle = capability.title || capability.capability_id;
    select.textContent = state.selectedSkillCapability?.id === capability.capability_id ? "已选择" : "使用此能力";
    item.append(titleLine, meta, desc, select);
    capabilityList.append(item);
  }
  if (skillCapabilities.length) {
    const divider = document.createElement("p");
    divider.className = "capability-divider";
    divider.textContent = "系统动作（仍会按权限与审批执行）";
    capabilityList.append(divider);
  }
  const displayedCapabilities = [
    ...(data.capabilities || []).filter((capability) => !skillCapabilities.some(
      (item) => item.capability_id === capability.capability_id,
    )),
    ...(data.reserved_capabilities || []).map((capability) => ({ ...capability, reserved: true })),
  ];
  for (const capability of displayedCapabilities) {
    const item = document.createElement("article");
    item.className = `capability-item risk-${capability.risk_level || "medium"}${capability.reserved ? " reserved-capability" : ""}`;
    const titleLine = document.createElement("div");
    titleLine.className = "capability-title";
    titleLine.textContent = capability.reserved
      ? `${capability.title} · 预留能力`
      : `${capability.title} · ${capability.capability_id}`;
    const meta = document.createElement("div");
    meta.className = "capability-meta";
    const required = capability.schema?.required || [];
    meta.textContent = capability.reserved
      ? `预留 · ${capability.risk_level} · 将强制进入对应流程`
      : `${capability.risk_level} · ${capability.approval_policy} · 必填 ${required.join("、") || "无"}`;
    const desc = document.createElement("p");
    desc.textContent = capability.description || "";
    item.append(titleLine, meta, desc);
    capabilityList.append(item);
  }
}

function selectSkillCapability(id, title) {
  state.selectedSkillCapability = { id, title };
  renderSelectedSkillCapability();
  void loadCapabilities();
  messageInput.focus();
}

function clearSelectedSkillCapability() {
  state.selectedSkillCapability = null;
  renderSelectedSkillCapability();
}

function renderSelectedSkillCapability() {
  const selected = state.selectedSkillCapability;
  selectedSkillCapability.hidden = !selected;
  selectedSkillCapability.replaceChildren();
  if (!selected) return;
  const label = document.createElement("span");
  label.textContent = `正在使用：${selected.title}`;
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "icon-button selected-skill-cancel";
  cancel.title = "取消本次能力选择";
  cancel.setAttribute("aria-label", "取消本次能力选择");
  cancel.textContent = "×";
  cancel.addEventListener("click", clearSelectedSkillCapability);
  selectedSkillCapability.append(label, cancel);
}

function usageGuideStorageKey() {
  return `hermi_usage_guide_dismissed:${state.user?.user_id || ""}`;
}

function showUsageGuideIfNeeded() {
  if (!state.user || localStorage.getItem(usageGuideStorageKey()) === "1") return;
  usageGuideModal.hidden = false;
  usageGuideConfirm.focus();
}

function closeUsageGuide(dismissForever) {
  if (dismissForever && state.user) localStorage.setItem(usageGuideStorageKey(), "1");
  usageGuideModal.hidden = true;
  showPendingAccountNotice();
  showPendingEvolutionUpdateNotice();
}

async function validateActionDraft(event) {
  event.preventDefault();
  actionValidateResult.textContent = "";
  let payload;
  try {
    payload = JSON.parse(actionValidateInput.value || "{}");
  } catch {
    actionValidateResult.textContent = "JSON 格式错误。";
    actionValidateResult.dataset.state = "bad";
    return;
  }
  try {
    const result = await api("/actions/validate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    actionValidateResult.textContent = `校验通过：${result.capability_id}`;
    actionValidateResult.dataset.state = "ok";
  } catch (error) {
    actionValidateResult.textContent = `校验失败：${error.message || error}`;
    actionValidateResult.dataset.state = "bad";
  }
}

async function loadTasks() {
  const [tasksData, jobsData] = await Promise.all([api("/tasks"), api("/scheduled-jobs")]);
  taskList.innerHTML = "";
  const tasks = tasksData.tasks.slice(0, 8);
  const jobs = jobsData.scheduled_jobs.slice(0, 8);
  if (!tasks.length && !jobs.length) {
    taskList.innerHTML = `<p class="empty">暂无任务。</p>`;
    return;
  }
  for (const job of jobs) {
    const item = document.createElement("article");
    item.className = "task-item";
    item.textContent = `${job.status} · ${job.kind} · ${job.schedule} · ${job.summary}`;
    taskList.append(item);
  }
  for (const task of tasks) {
    const item = document.createElement("article");
    item.className = "task-item";
    item.textContent = `${task.status} · ${task.task_type} · ${task.title}`;
    taskList.append(item);
  }
}

function initializePanels() {
  if (isCompactViewport()) {
    closeDrawers();
    return;
  }
  conversationPanel.classList.add("open");
  approvalPanel.classList.remove("open");
  document.body.setAttribute("data-left-open", "true");
  document.body.setAttribute("data-right-open", "false");
  drawerBackdrop.hidden = true;
}

function toggleDrawer(which) {
  togglePanel(which);
}

function togglePanel(which) {
  const target = which === "approvals" ? approvalPanel : conversationPanel;
  if (target.classList.contains("open")) {
    setPanelOpen(which, false);
    return;
  }
  setPanelOpen(which, true);
}

function openDrawer(which) {
  setPanelOpen(which, true);
}

function setPanelOpen(which, open) {
  const target = which === "approvals" ? approvalPanel : conversationPanel;
  if (isCompactViewport()) {
    closeDrawers();
  }
  target.classList.toggle("open", open);
  if (which === "approvals") {
    document.body.setAttribute("data-right-open", open ? "true" : "false");
  } else {
    document.body.setAttribute("data-left-open", open ? "true" : "false");
  }
  drawerBackdrop.hidden = !isCompactViewport() || !document.querySelector(".panel.open");
}

function closeDrawers() {
  conversationPanel.classList.remove("open");
  approvalPanel.classList.remove("open");
  document.body.setAttribute("data-left-open", "false");
  document.body.setAttribute("data-right-open", "false");
  drawerBackdrop.hidden = true;
}

function confirmAction({ title: confirmHeading = "确认", message = "确认执行？", confirmText = "确认", cancelText = "取消", danger = true } = {}) {
  return new Promise((resolve) => {
    state.pendingConfirm = resolve;
    confirmTitle.textContent = confirmHeading;
    confirmMessage.textContent = message;
    confirmOk.textContent = confirmText;
    confirmCancel.hidden = !cancelText;
    confirmCancel.textContent = cancelText || "取消";
    confirmOk.classList.toggle("danger-button", danger);
    confirmOk.classList.toggle("primary-button", !danger);
    confirmModal.hidden = false;
    confirmOk.focus();
  });
}

function resolveConfirm(value) {
  if (!state.pendingConfirm) return;
  const resolve = state.pendingConfirm;
  state.pendingConfirm = null;
  confirmModal.hidden = true;
  confirmCancel.hidden = false;
  confirmCancel.textContent = "取消";
  confirmOk.textContent = "确认";
  confirmOk.classList.add("danger-button");
  confirmOk.classList.remove("primary-button");
  resolve(Boolean(value));
}

function showInfoNotice({ title, message }) {
  return confirmAction({ title, message, confirmText: "知道啦", cancelText: "", danger: false });
}

function openTemporaryTools() {
  switchRightPanelView("temporary");
  setPanelOpen("approvals", true);
}

function openSettingsTools() {
  switchRightPanelView("settings");
  setPanelOpen("approvals", true);
}

function switchRightPanelView(view) {
  const selected = ["approvals", "settings", "temporary", "meeting"].includes(view) ? view : "approvals";
  approvalToolsView.hidden = selected !== "approvals";
  settingsToolsModal.hidden = selected !== "settings";
  temporaryToolsModal.hidden = selected !== "temporary";
  meetingToolsView.hidden = selected !== "meeting";
  approvalToolsButton.classList.toggle("active", selected === "approvals");
  settingsToolsButton.classList.toggle("active", selected === "settings");
  temporaryToolsButton.classList.toggle("active", selected === "temporary");
  meetingToolsButton.classList.toggle("active", selected === "meeting");
  const labels = {
    approvals: ["Approvals", uiText("approvals", "审批")],
    settings: ["Settings", uiText("settings", "设置")],
    temporary: ["Management", uiText("management", "管理")],
    meeting: ["Meeting", uiText("meeting", "会议")],
  };
  rightPanelEyebrow.textContent = labels[selected][0];
  rightPanelTitle.textContent = labels[selected][1];
  syncRightPanelTabNavigation();
}

function syncRightPanelTabNavigation() {
  const overflow = rightPanelTabs.scrollWidth > rightPanelTabs.clientWidth + 4;
  rightPanelTabPrev.hidden = !overflow;
  rightPanelTabNext.hidden = !overflow;
  rightPanelTabPrev.disabled = !overflow || rightPanelTabs.scrollLeft <= 2;
  rightPanelTabNext.disabled = !overflow || rightPanelTabs.scrollLeft + rightPanelTabs.clientWidth >= rightPanelTabs.scrollWidth - 2;
}

function isCompactViewport() {
  return window.matchMedia("(max-width: 980px)").matches;
}

function setDisplayMode(mode) {
  state.chatMode = mode === "professional" ? "professional" : "chat";
  localStorage.setItem("hermi_chat_mode", state.chatMode);
  document.body.dataset.chatMode = state.chatMode;
  displayModeToggle.textContent = state.chatMode === "professional"
    ? uiText("professional", "Professional")
    : uiText("chat", "Chat");
  if (state.chatMode === "chat") {
    messageList.querySelectorAll(".trace-actor-label").forEach((label) => label.remove());
  }
  if (state.conversationId) void loadMessages({ preserveScroll: true });
}

function autosizeComposer() {
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 132)}px`;
}

function isMobileComposer() {
  return window.matchMedia("(max-width: 720px), (pointer: coarse)").matches;
}

async function api(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: {
        Authorization: `Bearer ${state.token}`,
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...(options.headers || {}),
      },
    });
  } catch (error) {
    if (state.token) {
      setConnectionState(false);
    }
    throw error;
  }
  if (!response.ok) throw new Error(await responseErrorMessage(response));
  return response.json();
}

async function responseErrorMessage(response) {
  let detail = "";
  try {
    const body = await response.json();
    detail = typeof body.detail === "string" ? body.detail : "";
  } catch {}
  const messages = {
    "permission_denied:chat": "消息权限已被禁止，请联系 Owner 调整权限。",
    "permission_approval_required:chat": "这条消息需要 Owner 审批。",
    "token_quota_exceeded": "",
    "text_quota_exceeded": "消息额度已用完，请等待额度窗口重置或联系 Owner。",
    "file_quota_exceeded": "文件额度或文件大小已超过限制。",
    "permission_denied:media": "没有文件权限。",
    "permission_denied:manage_scheduled": "没有管理定时任务的权限。",
    "conversation_forbidden": "不能操作其他用户的会话。",
  };
  if (detail === "token_quota_exceeded") {
    const retryAfter = Number(response.headers.get("Retry-After") || 0);
    const resetHint = retryAfter > 0 ? `约 ${formatQuotaReset(retryAfter)}` : "额度窗口重置后";
    return `本额度窗口已超额，${resetHint}恢复。本次消息未发送，避免继续累积额度欠账；可等待恢复或联系 Owner 调整额度。`;
  }
  return messages[detail] || detail || `请求失败（${response.status}）`;
}

refresh();
window.setInterval(refreshLiveTraceDurations, 1000);
window.setInterval(() => {
  if (!document.hidden && state.user) refreshVisibleState();
}, 4000);
