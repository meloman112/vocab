import { initData } from './lib/telegram';

// Вне Telegram страница притворяется стандартным 404 nginx: снаружи не
// должно быть видно, что здесь приложение. Код и стили мини-аппа лежат в
// отдельном чанке и без initData даже не скачиваются.
if (initData) {
  void import('./boot');
} else {
  document.title = '404 Not Found';
  document.body.innerHTML = '<center><h1>404 Not Found</h1></center><hr><center>nginx</center>';
}
