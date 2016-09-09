# -*- coding: utf-8 -*-
import os
import time
import re
import logging
import datetime
import json
import requests
import hashlib
import rsa
import base64

from random import Random
from collections import OrderedDict

from django.utils.http import urlquote_plus
#from django.conf import settings
#from django.core.exceptions import ImproperlyConfigured


# Get an instance of a logger
logger = logging.getLogger(__name__)

# 下载bill的时间,每日13点
GET_BILL_TIME = 13

def dict_to_xml(params, sign):
    xml = ['<xml>']
    for (k, v) in params.items():
        if v.isdigit():
            xml.append('<%s>%s</%s>' % (k, v, k))
        else:
            xml.append('<%s><![CDATA[%s]]></%s>' % (k, v, k))

    if sign:
        xml.append('<sign><![CDATA[%s]]></sign>' % sign)
    xml.append('</xml>')
    return ''.join(xml)


def xml_to_dict(xml):
    #print(xml)
    if xml[0:5].upper() != "<XML>" and xml[-6].upper() != "</XML>":
        return None, None

    result = {}
    sign = None
    content = ''.join(xml[5:-6].strip().split('\n'))

    pattern = re.compile(r'<(?P<key>.+)>(?P<value>.+)</(?P=key)>')
    m = pattern.match(content)
    while m:
        key = m.group('key').strip()
        value = m.group('value').strip()
        if value != '<![CDATA[]]>':
            pattern_inner = re.compile(r'<!\[CDATA\[(?P<inner_val>.+)\]\]>')
            inner_m = pattern_inner.match(value)
            if inner_m:
                value = inner_m.group('inner_val').strip()
            if key == 'sign':
                sign = value
            else:
                result[key] = value

        next_index = m.end('value') + len(key) + 3
        if next_index >= len(content):
            break
        content = content[next_index:]
        m = pattern.match(content)

    return sign, result


class AliPayConfig(object):
    def __init__(self, channel_config):
        self.partner = channel_config['partner']
        self.seller_id = channel_config['seller_id']
        self.partner_private_key_file = channel_config['partner_private_key_file']
        self.partner_public_key_file = channel_config['partner_public_key_file']
        self.alipay_public_key_file = channel_config['alipay_public_key_file']
        self.notify_url = channel_config['notify_url']
        self.sign_type = channel_config['sign_type']

    def __str__(self):
        return "AliPayConfig object: " + str(self.__dict__)


class AliPay(object):

    def __init__(self, alipay_config):
        self.partner = alipay_config.partner
        self.seller_id = alipay_config.seller_id
        self.partner_private_key_file = alipay_config.partner_private_key_file
        self.partner_public_key_file = alipay_config.partner_public_key_file
        self.alipay_public_key_file = alipay_config.alipay_public_key_file
        self.notify_url = alipay_config.notify_url
        self.sign_type = alipay_config.sign_type

        self.common_params = {'partner': self.partner,
                              'seller_id': self.seller_id}
        self.params = {}

    def set_params(self, **kwargs):
        self.params = {}
        for (k, v) in kwargs['params'].items():
            self.params[k] = v#smart_str(v)

        self.params.update(self.common_params)

    def get_order_string(self):
        msg = OrderedDict(sorted(self.params.items()))
        s = ''
        for (k,v) in msg.items():
            s += k
            s += '='
            s += '"'
            s += str(v)
            s += '"'
            s += '&'

        sign_pre = s[:-1]

        sign = self.get_sign(sign_pre)

        signed = sign_pre + '&sign="' + sign + '"&sign_type="' + self.sign_type + '"'

        return signed

    def get_sign(self, content):
        with open(self.partner_private_key_file, mode='rb') as privatefile:
            keydata = privatefile.read()
        privkey = rsa.PrivateKey.load_pkcs1(keydata)

        print('Input string to RSA signature[%s]' % content)
        sign_bytes = rsa.sign(content.encode('utf-8'), privkey, 'SHA-1')
        sign = base64.b64encode(sign_bytes)

        # urlencode
        sign_urlencoded = urlquote_plus(sign.decode('utf-8'))
        #print(sign_urlencoded)

        return(sign_urlencoded)

    def post_xml(self):
        xml = self.dict2xml(self.params)
        response = requests.post(self.url, data=xml)
        logger.info('Make post request to %s' % response.url)
        logger.debug('Request XML: %s' % xml)
        logger.debug('Response encoding: %s' % response.encoding)
        logger.debug('Response XML: %s' % ''.join(response.text.splitlines()))

        return self.xml2dict(response.text.encode(response.encoding)) if response.encoding else response.text

    def post_xml_ssl(self):
        xml = self.dict2xml(self.params)
        #print(xml)
        logger.debug('Cert file: %s' % self.cert_file)
        logger.debug('Key file: %s' % self.key_file)
        requests.encoding = 'utf-8'
        response = requests.post(
            self.url, data=xml.encode('utf-8'), verify=True, cert=(self.cert_file, self.key_file))
        logger.info('Make SSL post request to %s' % response.url)
        logger.debug('Request XML: %s' % xml)
        logger.debug('Response encoding: %s' % response.encoding)
        logger.debug('Response XML: %s' % ''.join(response.text.splitlines()))

        response.encoding = 'utf-8'
        return self.xml2dict(response.text)

