(function () {
  const defaults = { roomId: null, meetingRunId: null, meetingPoll: null };
  function attach(state) {
    for (const [key, value] of Object.entries(defaults)) {
      if (!(key in state)) state[key] = value;
    }
    return state;
  }
  function clear(state) {
    state.roomId = null;
    state.meetingRunId = null;
    if (state.meetingPoll) window.clearTimeout(state.meetingPoll);
    state.meetingPoll = null;
  }
  window.HermiMeetingState = { attach, clear };
})();
