import uuid
from yookassa import Configuration, Payment
from app import config

# Настраиваем авторизацию
Configuration.account_id = config.YOO_SHOP_ID
Configuration.secret_key = config.YOO_SECRET_KEY

def create_yoo_payment(amount_rub: int, description: str, user_id: int):
    """
    Создает платеж. 
    Мы НЕ передаем payment_method_data, чтобы ЮКасса сама показала
    выбор: Карты, СБП, SberPay и т.д.
    """
    idempotence_key = str(uuid.uuid4())
    
    payment = Payment.create({
        "amount": {
            "value": str(amount_rub),
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/nan0banana_bot" # Куда вернуть юзера
        },
        "capture": True, # Автосписание
        "description": description,
        "metadata": {
            "user_id": user_id
        }
    }, idempotence_key)

    return payment

def check_yoo_payment(payment_id: str):
    """Проверяет статус платежа"""
    payment = Payment.find_one(payment_id)
    return payment.status