class AliPayOrderPay(AliPay):

    def __init__(self, alipay_config):
        super(AliPayOrderPay, self).__init__(alipay_config)
        self.trade_type = ''

    def _post(self, body, out_trade_no, total_fee, spbill_create_ip, notify_url, **kwargs):
        params = {'body': body,
                  'out_trade_no': out_trade_no,
                  'total_fee': total_fee,
                  'spbill_create_ip': spbill_create_ip,
                  'notify_url': notify_url,
                  'trade_type': self.trade_type}
        params.update(**kwargs)

        self.set_params(**params)
        return self.post_xml()

    def get_order_info(self):

        order_info = {}
        return order_info

class UnifiedOrderPay(AliPay):

    def __init__(self, alipay_config):
        super(UnifiedOrderPay, self).__init__(alipay_config)
        self.url = 'https://api.mch.weixin.qq.com/pay/unifiedorder'
        self.trade_type = ''

    def _post(self, body, out_trade_no, total_fee, spbill_create_ip, notify_url, **kwargs):
        params = {'body': body,
                  'out_trade_no': out_trade_no,
                  'total_fee': total_fee,
                  'spbill_create_ip': spbill_create_ip,
                  'notify_url': notify_url,
                  'trade_type': self.trade_type}
        params.update(**kwargs)

        self.set_params(**params)
        return self.post_xml()

class NativeOrderPay(UnifiedOrderPay):

    """
    Native 统一支付类
    """

    def __init__(self, alipay_config):
        super(NativeOrderPay, self).__init__(alipay_config)
        self.trade_type = 'NATIVE'

    def post(self, body, out_trade_no, total_fee, spbill_create_ip, notify_url):
        return super(NativeOrderPay, self)._post(body, out_trade_no, total_fee, spbill_create_ip, notify_url)


class AppOrderPay(UnifiedOrderPay):

    """
    App 统一支付类
    """

    def __init__(self, alipay_config):
        super(AppOrderPay, self).__init__(
            wechat_config)
        self.trade_type = 'APP'

    def post(self, body, out_trade_no, total_fee, spbill_create_ip, notify_url):
        return super(AppOrderPay, self)._post(body, out_trade_no, total_fee, spbill_create_ip, notify_url)

class AliPayOrderQuery(AliPay):

    def __init__(self, alipay_config):
        super(AliPayOrderQuery, self).__init__(wechat_config)
        self.url = 'https://api.mch.weixin.qq.com/pay/orderquery'

    def post(self, out_trade_no):
        params = {'out_trade_no': out_trade_no}
        #params = {'transaction_id': out_trade_no}
        self.set_params(params=params)
        return self.post_xml_ssl()


class AliPayNotify(AliPay):

    def __init__(self, alipay_config):
        super(AliPayNotify, self).__init__(alipay_config)

    def sign_verify(self, content):
        msg_dict = OrderedDict(sorted(content.items()))
        s = ''
        for (k,v) in msg_dict.items():
            if k != 'sign' and k != 'sign_type':
                s += k
                s += '='
                s += str(v)
                s += '&'

        msg_str = s[:-1]

        # calc signature
        with open(self.alipay_public_key_file, mode='rb') as publicfile:
            keydata = publicfile.read()
        pubkey = rsa.PublicKey.load_pkcs1(keydata)
        sign_list = content.get('sign', '')
        sign_str = sign_list

        # no sign in notify
        if sign_str == '':
            return False

        sign_bytes = sign_str.encode('utf-8')

        sign = base64.b64decode(sign_bytes)
        print('Input string to RSA signature[%s]' % msg_str)
        #print(sign)

        try:
            result = rsa.verify(msg_str.encode('utf-8'), sign, pubkey)
            print('AliPay notification verified.')
        except rsa.pkcs1.VerificationError:
            print('AliPay notification verify FAILED.')
            result = False

        return result


class Refund(AliPay):

    def __init__(self, alipay_config):
        super(Refund, self).__init__(alipay_config)
        self.url = 'https://api.mch.weixin.qq.com/secapi/pay/refund'

    def post(self, out_trade_no, out_refund_no, total_fee, refund_fee):
        params = {'out_trade_no': out_trade_no,
                  'out_refund_no': out_refund_no,
                  'total_fee': total_fee,
                  'refund_fee': refund_fee,
                  'op_user_id': self.mch_id}
        self.set_params(**params)
        return self.post_xml_ssl()


class RefundQuery(AliPay):

    def __init__(self, alipay_config):
        super(RefundQuery, self).__init__(alipay_config)
        self.url = 'https://api.mch.weixin.qq.com/pay/refundquery'

    def post(self, out_refund_no):
        params = {'out_refund_no': out_refund_no}
        self.set_params(**params)
        return self.post_xml()


