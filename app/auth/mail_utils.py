from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from fastapi import HTTPException
import os
from typing import Dict, Optional
from jinja2 import Template
import json

VERIFICATION_TEMPLATE = '''
Здравствуйте!

Чтобы подтвердить почту и завершить регистрацию, перейдите по ссылке:

{{ link }}

Если вы не регистрировались — просто проигнорируйте это письмо.

С уважением,
Команда %APP_NAME%
'''


def _build_connection_config() -> Optional[ConnectionConfig]:
    """Пытаемся построить ConnectionConfig гибко — поддерживаем разные версии fastapi-mail.
    Если не получилось (валидация pydantic), возвращаем None и используем заглушку.
    """
    try:
        kwargs = {
            'MAIL_USERNAME': os.getenv('SMTP_USERNAME', ''),
            'MAIL_PASSWORD': os.getenv('SMTP_PASSWORD', ''),
            'MAIL_FROM': os.getenv('MAIL_FROM', 'noreply@example.com'),
            'MAIL_PORT': int(os.getenv('MAIL_PORT', 587)),
            'MAIL_SERVER': os.getenv('MAIL_SERVER', 'smtp.gmail.com'),
            'MAIL_STARTTLS': os.getenv('MAIL_STARTTLS', os.getenv('MAIL_TLS', 'True')).lower() in ('1','true','yes'),
            'MAIL_SSL_TLS': os.getenv('MAIL_SSL_TLS', os.getenv('MAIL_SSL', 'False')).lower() in ('1','true','yes'),
            'USE_CREDENTIALS': True,
            'VALIDATE_CERTS': True
        }

        return ConnectionConfig(**kwargs)
    except Exception as e:
        print(f'⚠️ Не удалось создать ConnectionConfig для FastMail: {e}')
        return None


def _get_fastmail():
    cfg = _build_connection_config()
    if not cfg:
        return None
    try:
        fm = FastMail(cfg)
        return fm
    except Exception as e:
        print(f'⚠️ Не удалось инициализировать FastMail: {e}')
        return None


def _log_email_locally(to_email: str, subject: str, body: str):
    out = {
        'to': to_email,
        'subject': subject,
        'body': body,
    }
    try:
        with open('sent_emails.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f'Ошибка логирования письма: {e}')


def send_verification_email(to_email: str, link: str):
    sender_name = os.getenv('MAIL_SENDER_NAME', os.getenv('APP_NAME', 'The Last Reality'))
    mail_from = os.getenv('MAIL_FROM', 'noreply@example.com')
    subject = f"Подтвердите email для {os.getenv('APP_NAME', 'The Last Reality')}"
    body_text = Template(VERIFICATION_TEMPLATE).render(link=link)

    fm = _get_fastmail()
    if not fm:
        print(f'⚠️ SMTP недоступен — сохраняю письмо локально и логирую. Кому: {to_email}')
        _log_email_locally(to_email, subject, body_text)
        return

    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=body_text,
        subtype='plain'
    )

    headers = {
        'From': f"{sender_name} <{mail_from}>",
        'Reply-To': mail_from
    }

    try:
        try:
            fm.send_message(message, template_name=None, html=None, headers=headers)
        except TypeError:
            fm.send_message(message)
    except Exception as e:
        print(f'Ошибка отправки письма через SMTP: {e}')
        _log_email_locally(to_email, subject, body_text)
        raise HTTPException(status_code=500, detail='Ошибка отправки подтверждения по email')
