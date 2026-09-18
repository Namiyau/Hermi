(function () {
  const listRooms = (request) => request("/rooms");
  const getRoom = (request, roomId) => request(`/rooms/${roomId}`);
  const updateRoom = (request, roomId, payload) => request(`/rooms/${roomId}`, { method: "PATCH", body: JSON.stringify(payload) });
  const deleteRoom = (request, roomId) => request(`/rooms/${roomId}`, { method: "DELETE" });
  const changeRunState = (request, runId, action) => request(`/workflow-runs/${runId}/${action}`, { method: "POST" });
  const getRun = (request, runId) => request(`/workflow-runs/${runId}`);
  const getSteps = (request, runId) => request(`/workflow-runs/${runId}/steps`);
  window.HermiMeetingAPI = { changeRunState, deleteRoom, getRoom, getRun, getSteps, listRooms, updateRoom };
})();
