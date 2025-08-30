import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

from app.core.config import config


class EmailService:
    def __init__(self):
        self.smtp_server = config.SMTP_SERVER
        self.smtp_port = config.SMTP_PORT
        self.smtp_username = config.SMTP_USERNAME
        self.smtp_password = config.SMTP_PASSWORD
        self.from_email = config.FROM_EMAIL

    def send_verification_email(self, to_email: str, token: str, username: str):
        subject = "Подтверждение email адреса"

        html_content = f"""
        <html>
        <body>
            <h2>Добро пожаловать, {username}!</h2>
            <p>Для подтверждения вашего email адреса перейдите по ссылке:</p>
            <a href="{config.SERVER_NAME}/accounts/verify-email/{token}">Подтвердить email</a>
            <p>Ссылка действительна в течение 24 часов.</p>
        </body>
        </html>
        """

        text_content = f"""
        Добро пожаловать, {username}!

        Для подтверждения вашего email адреса перейдите по ссылке:
        {config.SERVER_NAME}/accounts/verify-email/{token}

        Ссылка действительна в течение 24 часов.
        """

        self._send_email(to_email, subject, text_content, html_content)

    def send_admin_approval_notification(self, to_email: str, username: str):
        subject = "Запрос на одобрение нового пользователя"

        html_content = f"""
        <html>
        <body>
            <h2>Новый пользователь ожидает одобрения</h2>
            <p>Пользователь {username} ({to_email}) ожидает одобрения администратора.</p>
            <a href="{config.SERVER_NAME}/accounts/admin/approvals">Перейти к одобрениям</a>
        </body>
        </html>
        """

        self._send_email(to_email, subject, html_content, html_content)

    def send_approval_confirmation(self, to_email: str, username: str):
        subject = "Ваш аккаунт одобрен"

        html_content = f"""
        <html>
        <body>
            <h2>Ваш аккаунт одобрен, {username}!</h2>
            <p>Теперь вы можете войти в систему и использовать все возможности.</p>
            <a href="{config.SERVER_NAME}/accounts/login">Войти в систему</a>
        </body>
        </html>
        """

        self._send_email(to_email, subject, html_content, html_content)

    def _send_email(self, to_email: str, subject: str, text_content: str, html_content: str):
        if not all([self.smtp_username, self.smtp_password, self.from_email]):
            logging.warn(f"Email не отправлен (настройки SMTP не заданы): {subject} для {to_email}")
            return

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = to_email

            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")

            msg.attach(part1)
            msg.attach(part2)

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logging.info(f"Email отправлен: {subject} для {to_email}")

        except Exception as e:
            logging.warn(f"Ошибка отправки email: {e}")


email_service = EmailService()
