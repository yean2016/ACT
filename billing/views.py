from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.shortcuts import render, render_to_response
from django.contrib.auth.models import User
from collections import OrderedDict

#import requests
from random import Random
from datetime import datetime
from urllib.parse import unquote, parse_qs

import pytz
#import hashlib
import time

from rest_framework import status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import JSONParser

from parking.models import (
    ParkingLot, ParkingSpace, VehicleIn, VehicleOut,
)
from parking.views import get_parking_records, cacl_notice_id
from parking.roadside import insert_vehicle_out_record # INTERNAL TEST
from billing.models import (
    PrePayOrder, PrePayOrderWeChatPay, PrePayNotifyWeChatPay,
    PrePayOrderAliPay, PrePayNotifyAliPay,
    PrePayOrderUnionPay, PrePayNotifyUnionPay,
    Bill, BillNotify, Payment, OfflinePayment, MonthlyCardPayment
)
from billing.wechatpay import (
    WeChatConfig, WeChatPay, WeChatOrderQuery, WeChatNotify, WeChatCloseOrder,
    random_str, get_sign
)
from billing.alipay import(
    AliPayConfig, AliPay, AliPayNotify
)
from billing.unionpay import (
    UnionPayConfig, UnionPay, UnionPayNotify, UnionPaySigner
)
from userprofile.models import UserProfile
from socket_broker.client import BrokerClient

#tz = pytz.timezone('Asia/Shanghai')
import logging
logger = logging.getLogger(__name__)
#logger.info('info')
#logger.error('error')

wx_channel_config = {'app_id':'wxfb1cf19da66e305c',
    'mch_id':'1301359001',
    #'api_key':'04f6c8644b761f26cf3f1e33ec2a5f3b',
    'api_key':'81HDS7iU6JOQ2UyUjtSaqsZhacgKmAw6',
    'api_cert_file':'api_cert.pem',
    'api_key_file':'api_key.pem',
    'notify_url': 'http://120.25.60.20:8080/v0.1/billing/prepay/notify/wxpay/',
}

# alipay config
ali_channel_config = {
    'partner':'2088911833106433',
    'seller_id':'hqding@139.com',
    'partner_private_key_file':'ali_partner_pri_key.pem',
    'partner_public_key_file':'ali_partner_pub_key.pem',
    'alipay_public_key_file':'ali_pub_key.pem',
    'notify_url': 'http://120.25.60.20:8080/v0.1/billing/prepay/notify/alipay/',
    'sign_type': 'RSA',
}

unionpay_channel_config = {
    'version': '5.0.0',
    'encoding': 'UTF-8',
    'sign_method': '01',
    'trade_type': '01',
    'trade_subtype': '01',
    'biz_type': '001001',
    'channel_type': '08',
    'back_url': 'http://120.25.60.20:8080/v0.1/billing/prepay/notify/unionpay/',
    'access_type': '0',
    'merchant_id': '898110257340256',
    #'order_id': '',
    #'trade_time': '',
    #'trade_amount': '', # unit in FEN
    'currency_code': '156',
    #'pay_timeout': '',
    'order_description': '哒哒停车-账户充值',
    'pfx_file':'898110257340256.pfx',
    'x509_file': 'acp_prod_verify_sign.cer',
    'pfx_password': '111111',
}

# Create your views here.
def insert_record(plate_number):
    r = ParkingRecord()
    count = ParkingLot.objects.all().count()
    index = random.randint(1, count)
    lot = ParkingLot.objects.get(pk=index)
    space = ParkingSpace.objects.filter(parking_lot=lot)
    index = random.randint(0, space.count()-1)

    r.parking_lot = lot
    r.parking_space = space[index]
    r.entrance = ''
    r.plate_number = plate_number
    r.parking_card_number = 'TEST'
    r.vehicle_img = ''
    r.plate_img = ''
    r.type = 'parking'
    r.created_time = datetime.now()
    r.time_stamp = datetime.now()
    r.save()

    return r

def _get_record(plate_number):
    r = None

    if plate_number:
        try:
            r = ParkingRecord.objects.filter(plate_number=plate_number).latest('created_time')
            if r.type != 'parking':
                r = insert_record(plate_number)

        except ParkingRecord.DoesNotExist:
            # let's created one
            r = insert_record(plate_number)

    return r

def get_vehicle_in_record(plate_number):
    ret = None

    if plate_number:
        # try to retrieve vehicle in record
        try:
            #v_in = VehicleIn.objects.filter(plate_number=plate_number).latest('in_time')
            v_in = VehicleIn.objects.filter(plate_number=plate_number).latest('in_time')
            logger.info('vehicle in record id[%d]' % v_in.id)
            ret = v_in

            # there should be no vehicle out record
            try:
                v_out = VehicleOut.objects.filter(plate_number=plate_number).latest('out_time')
                #time_diff = vout.out_time - vin.in_time
                # out time should be earlier than in time
                logger.info('vehicle out record id[%d]' % v_out.id)
                if v_out.out_time > v_in.in_time:
                    logger.info('Vehicle in but already out.')
                    ret = None
            except VehicleOut.DoesNotExist:
                # it's ok
                pass

        except VehicleIn.DoesNotExist:
            logger.error('No vehicle in record found.')
            ret = None

        return ret
    else:
        logger.error('please provide the palte number')
        return ret

