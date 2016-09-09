from django.db import models
from django.contrib.auth.models import User

from parking.models import ParkingLot, VehicleIn
from userprofile.models import UserProfile

# length of each field
# type   - 10
# amount - 13
# id     - 32
# time   - 30
# desc   - 50
# url    - 80

# Create your models here.
class PrePayOrder(models.Model):
    user = models.ForeignKey(User)
    out_trade_no = models.CharField(max_length=50)
    created_time = models.DateTimeField(auto_now_add=True)
    updated_time = models.DateTimeField(auto_now=True)
    paid = models.BooleanField(default=False)
    payment_channel = models.CharField(max_length=10)
    amount = models.IntegerField(default=0)

class PrePayOrderWeChatPay(models.Model):
    prepay_order = models.ForeignKey('PrePayOrder')
    app_id = models.CharField(max_length=32)
    mch_id = models.CharField(max_length=32)
    body = models.CharField(max_length=50)
    total_fee = models.CharField(max_length=13)
    spbill_create_ip = models.CharField(max_length=50)
    notify_url = models.CharField(max_length=80)
    trade_type = models.CharField(max_length=20)
    # from response
    response_app_id = models.CharField(max_length=32)
    response_mch_id = models.CharField(max_length=32)
    response_trade_type = models.CharField(max_length=20)
    prepay_id = models.CharField(max_length=50)

class PrePayNotifyWeChatPay(models.Model):
    prepay_order = models.ForeignKey('PrePayOrder')
    app_id = models.CharField(max_length=32)
    mch_id = models.CharField(max_length=32)
    open_id = models.CharField(max_length=32)
    transaction_id = models.CharField(max_length=32)
    total_fee = models.CharField(max_length=13)
    trade_type = models.CharField(max_length=20)
    fee_type = models.CharField(max_length=10)
    bank_type = models.CharField(max_length=10)
    cash_fee = models.CharField(max_length=13)
    is_subscribe = models.CharField(max_length=4)
    time_end = models.CharField(max_length=30)

class PrePayOrderAliPay(models.Model):
    prepay_order = models.ForeignKey('PrePayOrder')
    partner = models.CharField(max_length=32)
    seller_id = models.CharField(max_length=50)
    subject = models.CharField(max_length=50)
    body = models.CharField(max_length=50)
    total_fee = models.CharField(max_length=13)
    payment_type = models.CharField(max_length=4)
    service = models.CharField(max_length=80)
    it_b_pay = models.CharField(max_length=5)
    notify_url = models.CharField(max_length=80)

class PrePayNotifyAliPay(models.Model):
    prepay_order = models.ForeignKey('PrePayOrder')
    trade_no = models.CharField(max_length=32)
    trade_status = models.CharField(max_length=20)
    buyer_email = models.CharField(max_length=50)
    buyer_id = models.CharField(max_length=50)
    seller_id = models.CharField(max_length=50)
    seller_email = models.CharField(max_length=50)
    subject = models.CharField(max_length=50)
    body = models.CharField(max_length=50)
    quantity = models.CharField(max_length=5)
    price = models.CharField(max_length=13)
    total_fee = models.CharField(max_length=13)
    discount = models.CharField(max_length=13)
    is_total_fee_adjust = models.CharField(max_length=4)
    use_coupon = models.CharField(max_length=4)
    payment_type = models.CharField(max_length=4)
    gmt_create = models.CharField(max_length=30)
    gmt_payment = models.CharField(max_length=30)
    notify_time = models.CharField(max_length=30)
    notify_id = models.CharField(max_length=50)

class PrePayOrderUnionPay(models.Model):
    prepay_order = models.ForeignKey('PrePayOrder')
    version = models.CharField(max_length=10)
    encoding = models.CharField(max_length=10)
    sign_method = models.CharField(max_length=10)
    trade_type = models.CharField(max_length=10)
    trade_subtype = models.CharField(max_length=10)
    biz_type = models.CharField(max_length=10)
    channel_type = models.CharField(max_length=10)
    back_url = models.CharField(max_length=80)
    access_type = models.CharField(max_length=10)
    merchant_id = models.CharField(max_length=32)
    order_id = models.CharField(max_length=32)
    trade_time = models.CharField(max_length=30)
    trade_amount = models.CharField(max_length=13)
    currency_code = models.CharField(max_length=10)
    pay_timeout = models.CharField(max_length=30)
    order_description = models.CharField(max_length=50)
    # from response
    response_version = models.CharField(max_length=10)
    response_encoding = models.CharField(max_length=10)
    response_sign_method = models.CharField(max_length=10)
    response_trade_type = models.CharField(max_length=10)
    response_trade_subtype = models.CharField(max_length=10)
    response_biz_type = models.CharField(max_length=10)
    response_access_type = models.CharField(max_length=10)
    response_merchant_id = models.CharField(max_length=32)
    response_order_id = models.CharField(max_length=32)
    response_trade_time = models.CharField(max_length=30)
    cert_id = models.CharField(max_length=32)
    tn = models.CharField(max_length=32)
    resp_code = models.CharField(max_length=10)
    resp_msg = models.CharField(max_length=50)

