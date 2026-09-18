(function () {
  function messageKey(conversationId, messageId) {
    return `conversation:${conversationId}:${messageId}`;
  }

  function hasMessage(messageList, key) {
    return Boolean(key && messageList.querySelector(`[data-message-key="${key}"]`));
  }

  function reconcilePendingMessage(messageList, pendingId, key) {
    const pending = messageList.querySelector(`[data-pending-id="${pendingId}"]`);
    const existing = key ? messageList.querySelector(`[data-message-key="${key}"]`) : null;
    if (existing && pending && existing !== pending) {
      pending.remove();
      return existing;
    }
    if (!pending) return existing;
    pending.classList.remove("pending-user");
    pending.removeAttribute("data-pending-id");
    if (key) pending.dataset.messageKey = key;
    return pending;
  }

  window.HermiMessageUI = { hasMessage, messageKey, reconcilePendingMessage };
})();