def get_bill(vehicle_in, user, spbill_create_ip):
    # if there is a bill generated
    try:
        b = Bill.objects.filter(vehicle_in=vehicle_in).latest('created_time')
        #try: # check if the bill had been paid
        #    p = Payment.objects.get(billing_record=b)
        #    # TODO timeout payment check needed
        #    print('There is a bill. But it had been paid.')
        #    return None

        #except Payment.DoesNotExist as e:
        #    # it's ok
        #    pass

        # a paid bill
        if b.paid:
            logger.info('A bill already created.')
            return b

        time_diff = datetime.now(pytz.utc) - b.created_time
        if time_diff.total_seconds() > 60:
            b.delete()
        else:
            logger.info('A bill already created.')
            return b

    except Bill.DoesNotExist:
            # it's ok
        pass

    # create a bill
    pl = eval(vehicle_in.price_list)
    logger.debug(pl)
    time_span_ms = datetime.now(pytz.utc) - vehicle_in.created_time#.replace(tzinfo=pytz.utc)
    time_span = int(time_span_ms.total_seconds()/60)

    # get all time frames
    time_frames = []
    price_frames = []
    time_slot = 0
    for item in pl:
        time_frames.append(item['time'])
        price_frames.append(item['price'])
    time_frames.sort()
    price_frames.sort()

    logger.info(datetime.now(pytz.utc))
    logger.info(vehicle_in.created_time)
    logger.info(time_span_ms)
    logger.info('time span is %d.' % time_span)

    # get the price
    time_slot = len(time_frames)
    for i in range(0, len(time_frames)):
        if time_span < time_frames[i]:
            time_slot = i
            break

    # too long time parking
    if time_span > 24 * 60:
        # ask for a bill from parking lot

        logger.error('time slot [%d], time frame [%d].' % (time_slot, time_frames[time_slot-1]))
        logger.error('A bill from parking lot needed.')
        return None
        #return  Response({"detail": "A bill from parking lot needed."}, status=404)
    if time_slot < 0:
        amount = 0
    else:
        amount = price_frames[time_slot]
    logger.info('bill amount is %d.' % amount)

    b = Bill()
    b.user = user
    b.vehicle_in = vehicle_in
    b.charged_duration = time_span
    b.out_trade_no = get_trade_no(6)
    b.spbill_create_ip = spbill_create_ip
    b.created_time = datetime.now(pytz.utc)
    b.updated_time = datetime.now(pytz.utc)
    b.payment_channel = 'online payment'
    b.amount = amount
    b.price = vehicle_in.price_list

    b.save()

    return b


@api_view(['GET', 'POST'])
@permission_classes((IsAuthenticated,))
def check_api(request):
    """
    app api
    """
    if request.method == 'GET':
        plate_number = request.GET.get('plate_number')
        user = request.user
        spbill_create_ip = get_client_ip(request)

        logger.info('checking for %s.' % plate_number)

        #return Response(status=200)

        if plate_number:
            v_in = get_vehicle_in_record(plate_number)

            # retrieve the bill
            if v_in:
                b = get_bill(v_in, user, spbill_create_ip)
                if b == None:
                    logger.error('retrieve bill from parking lot.')
                    return  Response({'detail': 'A bill from parking lot needed.'}, status=status.HTTP_404_NOT_FOUND)
            else:
                logger.info('No vehicle in record found.')
                return Response({'detail': 'No bill created.'}, status=404)

            if b.paid:
                detail = 'Bill has been paid.'
                logger.info(detail)
                return Response({'detail': detail}) #,status=status.HTTP_404_NOT_FOUND)
            # assembling the response
            try:
                lot = ParkingLot.objects.get(pk=v_in.parking_lot_id)
            except ParkingLot.DoesNotExist as e:
                logger.error(e)

            if lot:
                pl_name = lot.name
            else:
                pl_name = ''

            response_dict = OrderedDict()
            response_dict['kind'] = 'billing#base_info'
            response_dict['out_trade_no'] = b.out_trade_no
            response_dict['plate_number'] = plate_number
            response_dict['parking_card_number'] = v_in.parking_card_number
            response_dict['parking_lot'] = v_in.parking_lot.name#pl_name
            response_dict['parking_time'] = v_in.in_time
            response_dict['billing_time'] = b.created_time# TODO time span adjust
            response_dict['charged_duration'] = b.charged_duration
            response_dict['amount'] = b.amount
            response_dict['price'] = b.price

            logger.info(response_dict)
            return Response(response_dict)

        else:
            #please provide a valid palte number
            logger.error('Please provide a valid plate number')
            return Response({'detail': 'Please provide a valid plate number'})