class PrePayNotifyUnionPay(models.Model):
    prepay_order = models.ForeignKey('PrePayOrder')
    version = models.CharField(max_length=10)
    encoding = models.CharField(max_length=10)
    cert_id = models.CharField(max_length=32)
    sign_method = models.CharField(max_length=10)
    trade_type = models.CharField(max_length=10)
    trade_subtype = models.CharField(max_length=10)
    biz_type = models.CharField(max_length=10)
    access_type = models.CharField(max_length=10)
    merchant_id = models.CharField(max_length=32)
    order_id = models.CharField(max_length=32)
    trade_time = models.CharField(max_length=30)
    trade_amount = models.CharField(max_length=13)
    currency_code = models.CharField(max_length=10)
    query_id = models.CharField(max_length=32)
    resp_code = models.CharField(max_length=10)
    resp_msg = models.CharField(max_length=50)
    settle_amount = models.CharField(max_length=13)
    settle_currency_code = models.CharField(max_length=10)
    settle_date = models.CharField(max_length=30)
    trace_no = models.CharField(max_length=32)
    trace_time = models.CharField(max_length=30)


class Bill(models.Model):
    user = models.ForeignKey(User)
    vehicle_in = models.ForeignKey(VehicleIn)
    charged_duration = models.IntegerField(default=0) # minutes
    out_trade_no = models.CharField(max_length=50)
    spbill_create_ip = models.CharField(max_length=50)
    created_time = models.DateTimeField(auto_now_add=True)
    updated_time = models.DateTimeField(auto_now=True)
    paid = models.BooleanField(default=False)
    payment_channel = models.CharField(max_length=20)
    amount = models.IntegerField(default=0) # UNIT IN FEN
    price = models.CharField(max_length=1000)


class BillNotify(models.Model):
    user = models.ForeignKey(User)
    trade_no = models.CharField(max_length=50)
    balance = models.IntegerField(default=0)
    spbill_pay_ip = models.CharField(max_length=50)
    trade_time = models.DateTimeField(auto_now_add=True)


class Payment(models.Model):
    bill = models.ForeignKey('Bill')
    paid = models.BooleanField(default=False)
    created_time = models.DateTimeField()

class OnlinePayment(models.Model):
    pass


class OfflinePayment(models.Model):
    PAYMENT = 'PY'
    TIMEOUT_PAYMENT = 'TO'
    PAYMENT_TYPES = (
        (PAYMENT, 'payment for parking time'),
        (TIMEOUT_PAYMENT, 'payment for not leaving on time'),
    )

    parking_lot = models.ForeignKey(ParkingLot)
    plate_number = models.CharField(max_length=15)
    parking_card_number = models.CharField(max_length=20)
    amount = models.IntegerField(default=0)
    payment_type = models.CharField(max_length=2,
                                    choices=PAYMENT_TYPES,
                                    default=PAYMENT)
    payment_time = models.CharField(max_length=25)
    time_stamp = models.BigIntegerField(default=0) # uploaded by parking lot
    notice_id = models.CharField(max_length=40)
    price_list = models.CharField(max_length=1000)
    created_time = models.DateTimeField() # record created

    def __str__(self):
        return self.plate_number

class MonthlyCardPayment(models.Model):
    parking_lot = models.ForeignKey(ParkingLot)
    plate_number = models.CharField(max_length=15)
    parking_card_number = models.CharField(max_length=20)
    amount = models.IntegerField(default=0)
    month = models.IntegerField(default=0)
    payment_time = models.CharField(max_length=25)
    end_time = models.CharField(max_length=25)
    time_stamp = models.BigIntegerField(default=0) # uploaded by parking lot
    notice_id = models.CharField(max_length=40)
    created_time = models.DateTimeField() # record created

    def __str__(self):
        return self.plate_number


