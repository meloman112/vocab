// Chrome зовёт фон service worker-ом, Firefox — обычным скриптом; в манифесте
// объявлены оба ключа, и каждый браузер читает свой.
// В Firefox промисы возвращает browser.*, в Chrome — chrome.*; одна строка
// вместо двух сборок расширения.
const api = globalThis.browser ?? globalThis.chrome;

// Хост и токен лежат в storage, а не в коде: иначе токен уехал бы
// в git вместе с расширением.
const MENU_ID = 'vocab-add';

api.runtime.onInstalled.addListener(async () => {
  api.contextMenus.create({
    id: MENU_ID,
    title: 'vocab: добавить «%s»',
    contexts: ['selection'],
  });

  // Без адреса и токена расширение бесполезно, а страницу настроек
  // в about:addons ещё надо найти. Открываем её сами — но только пока
  // настройки пусты, иначе она лезла бы при каждом обновлении.
  const { host, token } = await api.storage.sync.get(['host', 'token']);
  if (!host || !token) api.runtime.openOptionsPage();
});

api.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== MENU_ID || !info.selectionText) return;

  const { host, token } = await api.storage.sync.get(['host', 'token']);
  if (!host || !token) {
    notify('vocab', 'Не заполнены настройки расширения');
    return;
  }

  try {
    const response = await fetch(`${host}/words`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Token': token },
      body: JSON.stringify({ word: info.selectionText }),
    });
    const body = await response.json();
    // 422 — слово не принято, detail написан для человека.
    if (!response.ok) throw new Error(body.detail ?? `API вернул ${response.status}`);
    notify('vocab', body.entries.map((e) => `${e.lemma} — ${e.translation}`).join('\n'));
  } catch (error) {
    // Молча проглоченная ошибка здесь означала бы слова, которые
    // «вроде добавил», а их нет.
    notify('vocab: ошибка', String(error.message));
  }
});

function notify(title, message) {
  api.notifications.create({
    type: 'basic',
    iconUrl: 'icon.png',
    title,
    message,
  });
}