@api_view(['GET', 'POST'])
@permission_classes((IsAuthenticated,))
def checkout_api(request):
    user = User.objects.get(username=request.user)
    records = get_parking_records(user.id) # a list of record id

    record = None
    response_dict = OrderedDict()

    for r in records:
        try:
            v_in = VehicleIn.objects.get(id=r)
            if v_in.type == 'road side':
                record = v_in 
        except VehicleIn.DoesNotExist:
            return Response({'detail': 'failed to get vehicle-in record.'},
                            status=status.HTTP_404_NOT_FOUND)

    # if the record has been paid
    try:
        bill = Bill.objects.get(vehicle_in=v_in,paid=True)
        print('No unpaid vechicle-in record.')
        return Response({'detail': 'No unpaid vechicle-in record.'},
                         status=status.HTTP_404_NOT_FOUND)
    except Bill.DoesNotExist:
        pass
    #return Response({'records': records})
    
    if record:
        #try:
        #    b = Bill.objects.filter(vehicle_in=r).latest('created_time')
        #    b.delete()
        #except Bill.DoesNotExist:
        #    pass

        # create a bill
        b = Bill()
        b.user = user
        b.vehicle_in = record
        b.out_trade_no = get_trade_no(6)
        b.spbill_create_ip = get_client_ip(request)
        random = Random()
        b.amount = random.randint(1, 100)
        time_span = datetime.now() - record.created_time.replace(tzinfo=None)
        b.charged_duration = int(time_span.total_seconds()/60)
        b.price = 'randomly charged.'
        b.save()

        # assembling the response
        response_dict['kind'] = 'billing#base_info'
        response_dict['out_trade_no'] = b.out_trade_no
        response_dict['plate_number'] = record.plate_number
        response_dict['parking_card_number'] = record.parking_card_number
        response_dict['parking_lot'] = record.parking_lot.name
        response_dict['parking_type'] = record.parking_lot.type
        response_dict['parking_time'] = record.in_time
        response_dict['billing_time'] = b.created_time
        response_dict['charged_duration'] = b.charged_duration
        response_dict['amount'] = b.amount
        response_dict['price'] = b.price

    return Response(response_dict)

    # interface to entrance
    #response = requests.post(url='http://127.0.0.1:8000/billing/check/')
    #print(response.content)
    return Response(response.content)
    return Response({"success": "Successfully checked out."})

@api_view(['GET', 'POST'])
@permission_classes((IsAuthenticated,))
def pay_api(request):
    params = request.query_params
    out_trade_no = params.get('out_trade_no')
    if not out_trade_no:
        return Response({'detail': 'please provide an out_trade_no.'},status=status.HTTP_400_BAD_REQUEST)


    try:
        # get bill
        bill = Bill.objects.get(out_trade_no=params.get('out_trade_no'))
        lot_id = bill.vehicle_in.parking_lot_id

        # only for test
        if lot_id != 49:
            logger.info('Not a parking lot testing for online payment[%s].' % lot_id)
            #return Response({'respCode': '00', 'respMsg': 'success', 'amount': bill.amount})

        # payment over-time?
        diff = datetime.now() - bill.created_time.replace(tzinfo=None)
        overtime = diff.total_seconds()
        if overtime > 300:
            #print(datetime.now().replace(tzinfo=pytz.utc))
            #print(bill.created_time.replace(tzinfo=pytz.utc))
            logger.error('overtime[%d]' % overtime)
            #return Response({'detail': 'payment overtime'},status=status.HTTP_408_REQUEST_TIMEOUT)

        if bill.paid:
            detail = ('Bill has been paid[%s].' % out_trade_no)
            logger.info(detail)
            return Response({'detail': detail}) #,status=status.HTTP_404_NOT_FOUND)

        paid = bill.paid

        if not paid:
            # send online payment notice to parking lot
            c = BrokerClient()
            c.connect()
            #ret = c.pay(b)
            ret = c.pay(bill)
            logger.info(ret)
            #return Response({'respCode': '00', 'respMsg': 'success', 'amount': bill.amount})
            # create notice
            notice = BillNotify.objects.create(user=request.user,
                trade_no=out_trade_no,
                spbill_pay_ip=get_client_ip(request),)
            #notice.save()

            # update balance
            user_profile = UserProfile.objects.get(user=request.user)
            balance_pre = user_profile.account_balance
            balance_updated = balance_pre - bill.amount
            user_profile.account_balance = balance_updated
            user_profile.save()
            # update balance in notice
            notice.balance = balance_updated
            notice.save()
            # update bill
            bill.paid = True
            bill.updated_time = datetime.now(pytz.utc)
            bill.save()

            # INTERNAL TEST ONLY
            #insert_vehicle_out_record(bill.vehicle_in.parking_lot.pk,
            #                          bill.vehicle_in.parking_space.pk)
    except Bill.DoesNotExist:
        detail = 'please provide a valid out_trade_no.'
        logger.error(detail)
        return Response({'detail': detail},status=status.HTTP_400_BAD_REQUEST)
    except UserProfile.DoesNotExist:
        logger.error('The owner of bill[%s] NOT found in table UserProfile.' % out_trade_no)
        return Response({'detail': 'please provide a valid out_trade_no.'},status=status.HTTP_400_BAD_REQUEST)

    return Response({'respCode': '00', 'respMsg': 'success', 'amount': bill.amount})


