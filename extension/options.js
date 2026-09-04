const api = globalThis.browser ?? globalThis.chrome;

const host = document.getElementById('host');
const token = document.getElementById('token');
const status = document.getElementById('status');

api.storage.sync.get(['host', 'token']).then((saved) => {
  host.value = saved.host ?? '';
  token.value = saved.token ?? '';
});

document.getElementById('save').addEventListener('click', async () => {
  await api.storage.sync.set({
    host: host.value.replace(/\/+$/, ''),
    token: token.value.trim(),
  });
  status.textContent = 'Сохранено';
});
