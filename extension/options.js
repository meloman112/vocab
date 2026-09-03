const host = document.getElementById('host');
const token = document.getElementById('token');
const status = document.getElementById('status');

chrome.storage.sync.get(['host', 'token']).then((saved) => {
  host.value = saved.host ?? '';
  token.value = saved.token ?? '';
});

document.getElementById('save').addEventListener('click', async () => {
  await chrome.storage.sync.set({
    host: host.value.replace(/\/+$/, ''),
    token: token.value.trim(),
  });
  status.textContent = 'Сохранено';
});