@api_view(['GET', 'POST'])
#@permission_classes((IsAuthenticated,))
def payment_api(request):
    transaction_id = request.GET.get('transaction_id')

    try:
        b = BillingRecord.objects.get(pk=transaction_id)
    #if b:
        try:
            p = Payment.objects.get(billing_record=b.pk)
            if p: # the bill had been paid
                return Response({"detail": "The bill had been paid."},
                                status=status.HTTP_400_BAD_REQUEST)

        #else:
        except Payment.DoesNotExist:
            # not paid
            # notify parking lot that the bill has been paid
            c = BrokerClient()
            c.connect()
            ret = c.pay(b)
            #return Response({"detail": "Transaction completed."})
            # insert the payment record
            p = Payment()
            p.billing_record = b
            p.paid = True
            p.created_time = datetime.now()
            p.save()

            # refresh the balance
            user = UserProfile.objects.get(user=request.user)
            new_balance = user.account_balance - b.amount
            user.account_balance = new_balance
            user.save()

            return Response({"detail": "Transaction completed."})

    #else:
    except BillingRecord.DoesNotExist:
        return Response({"detail": "NO such bill found."},
                            status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
#@permission_classes((IsAuthenticated,))
def pay_offline_api(request):
    parser = JSONParser
    confirmed = 'no'
    data = request.data

    #print(data)
    logger.debug(data)
    # verify the entrance
    try:
        identifier = str(data['identifier'])
        payment_time = data['paytime']
        payment_time = payment_time.replace('/','-') # uniform date format
        plate_number = data['carno']
    except KeyError as e:
        detail = {"detail": repr(e)}
        logger.error(detail)
        return Response(detail, status=status.HTTP_406_NOT_ACCEPTABLE)


    try:
        lot = ParkingLot.objects.get(identifier=identifier)
    except ParkingLot.DoesNotExist as e:
        # for debug
        #pl = ParkingLot.objects.get(pk=1)
        #er = Entrance(name=en,parking_lot=pl)
        #er.save()
        logger.error(repr(e))
        return Response({"detail": "No parking lot found."}, status=404)

    # check duplication
    #notice_id = data['notice_id']
    # upload tool is unable to provide correct notice ids
    # we have to calculate it by ourselves
    # it's the md5 of 'in_time' + 'carno' + 'identifier'
    notice_id = cacl_notice_id(payment_time, plate_number, identifier)

    try:
        off_pay = OfflinePayment.objects.get(notice_id=notice_id)
        logger.error('Duplicated offline payment record[%s][%s][%s][%s][%s].' % (notice_id,lot.name,plate_number,data['timestamp'],payment_time))
        return Response('success')
    except OfflinePayment.MultipleObjectsReturned:
        off_pays = OfflinePayment.objects.filter(notice_id=notice_id)
        logger.error('More than one offline payment records returned[%s][%s][%s][%s][%s].' % (notice_id,lot.name,plate_number,data['timestamp'],payment_time))
        for op in off_pays:
            logger.error('One offline payment record deleted[%s][%s][%s][%s][%s].' % (op.notice_id,op.parking_lot.name,op.plate_number,op.time_stamp,op.payment_time))
            op.delete()
    except OfflinePayment.DoesNotExist:
        pass

    pr = OfflinePayment()

    try:
        pr.parking_lot = lot
        pr.plate_number  = plate_number
        pr.amount = data['paymoney']

        if data['action'] == 'pay':
            pr.payment_type = 'PY'
        elif data['action'] == 'paytimeout':
            pr.payment_type == 'TO'
        else:
            # complain
            print('Unkonwn payment type %s.' % data['action'])

        pr.payment_time = payment_time#datetime.strptime(data['paytime'],'%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc)
        pr.time_stamp = data['timestamp']#datetime.fromtimestamp(int(data['timestamp'])).replace(tzinfo=pytz.utc)
        pr.notice_id = notice_id
        pr.price_list = data['pricelist']
        pr.created_time = datetime.now(pytz.utc)

        pr.save()

        if data['action'] == 'pay':
            logger.info('inserted offline payment record[%s][%s][%s][%s][%s][%s].' % (notice_id,lot.name,plate_number,data['timestamp'],payment_time,data['paymoney']))
        elif data['action'] == 'paytimeout':
            logger.info('inserted offline timeout payment record[%s][%s][%s][%s][%s][%s].' % (notice_id,lot.name,plate_number,data['timestamp'],payment_time,data['paymoney']))

    except KeyError as e:
        detail = {"detail": repr(e)}
        logger.error(detail)
        return Response(detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    return Response('success')

@api_view(['POST'])
def monthly_card_api(request):
    parser = JSONParser
    confirmed = 'no'
    data = request.data

    try:
        identifier = str(data['identifier'])
        payment_time = data['paytime']
        payment_time = payment_time.replace('/','-') # uniform date format
        plate_number = data['carno']
    except KeyError as e:
        error_detail = {"detail": repr(e)}
        logger.error(error_detail)
        return Response(error_detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    # verify the parking lot
    try:
        lot = ParkingLot.objects.get(identifier=identifier)
    except ParkingLot.DoesNotExist:
        logger.error('No parking lot named[%s].' % identifier)
        return Response({"detail": "No parking lot named[%s]." % identifier}, status=404)

    # check duplication
    #notice_id = data['notice_id']
    # upload tool is unable to provide correct notice ids
    # we have to calculate it by ourselves
    # it's the md5 of 'in_time' + 'carno' + 'identifier'
    notice_id = cacl_notice_id(payment_time, plate_number, identifier)

    try:
        month_pay = MonthlyCardPayment.objects.get(notice_id=notice_id)
        logger.error('Duplicated offline payment record[%s][%s][%s][%s][%s].' % (notice_id,lot.name,plate_number,data['timestamp'],payment_time))
        return Response('success')
    except MonthlyCardPayment.DoesNotExist:
        pass

    r = MonthlyCardPayment(parking_lot=lot)

    try:
        r.plate_number  = plate_number
        r.parking_card_number = data['cardno']
        r.amount = data['paymoney']
        r.month = data['month']
        r.payment_time = payment_time
        r.end_time = data['endtime']
        r.time_stamp = data['timestamp']
        r.notice_id = notice_id
        #r.parking_space_available = data['space_available']
        #r.parking_space_total = data['space_total']
        r.created_time = datetime.now(pytz.utc)
        #r.parking_space_id = 1
        r.save()

        logger.info('inserted monthly card record[%s][%s][%s][%s][%s].' % (notice_id,lot.name,plate_number,payment_time,data['paymoney']))

    except KeyError as e:
        error_detail = {"detail": repr(e)}
        logger.error(error_detail)
        return Response(error_detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    return Response('success')


@api_view(['GET',])
@permission_classes((IsAuthenticated,))
def prepay_get_order_wxpay_api(request):
    amount=request.GET.get('amount')

    if not amount:
       error_detail = {'detail': 'Please provide the prepay amount.'}
       return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)

    wx_config = WeChatConfig(wx_channel_config)
    wx_pay = WeChatPay(wx_config)
    params = {}
    #params['body'] = 'prepay'#'账户充值'
    params['body'] = '哒哒停车-账户充值'
    trade_no = get_trade_no(length=6)
    params['out_trade_no'] = trade_no
    params['total_fee'] = str(amount)#'1'
    params['spbill_create_ip'] = get_client_ip(request)
    params['notify_url'] = wx_config.notify_url
    params['trade_type'] = 'APP'

    wx_pay.set_params(params=params)
    print(wx_pay.params)
    response = wx_pay.post_xml_ssl()

    print(response)

    if response.get('return_code') != 'SUCCESS':
        error_detail = {'detail': response.get('return_msg')}
        return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)

    if response.get('result_code') != 'SUCCESS':
        error_detail = {'detail': response.get('err_code')}
        return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)

    wx_order = OrderedDict()
    wx_order['appid'] = response.get('appid')
    wx_order['partnerid'] = response.get('mch_id')
    wx_order['prepayid'] = response.get('prepay_id')
    wx_order['package'] = 'Sign=WXPay'
    wx_order['noncestr'] = random_str(length=32)
    now = int(time.time())
    now_str = str(now)
    wx_order['timestamp'] = now_str#response.get()
    sign = get_sign(wx_order, wx_config.api_key)
    wx_order['sign'] = sign

    #user = User.objects.get(id=2)
    user = User.objects.get(username=request.user)
    # insert order record
    order = PrePayOrder.objects.create(user=user,
                                 amount=amount)
    order.out_trade_no = trade_no
    order.payment_channel = 'wxpay'
    order.save()

    wxpay_record = PrePayOrderWeChatPay.objects.create(prepay_order=order,
                       app_id=wx_pay.app_id,
                       mch_id=wx_pay.mch_id,
                       body= params['body'],
                       total_fee=params['total_fee'],
                       spbill_create_ip=params['spbill_create_ip'],
                       notify_url=params['notify_url'],
                       trade_type=response.get('trade_type'),
                       response_app_id=wx_order['appid'],
                       response_mch_id=wx_order['partnerid'],
                       response_trade_type=response.get('trade_type'),
                       prepay_id=wx_order['prepayid'])
    wxpay_record.save()

    return Response(wx_order)


@api_view(['GET',])
#@permission_classes((IsAuthenticated,))
def prepay_order_query_wxpay_api(request):
    trade_no = request.GET.get('trade_no')

    if not trade_no:
       error_detail = {'detail': 'Please provide the prepay trade number.'}
       return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)

    wx_config = WeChatConfig(wx_channel_config)
    wx_query = WeChatOrderQuery(wx_config)
    query = wx_query.post(str(trade_no))
    print(query)

    return Response(query)

