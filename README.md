# guide-proxy

Статичное зеркало `wardogs.zone/ru` для `guide.dendich.online` (калькуляторы, база данных, вики, новости).

Скачано: 341 файл, ~92 МБ (HTML всех /ru страниц + _next JS/CSS + шрифты + brand-картинки + i18n).

## Структура

```
guide-proxy/
  main.py       FastAPI: статика + clean URLs (/ru/..., /ru/calculators/rewards/...)
  static/       зеркало сайта
    ru/         все страницы /ru (калькуляторы, база, вики...)
    _next/      JS-чанки, CSS, шрифты, медиа
    i18n/       ru.js (303 КБ)
    brand/      фоновые картинки
    manifest.webmanifest, favicon, icon.png, apple-icon.png
    x/script.js
  Dockerfile
  requirements.txt
```

## Deploy (Bothost)

1. Отдельный Docker-проект из этой папки.
2. Порт: `8237`.
3. Домен: `guide.dendich.online`.
4. DNS A/AAAA как у panel.dendich.online.

## Health

`GET /api/health` → `{"ok": true, "static": true}`

## Чистка/пересборка зеркала

Зеркало статичное. Для обновления — повторить краул (см. историю `mirror*.py` в git) или скачать точечно недостающее.