class DownloadBill(AliPay):

    def __init__(self, alipay_config):
        super(DownloadBill, self).__init__(alipay_config)
        self.url = 'https://api.mch.weixin.qq.com/pay/downloadbill'
        self.unique_id = 'wechat_%s_%s' % (wechat_config.app_id, wechat_config.mch_id)
        self.channel_account = ChannelAccount.objects.get(unique_id=self.unique_id)

    def post_xml(self):
        xml = self.dict2xml(self.params)
        response = requests.post(self.url, data=xml)
        logger.info('Make post request to %s' % response.url)
        logger.debug('Request XML: %s' % xml)
        logger.debug('Response encoding: %s' % response.encoding)
        logger.debug('Response XML: %s' % ''.join(response.text.splitlines()))

        return self.xml2dict_for_bill(response.text.encode(response.encoding)) if response.encoding else response.text

    def xml2dict_for_bill(self, xml):
        sign, params = xml_to_dict(xml)
        return params

    def get_yesterday_date_str(self):
        today = datetime.date.today()
        t = datetime.timedelta(days=1)
        # e.g. 20150705
        yesterday = str(today - t)
        return yesterday

    def is_record_writen(self):
        bill_log = BillLog.objects.filter(
            date=self.bill_date, channel_account=self.channel_account)
        return bill_log

    def date_validation(self, input_date):
        today = datetime.date.today()
        t = datetime.timedelta(days=1)
        yesterday = (today - t)
        now = datetime.datetime.now()
        if input_date < today:
            if input_date == yesterday:
                if now.hour >= GET_BILL_TIME:
                    return True
                else:
                    raise ValueError(
                        "Get bill time:[%s] o‘clock must later then %s o‘clock." % (
                            now.hour, GET_BILL_TIME))
            else:
                return True
        else:
            raise ValueError(
                "Bill_date given: [%s] should before today's date: [%s]." % (input_date, today))

    def is_responese_string(self, res):
        if type(res) is unicode:
            return True
        elif type(res) is dict:
            return False
        else:
            raise Exception(u'Invalid response type %s.' % type(res))

    def get_res(self, bill_date=None, bill_type='ALL'):
        params = {}
        if bill_date:
            input_bill_date = datetime.datetime.strptime(
                bill_date, '%Y-%m-%d').date()
            if self.date_validation(input_bill_date):
                self.bill_date = str(input_bill_date)
        else:
            self.bill_date = self.get_yesterday_date_str()
        # reformat date string from yyyy-mm-dd to yyyymmdd
        print('input_date>>>', self.bill_date)
        self.rf_bill_date = self.bill_date.replace('-', '')

        params['bill_date'] = self.rf_bill_date
        params['bill_type'] = bill_type

        self.set_params(**params)

        return self.post_xml()

    def create_bill_log(self, bill_status, file_path, remark):
        BillLog.objects.create(date=self.bill_date,
                               bill_status=bill_status,
                               file_path=file_path,
                               remark=remark,
                               channel_account=self.channel_account,
                               )

    def get_bill(self, bill_date=None, bill_type='ALL'):
        res = self.get_res(bill_date, bill_type)

        month_dir = '%s' % self.rf_bill_date[:6]
        bill_file_dir = os.path.join(WC_BILLS_PATH, month_dir)
        if not os.path.exists(bill_file_dir):
            os.makedirs(bill_file_dir)

        self.file_path = os.path.join(
            bill_file_dir, "%s_%s.csv" % (self.unique_id, self.rf_bill_date))
        self.rel_dir_name = os.path.relpath(self.file_path)

        # 成功取回外部账单
        if self.is_responese_string(res):
            res = res.replace('`', '')

            if not self.is_record_writen():
                with open(self.file_path, "wb") as f:
                    f.write(res.encode("UTF-8"))
                    f.close()
                self.create_bill_log('SUCCESS', self.rel_dir_name, '{}')
        else:
            # 对账单文件为空，不创建，只写入数据库信息
            if res['return_msg'] == 'No Bill Exist':
                remark = json.dumps(res)
                if not self.is_record_writen():
                    self.create_bill_log('EMPTY', file_path='N/A', remark=remark)
            else:
                remark = json.dumps(res)
                if not self.is_record_writen():
                    self.create_bill_log('FAIL', file_path='N/A', remark=remark)

def get_sign(params, key):
    msg = OrderedDict(sorted(params.items()))
    s = ''
    for (k,v) in msg.items():
        s += k
        s += '='
        s += '\"'
        s += str(v)
        s += '\"'
        s += '&'

    s = s[:-1]

    print('Input string to RSA signature[%s]' % s)
    sign = rsa.sign(s, key, 'SHA-1')
    print(sign)

    # urlencode
    sign_urlencoded = urlquote(sign)
    print(sign_urlencoded)

    return sign_urlencoded

def random_str(length):
    str = ''
    chars = 'AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz0123456789'
    count = len(chars) - 1
    random = Random()
    for i in range(length):
        str+=chars[random.randint(0, count)]
    return str