#@api_view(['GET', 'POST'])
@csrf_exempt
def prepay_notify_wxpay_api(request):
    wx_config = WeChatConfig(wx_channel_config)
    wx_notify = WeChatNotify(wx_config)

    xml = request.body.decode('utf-8')
    notice = wx_notify.notify_process(xml)

    print(notice)

    if notice.get('result_code') == 'SUCCESS':
        try:
            # update order
            order = PrePayOrder.objects.get(out_trade_no=notice.get('out_trade_no'))
            paid = order.paid
            order.paid = True
            order.updated_time = datetime.now().replace(tzinfo=pytz.utc)
            order.save()

            # update wechatpay record
            wx_order = PrePayNotifyWeChatPay.objects.create(prepay_order=order)
            wx_order.app_id = notice.get('appid')
            wx_order.mch_id = notice.get('mch_id')
            wx_order.open_id = notice.get('openid')
            wx_order.transaction_id = notice.get('transaction_id')
            wx_order.total_fee = notice.get('total_fee')
            wx_order.trade_type = notice.get('trade_type')
            wx_order.fee_type = notice.get('fee_type')
            wx_order.bank_type = notice.get('bank_type')
            wx_order.cash_fee = notice.get('cash_fee')
            wx_order.is_subscribe = notice.get('is_subscribe')
            wx_order.time_end = notice.get('time_end')
            wx_order.save()

            # update balance
            if not paid:
                user_profile = UserProfile.objects.get(user=order.user)
                balance_pre = user_profile.account_balance
                balance_updated = balance_pre + order.amount
                user_profile.account_balance = balance_updated
                user_profile.save()
        except PrePayOrder.DoesNotExist:
            print('There is NO prepay order[%s] in table PrePayOrder.' % notice.get('out_trade_no'))
        except PrePayNotifyWeChatPay.DoesNotExist:
            print('There is NO WeChatPay order[%s] in table PrePayNotifyWeChatPay.' % notice.get('out_trade_no'))
        except UserProfile.DoesNotExist:
            print('The owner of prepay order[%s] NOT found in table UserProfile.' % notice.get('out_trade_no'))

    params = {'return_code': 'SUCCESS'}
    response_xml = wx_notify.dict2xml(params,with_sign=False)
    print(response_xml)

    return HttpResponse(response_xml,content_type="application/xml")

