// Хост и токен лежат в chrome.storage, а не в коде: иначе токен уехал бы
// в git вместе с расширением.
const MENU_ID = 'vocab-add';

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: MENU_ID,
    title: 'vocab: добавить «%s»',
    contexts: ['selection'],
  });
});

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== MENU_ID || !info.selectionText) return;

  const { host, token } = await chrome.storage.sync.get(['host', 'token']);
  if (!host || !token) {
    notify('vocab', 'Не заполнены настройки расширения');
    return;
  }

  try {
    const response = await fetch(`${host}/words`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Token': token },
      body: JSON.stringify({ word: info.selectionText, source_url: info.pageUrl }),
    });
    if (!response.ok) throw new Error(`API вернул ${response.status}`);
    const card = await response.json();
    notify('vocab', card.created ? `✅ ${card.word}` : `уже есть: ${card.word}`);
  } catch (error) {
    // Молча проглоченная ошибка здесь означала бы слова, которые
    // «вроде добавил», а их нет.
    notify('vocab: ошибка', String(error.message));
  }
});

function notify(title, message) {
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icon.png',
    title,
    message,
  });
}
