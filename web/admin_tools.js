(function () {
  function adminUserPath(userId) {
    return `/admin/users/${encodeURIComponent(userId)}`;
  }

  window.HermiAdminTools = {
    adminUserPath,
  };
})();