@api_view(['GET', 'POST'])
def prepay_close_order_wxpay_api(request):
    trade_no = request.GET.get('trade_no')

    if not trade_no:
       error_detail = {'detail': 'Please provide the prepay trade number.'}
       return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)

    wx_config = WeChatConfig(wx_channel_config)
    wx_close = WeChatCloseOrder(wx_config)
    close = wx_close.post(str(trade_no))
    print(close)

    return Response(close)

@api_view(['GET',])
@permission_classes((IsAuthenticated,))
def prepay_get_order_alipay_api(request):
    request_amount=request.GET.get('amount')

    print(request.GET)
    print(request.get_full_path())
    if not request_amount:
       error_detail = {'detail': 'Please provide the prepay amount.'}
       return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)

    try:
       amount_float = float(request_amount)
    except ValueError:
       error_detail = {'detail': 'Please provide a valid amount value.'}
       return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)

    amount = int(amount_float)
    trade_no = get_trade_no(length=6)

    print(amount)

    ali_config = AliPayConfig(ali_channel_config)
    ali_pay = AliPay(ali_config)
    params = {}
    params['subject'] = '哒哒停车'
    params['body'] = '哒哒停车-账户充值'
    params['out_trade_no'] = trade_no
    params['total_fee'] = str(int(amount)/100)# unit is YUAN
    params['notify_url'] = ali_config.notify_url
    params['service'] = 'mobile.securitypay.pay'
    params['payment_type'] = '1'
    params['_input_charset'] = 'utf-8'
    params['it_b_pay'] = '30m'
    #params['return_url'] = 'm.alipay.com'

    ali_pay.set_params(params=params)
    print(ali_pay.params)

    order_string = ali_pay.get_order_string()
    print(order_string)

    #user = User.objects.get(id=2)
    user = User.objects.get(username=request.user)
    # insert order record
    order = PrePayOrder.objects.create(user=user,
                                 amount=amount)
    order.out_trade_no = trade_no
    order.payment_channel = 'alipay'
    order.save()

    # AliPay record
    alipay_record = PrePayOrderAliPay.objects.create(prepay_order=order,
                        partner=ali_config.partner,
                        seller_id=ali_config.seller_id,
                        subject = params['subject'],
                        body = params['body'],
                        total_fee = params['total_fee'],
                        payment_type = params['payment_type'],
                        service = params['service'],
                        it_b_pay = params['it_b_pay'],
                        notify_url = params['notify_url'])
    alipay_record.save()

    return Response({'order_string': order_string})


