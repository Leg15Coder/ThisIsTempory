# Android WebView Wrapper

Этот каталог содержит Android-приложение-оболочку для сайта Motify.

## Возможности
- Kotlin, `minSdk 24`, `targetSdk 34`
- WebView с JavaScript и DOM Storage
- Внутреннее открытие ссылок
- Обработка кнопки Назад по истории WebView
- Splash screen
- Экран ошибки сети с перезагрузкой
- Экран настроек: очистка кэша и данных
- Firebase foundation: Auth, Dynamic Links, FCM
- Простая проверка обновлений через JSON endpoint
- Синхронизация нативной Firebase-сессии с WebView через backend `/auth/google`

## Структура проекта
- `app/src/main/java/com/motify/wrapper/ui/MainActivity.kt` — WebView контейнер
- `app/src/main/java/com/motify/wrapper/ui/SplashActivity.kt` — экран загрузки
- `app/src/main/java/com/motify/wrapper/network/NetworkUtils.kt` — проверка сети
- `app/src/main/java/com/motify/wrapper/auth/AuthManager.kt` — нативный Firebase Auth
- `app/src/main/java/com/motify/wrapper/auth/SessionSyncManager.kt` — обмен Firebase ID token на серверную cookie-сессию
- `app/src/main/java/com/motify/wrapper/links/DynamicLinkHandler.kt` — обработка deep links / Firebase Dynamic Links
- `app/src/main/java/com/motify/wrapper/push/AppFirebaseMessagingService.kt` — FCM service
- `app/src/main/java/com/motify/wrapper/updates/UpdateChecker.kt` — простая проверка обновлений
- `app/src/main/java/com/motify/wrapper/ui/settings/SettingsActivity.kt` — настройки

## 1. Настройка проекта в Android Studio
1. Установите Android Studio Hedgehog/Koala+ и Android SDK 34.
2. Откройте папку `android-app` как отдельный проект.
3. Дождитесь Gradle Sync.
4. При необходимости измените значения в `gradle.properties`:
   - `BASE_URL=https://ваш-домен.vercel.app`
   - `UPDATE_CHECK_URL=https://ваш-домен.vercel.app/api/mobile/version`
   - `APP_HOST=ваш-домен.vercel.app`

## 2. Подключение Firebase
### Что нужно скачать
Из Firebase Console скачайте:
- `google-services.json`

### Куда положить
Положите файл сюда:
- `android-app/app/google-services.json`

### Что нужно включить в Firebase Console
1. **Authentication**
   - Включите Google Sign-In.
2. **Dynamic Links**
   - Настройте домен dynamic links или используйте App Links на ваш домен.
3. **Cloud Messaging**
   - Включите Firebase Cloud Messaging.
4. **SHA сертификаты**
   - Добавьте SHA-1 и SHA-256 debug/release ключей в Firebase project settings.

### Важный ресурс
Замените строку в `app/src/main/res/values/firebase_placeholders.xml`:
- `default_web_client_id`
на Web client ID из Firebase.

## 3. Как работает синхронизация сессии
Бэкенд уже умеет принимать Firebase ID token на `POST /auth/google` и выставлять серверную cookie-сессию.

В приложении используется такой поток:
1. Пользователь входит через нативный Firebase Auth SDK.
2. Приложение получает свежий Firebase ID token.
3. `SessionSyncManager` отправляет его на backend `POST /auth/google` по HTTPS.
4. Ответ backend содержит `Set-Cookie` с серверной сессией.
5. Эти cookie записываются в `android.webkit.CookieManager`.
6. После этого WebView открывает `/quest-app/` уже с авторизованной серверной сессией.

### Почему это безопаснее
- Токен не инжектится в JavaScript.
- Токен не кладётся в `localStorage`.
- WebView работает с обычной backend session cookie, как браузер.

## 4. Сборка APK
В Android Studio:
- `Build` → `Build Bundle(s) / APK(s)` → `Build APK(s)`

Или через терминал:
```bash
cd android-app
./gradlew assembleDebug
./gradlew assembleRelease
```

APK обычно появится в:
- `android-app/app/build/outputs/apk/debug/`
- `android-app/app/build/outputs/apk/release/`

## 5. Сборка AAB
```bash
cd android-app
./gradlew bundleRelease
```

Файл появится в:
- `android-app/app/build/outputs/bundle/release/`

## 6. Подписание приложения для публикации
### Создание keystore
```bash
keytool -genkeypair -v -keystore motify-release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias motify
```

### Подключение signing config
Добавьте в `app/build.gradle.kts` release signingConfig и храните пароли в `local.properties` или `gradle.properties` локально, не в git.

Пример переменных:
```properties
RELEASE_STORE_FILE=../motify-release.jks
RELEASE_STORE_PASSWORD=your_password
RELEASE_KEY_ALIAS=motify
RELEASE_KEY_PASSWORD=your_password
```

## 7. Проверка обновлений
Сейчас приложение ожидает JSON по адресу `UPDATE_CHECK_URL`.
Рекомендуемый формат:
```json
{
  "latest_version": "1.0.1",
  "minimum_supported_version": "1.0.0",
  "store_url": "https://example.com/download",
  "update_message": "Доступно обновление"
}
```

## 8. Push-уведомления (FCM)
В проект уже добавлен `AppFirebaseMessagingService`.
Для production стоит дополнить:
- создание notification channel
- показ уведомления
- обработка data payload и открытие конкретного URL в WebView

## 9. Что ещё нужно сделать перед production
- Заменить иконки launcher (`mipmap`).
- Подключить реальный Google Sign-In flow в UI (кнопка/автовход при необходимости).
- Добавить logout-сценарий: вызывать backend `/auth/logout`, очищать cookie и вызывать `FirebaseAuth.signOut()`.
- При необходимости добавить загрузку файлов, camera/file chooser и runtime permission flow.

## 10. Быстрый старт
1. Откройте `android-app` в Android Studio.
2. Положите `google-services.json` в `android-app/app/`.
3. Обновите `BASE_URL`, `UPDATE_CHECK_URL`, `APP_HOST`.
4. Замените `default_web_client_id`.
5. Sync Gradle.
6. Соберите debug APK.