#@api_view(['GET', 'POST'])
@csrf_exempt
def prepay_notify_alipay_api(request):
    notify = request.body.decode('utf-8')

    #print(notify)

    notify_list_value = parse_qs(notify)
    notice = {}

    for (k,v) in notify_list_value.items():
        notice[k] = v[0]

    print(notice)

    ali_config = AliPayConfig(ali_channel_config)
    ali_notify = AliPayNotify(ali_config)

    verify = ali_notify.sign_verify(notice)

    if verify:
        try:
            # update order
            order = PrePayOrder.objects.get(out_trade_no=notice.get('out_trade_no'))
            paid = order.paid
            order.open_id = notice.get('openid')
            order.transaction_id = notice.get('transaction_id')
            order.updated_time = datetime.now(pytz.utc)
            order.time_end = notice.get('time_end')
            trade_status = notice.get('trade_status')
            if trade_status == 'TRADE_SUCCESS':
                order.paid = True
            order.save()

            # update alipay record
            alipay_record = PrePayNotifyAliPay.objects.create(prepay_order=order)
            alipay_record.trade_no = notice.get('trade_no')
            alipay_record.trade_status = notice.get('trade_status')
            alipay_record.buyer_email = notice.get('buyer_email')
            alipay_record.buyer_id = notice.get('buyer_id')
            alipay_record.seller_id = notice.get('seller_id')
            alipay_record.seller_email = notice.get('seller_email')
            alipay_record.subject = notice.get('subject')
            alipay_record.body = notice.get('body')
            alipay_record.quantity = notice.get('quantity')
            alipay_record.price = notice.get('price')
            alipay_record.total_fee = notice.get('total_fee')
            alipay_record.discount = notice.get('discount')
            alipay_record.is_total_fee_adjust = notice.get('is_total_fee_adjust')
            alipay_record.use_coupon = notice.get('use_coupon')
            alipay_record.payment_type = notice.get('payment_type')
            alipay_record.gmt_create = notice.get('gmt_create')
            alipay_record.gmt_payment = notice.get('gmt_payment','')
            alipay_record.notify_time = notice.get('notify_time')
            alipay_record.notify_id = notice.get('notify_id')
            alipay_record.save()

            # update balance
            if not paid and trade_status == 'TRADE_SUCCESS':
                user_profile = UserProfile.objects.get(user=order.user)
                balance_pre = user_profile.account_balance
                balance_updated = balance_pre + order.amount
                user_profile.account_balance = balance_updated
                user_profile.save()
        except PrePayOrder.DoesNotExist:
            print('There is NO order[%s] in table PrePayOrder.' % notice.get('out_trade_no'))
        except PrePayNotifyAliPay.DoesNotExist:
            print('There is NO order[%s] table PrePayNotifyAliPay.' % notice.get('out_trade_no'))
        except UserProfile.DoesNotExist:
            print('The owner of order[%s] NOT found in table UserProfile.' % notice.get('out_trade_no'))

    return HttpResponse('success',content_type="application/text")

@api_view(['GET',])
@permission_classes((IsAuthenticated,))
def prepay_get_order_unionpay_api(request):
    request_amount=request.GET.get('amount')

    print(request.GET)
    print(request.get_full_path())
    if not request_amount:
       error_detail = {'detail': 'Please provide the prepay amount.'}
       return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)

    try:
       amount_float = float(request_amount)
    except ValueError:
       error_detail = {'detail': 'Please provide a valid amount value.'}
       return Response(error_detail, status=status.HTTP_400_BAD_REQUEST)

    amount = int(amount_float)
    trade_no = get_trade_no(length=6)

    print(amount)


    union_config = UnionPayConfig(unionpay_channel_config)
    union_pay = UnionPay(union_config)
    union_signer = UnionPaySigner(union_config.pfx_file,
                       union_config.password,
                       union_config.x509_file)
    union_pay.Signer = union_signer

    params = {}
    params['version'] = union_config.version
    params['encoding'] = union_config.encoding
    #params['certID'] =
    params['signMethod'] = union_config.sign_method
    params['txnType'] = union_config.trade_type
    params['txnSubType'] = union_config.trade_subtype
    params['bizType'] = union_config.biz_type
    params['channelType'] = union_config.channel_type
    params['backUrl'] = union_config.back_url
    params['accessType'] = union_config.access_type
    params['merId'] = union_config.merchant_id
    params['orderId'] = trade_no
    params['txnTime'] = union_pay.get_txn_time()
    params['txnAmt'] = str(int(amount))# the unit is FEN
    params['currencyCode'] = union_config.currency_code
    params['payTimeout'] = union_pay.get_timeout()
    params['orderDesc'] = union_config.order_description
    #params['signature'] =

    union_pay.set_params(params=params)
    print('UnionPay request:')
    print(union_pay.params)

    data = union_pay.Signer.filter_params(params)
    sign_result = union_pay.Signer.sign(data)

    #print(sign_result)

    if not sign_result:
        raise error.UnionpayError('Sign data error')

    response = union_pay.send_packet(union_config.app_trans_url, data)

    print('UnionPay response:')
    print(response)

    # failed to place order to unionpay
    if response.get('respCode') != '00':
        print('Failed to place order to unionpay.')
        if response.get('respCode') == '408':
            return Response(response, status=status.HTTP_408_REQUEST_TIMEOUT)
        else:
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

    #user = User.objects.get(id=2)
    user = User.objects.get(username=request.user)
    # insert order record
    order = PrePayOrder.objects.create(user=user,
                                 amount=amount)
    order.out_trade_no = trade_no
    order.payment_channel = 'unionpay'
    order.save()


    # create unionpay order
    unionpay_record = PrePayOrderUnionPay.objects.create(prepay_order=order,
                          version=params['version'],
                          encoding=params['encoding'],
                          sign_method=params['signMethod'],
                          trade_type=params['txnType'],
                          trade_subtype=params['txnSubType'],
                          biz_type=params['bizType'],
                          channel_type=params['channelType'],
                          back_url=params['backUrl'],
                          access_type=params['accessType'],
                          merchant_id=params['merId'],
                          order_id=params['orderId'],
                          trade_time=params['txnTime'],
                          trade_amount=params['txnAmt'],
                          currency_code=params['currencyCode'],
                          pay_timeout=params['payTimeout'],
                          order_description=params['orderDesc'],
                          # from response
                          response_version=response['version'],
                          response_encoding=response['encoding'],
                          response_sign_method=response['signMethod'],
                          response_trade_type=response['txnType'],
                          response_trade_subtype=response['txnSubType'],
                          response_biz_type=response['bizType'],
                          response_access_type=response['accessType'],
                          response_merchant_id=response['merId'],
                          response_order_id=response['orderId'],
                          response_trade_time=response['txnTime'],
                          cert_id=response['certId'],
                          tn=response['tn'],
                          resp_code=response['respCode'],
                          resp_msg=response['respMsg'],)

    unionpay_record.save()

    return Response({'tn': response['tn']})

@api_view(['GET', 'POST'])
@csrf_exempt
def prepay_notify_unionpay_api(request):
    raw_content = request.body

    union_config = UnionPayConfig(unionpay_channel_config)
    union_notify = UnionPayNotify(union_config)
    union_signer = UnionPaySigner(union_config.pfx_file,
                       union_config.password,
                       union_config.x509_file)
    union_notify.Signer = union_signer

    notice = union_notify.notify_process(raw_content)

    print(notice)

    if notice.get('respCode') == '00':
        try:
            # update order
            order = PrePayOrder.objects.get(out_trade_no=notice.get('orderId'))
            paid = order.paid
            order.updated_time = datetime.now().replace(tzinfo=pytz.utc)
            order.paid = True
            order.save()

            # update alipay record
            unionpay_record = PrePayNotifyUnionPay.objects.create(prepay_order=order)
            unionpay_record.version = notice.get('version')
            unionpay_record.encoding = notice.get('encoding')
            unionpay_record.cert_id = notice.get('certId')
            unionpay_record.sign_method = notice.get('signMethod')
            unionpay_record.trade_type = notice.get('txnType')
            unionpay_record.trade_subtype = notice.get('txnSubType')
            unionpay_record.biz_type = notice.get('bizType')
            unionpay_record.access_type = notice.get('accessType')
            unionpay_record.merchant_id = notice.get('merId')
            unionpay_record.order_id = notice.get('orderId')
            unionpay_record.trade_time = notice.get('txnTime')
            unionpay_record.trade_amount = notice.get('txnAmt')
            unionpay_record.currency_code = notice.get('currencyCode')
            unionpay_record.query_id = notice.get('queryId')
            unionpay_record.resp_code = notice.get('respCode')
            unionpay_record.resp_msg = notice.get('respMsg')
            unionpay_record.settle_amount = notice.get('settleAmt')
            unionpay_record.settle_currency_code = notice.get('settleCurrencyCode')
            unionpay_record.settle_date = notice.get('settleDate')
            unionpay_record.trace_no = notice.get('traceNo')
            unionpay_record.trace_time = notice.get('traceTime')

            unionpay_record.save()

            # update balance
            if not paid:
                user_profile = UserProfile.objects.get(user=order.user)
                balance_pre = user_profile.account_balance
                balance_updated = balance_pre + order.amount
                user_profile.account_balance = balance_updated
                user_profile.save()
        except PrePayOrder.DoesNotExist:
            print('There is NO order[%s] in table PrePayOrder.' % notice.get('orderId'))
        except PrePayNotifyUnionPay.DoesNotExist:
            print('There is NO order[%s] table PrePayNotifyUnionPay.' % notice.get('orderId'))
        except UserProfile.DoesNotExist:
            print('The owner of order[%s] NOT found in table UserProfile.' % notice.get('orderId'))


    print(notice)

    return Response({'respCode': '00', 'respMsg': '成功[0000000]'})


@api_view(['GET', 'POST'])
@permission_classes((IsAuthenticated,))
def billing_api(request):
    pass

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_trade_no(length):
    now = int(time.time())
    dateArray = datetime.utcfromtimestamp(now)
    ts = dateArray.strftime("%Y%m%d")
    append = ''
    chars = '0123456789'
    count = len(chars) - 1
    random = Random()
    for i in range(length):
        append+=chars[random.randint(0, count)]

    trade_no = ts + append

    return trade_no

